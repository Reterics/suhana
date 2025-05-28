import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

from engine.profile import summarize_profile_for_prompt
from engine.backends.ollama import query_ollama
from engine.backends.openai import query_openai
from langchain_community.vectorstores import FAISS
from engine.memory_store import search_memory
from engine.utils import configure_logging, get_embedding_model, load_vectorstore

# Configure logging
logger = configure_logging(__name__)

# Constants
VECTORSTORE_PATH = Path(__file__).parent.parent / "vectorstore"

# Singleton class for managing vectorstore state
class VectorStoreManager:
    _instance = None

    def __init__(self):
        self.current_vector_mode = None
        self.vectorstore = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(VectorStoreManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize the vectorstore manager."""
        self.embedding_model = get_embedding_model()
        self.current_vector_mode = None
        self.vectorstore = None

    def get_vectorstore(self, profile: Optional[Dict[str, Any]] = None) -> Optional[FAISS]:
        """
        Get the appropriate vectorstore based on the profile and mode.

        Args:
            profile: User profile containing mode and project path

        Returns:
            FAISS vectorstore or None if not available
        """
        mode = "normal"
        path = None

        if profile is not None:
            mode = profile.get("mode", "normal")
            path = profile.get("project_path", None)

        # If mode or path is not specified, default to normal mode
        if mode is None or (mode == "development" and path is None):
            mode = "normal"

        # If mode hasn't changed, return the existing vectorstore
        if mode == self.current_vector_mode and self.vectorstore is not None:
            return self.vectorstore

        # Update the current mode
        self.current_vector_mode = mode

        # Determine the path to the vectorstore
        if mode == "development" and profile.get("project_path"):
            path = Path(profile["project_path"]).name
        else:
            path = VECTORSTORE_PATH

        # Check if the vectorstore exists
        if not (Path(path) / "index.faiss").exists():
            if mode == "development":
                logger.warning("❌ Vectorstore not found — please run ingest_project.py.")
                return None
            elif mode == "normal":
                logger.info("📄 Vectorstore not found — running ingest.py...")
                try:
                    subprocess.run(["python", "ingest.py"], check=True)
                except subprocess.CalledProcessError as e:
                    logger.error(f"❌ Failed to run ingest.py: {e}")
                    return None

        # Load the vectorstore
        self.vectorstore = load_vectorstore(path, self.embedding_model)
        return self.vectorstore

# Initialize the vectorstore manager
vectorstore_manager = VectorStoreManager()
vectorstore_manager.get_vectorstore()

def should_include_documents(user_input: str, mems: List[Any]) -> bool:
    """
    Determine if documents should be included in the context based on heuristics.

    Args:
        user_input: The user's query
        mems: List of memory items

    Returns:
        Boolean indicating whether to include documents
    """
    keywords = ["explain", "how", "what is", "summarize", "doc", "article", "paper", "research", "source"]

    # Heuristic 1: Direct query keywords
    if any(k in user_input.lower() for k in keywords):
        return True

    # Heuristic 2: Memory contains only short facts
    if all(len(m.page_content.split()) < 10 for m in mems):
        return True

    # Heuristic 3: No strong semantic match (low memory count)
    if len(mems) < 2:
        return True

    return False


def handle_input(
    user_input: str,
    backend: str,
    profile: Dict[str, Any],
    settings: Dict[str, Any],
    force_stream: bool = False
) -> str:
    """
    Process user input and generate a response using the appropriate backend.

    Args:
        user_input: The user's query
        backend: The LLM backend to use (ollama or openai)
        profile: User profile information
        settings: Application settings
        force_stream: Whether to force streaming mode

    Returns:
        The generated response
    """
    # Get relevant memories
    mems = search_memory(user_input, k=10)
    include_docs = should_include_documents(user_input, mems)

    # Build context from memories and documents
    context_parts = []
    if mems:
        context_parts.append("MEMORY:\n" + "\n".join(f"- {m.page_content}" for m in mems))

    # Include documents if needed
    if include_docs:
        # Get the vectorstore for the current profile
        current_vectorstore = vectorstore_manager.get_vectorstore(profile)

        if current_vectorstore:
            try:
                docs_with_scores = current_vectorstore.similarity_search_with_score(user_input, k=10)
                docs = [doc for doc, score in docs_with_scores if score < 0.3]
                if docs:
                    context_parts.append("DOCUMENTS:\n" + "\n".join(f"- {d.page_content}" for d in docs))
            except Exception as e:
                logger.error(f"❌ Error during document search: {e}")
        else:
            logger.warning("❌ Vectorstore not available for document search")

    # Combine context and create system prompt
    context = "\n".join(context_parts)
    system_prompt = f"{summarize_profile_for_prompt(profile)}\n\nContext:\n{context}"

    if not context_parts:
        logger.warning("⚠️ No relevant memory or documents found.")

    # Generate response using the appropriate backend
    try:
        if backend == "ollama":
            reply = query_ollama(user_input, system_prompt, profile, settings, force_stream=force_stream)
        elif backend == "openai":
            reply = query_openai(user_input, system_prompt, profile, settings, force_stream=force_stream)
        else:
            logger.error(f"❌ Unknown backend: {backend}")
            reply = "❌ Unknown backend"
    except Exception as e:
        logger.error(f"❌ Error generating response: {e}")
        reply = f"❌ Error: {str(e)}"

    return reply
