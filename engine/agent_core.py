import json
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Generator

from engine.interfaces import VectorStoreInterface, VectorStoreManagerInterface, MemoryStoreInterface, LLMBackendInterface
from engine.profile_utils import summarize_profile_for_prompt
from langchain_community.vectorstores import FAISS

from engine.project_detector import detect_project_type
from engine.utils import get_embedding_model, load_vectorstore, refresh_vectorstore, load_metadata
from engine.di import container
from engine.error_handling import (
    error_boundary,
    VectorStoreError,
    BackendError,
)
from engine.logging_config import get_logger

# Get a logger for this module
logger = get_logger(__name__)

# Implementation of VectorStoreManager that implements the interface
class VectorStoreManager(VectorStoreManagerInterface):
    """
    Implementation of VectorStoreManagerInterface that manages vectorstore state.
    """

    def __init__(self):
        self._current_vector_mode = None
        self._vectorstore = None
        self._embedding_model = get_embedding_model()
        self._project_metadata = None

    @property
    def current_vector_mode(self) -> Optional[str]:
        """Get the current vector mode."""
        return self._current_vector_mode

    @current_vector_mode.setter
    def current_vector_mode(self, value: str) -> None:
        """Set the current vector mode."""
        self._current_vector_mode = value

    @property
    def vectorstore(self) -> Optional[VectorStoreInterface]:
        """Get the current vectorstore."""
        return self._vectorstore

    @property
    def embedding_model(self):
        """Get the embedding model."""
        return self._embedding_model

    @property
    def project_metadata(self) -> Optional[Dict[str, Any]]:
        """Get the project metadata."""
        return self._project_metadata

    def reset_vectorstore(self) -> None:
        """
        Reset the vectorstore, forcing it to be reloaded on the next get_vectorstore call.
        """
        self._vectorstore = None

    @error_boundary(fallback_value=None, error_type=VectorStoreError)
    def reload_vectorstore(self):
        if self._project_metadata is None:
            logger.warning('Project Metadata is empty, fallback')
            return None

        project_path = self._project_metadata.get('path', None)
        if project_path is None:
            logger.warning('Project path is not defined in metadata, fallback')
            return None

        vectorstore_path = Path(project_path)/ 'vectorstore'
        vectorstore = load_vectorstore(vectorstore_path, self._embedding_model)
        if vectorstore is None:
            return None
        # Store the vectorstore and extract project metadata
        self._vectorstore = FAISVectorStoreAdapter(vectorstore)
        return self._vectorstore

    @error_boundary(fallback_value=None, error_type=VectorStoreError)
    def get_vectorstore(self, profile: Optional[Dict[str, Any]] = None) -> Optional[VectorStoreInterface]:
        """
        Get the appropriate vectorstore based on the profile and mode.

        Args:
            profile: User profile containing mode and project path

        Returns:
            Vectorstore or None if not available

        Raises:
            VectorStoreError: If there's an issue with the vectorstore
        """
        mode = "normal"
        path: None | str  = None

        if profile is not None:
            mode = profile.get("mode", "normal")
            path = profile.get("project_path", None)

        # If mode or path is not specified, default to normal mode
        if mode is None or (mode == "development" and path is None):
            mode = "normal"

        prev_path: None | str = None
        if self._project_metadata is not None and 'path' in self._project_metadata:
            prev_path = self._project_metadata['path']

        # If mode and path hasn't changed, return the existing vectorstore
        if mode == self._current_vector_mode and self._vectorstore is not None and prev_path == path:
            logger.info(f"📄 Get Vectorstore - Return cached store for {path}")
            return self._vectorstore

        # Determine the path to the vectorstore
        if path is None or path == "":
            return None

        vectorstore_path = (Path(path)/ 'vectorstore')

        logger.info(f"📄 Get Vectorstore - Mode: {mode} Path: {path} Previous Path: {prev_path}")

        # Update the current mode
        self._current_vector_mode = mode

        if not (vectorstore_path / "index.faiss").exists() and path:
            logger.info("📄 Vectorstore not found — refreshing vectorstore...")
            refresh_vectorstore(vectorstore_path)
            self._project_metadata = load_metadata(path)
        elif path and not (Path(path)/ 'metadata.json').exists():
            print('Refresh metadata')
            metadata_path = Path(path)
            self._project_metadata = detect_project_type(metadata_path)
            metadata = {
                'project_path': str(path),
                'project_info': self._project_metadata,
            }
            with open(metadata_path / 'metadata.json', 'w') as f:
                json.dump(metadata, f, indent=2)
        elif self._project_metadata is None:
            self._project_metadata = load_metadata(path)

        return self.reload_vectorstore()


# Adapter for FAISS vectorstore to implement VectorStoreInterface
class FAISVectorStoreAdapter(VectorStoreInterface):
    """
    Adapter for FAISS vectorstore to implement VectorStoreInterface.
    """

    def __init__(self, faiss_vectorstore: FAISS):
        self._vectorstore = faiss_vectorstore

    def similarity_search_with_score(self, query: str, k: int = 4) -> List[tuple]:
        """
        Search for similar documents with scores.

        Args:
            query: The query string
            k: Number of results to return

        Returns:
            List of (document, score) tuples
        """
        return self._vectorstore.similarity_search_with_score(query, k)

# Adapter for memory store to implement MemoryStoreInterface
class MemoryStoreAdapter(MemoryStoreInterface):
    """
    Adapter for memory store to implement MemoryStoreInterface.
    """

    def __init__(self, search_memory_func):
        self._search_memory = search_memory_func

    def search_memory(self, query: str, k: int = 10) -> List[Any]:
        """
        Search for relevant memories.

        Args:
            query: The query string
            k: Number of results to return

        Returns:
            List of memory items
        """
        return self._search_memory(query, k)

# Adapter for LLM backends to implement LLMBackendInterface
class LLMBackendAdapter(LLMBackendInterface):
    """
    Adapter for LLM backends to implement LLMBackendInterface.
    """

    def __init__(self, query_func):
        self._query = query_func

    def query(
        self,
        user_input: str,
        system_prompt: str,
        profile: Dict[str, Any],
        settings: Dict[str, Any],
        force_stream: bool = False
    ) -> Union[str, Generator[str, None, None]]:
        """
        Query the LLM backend.

        Args:
            user_input: The user's query
            system_prompt: The system prompt
            profile: User profile information
            settings: Application settings
            force_stream: Whether to force streaming mode

        Returns:
            The generated response or a generator for streaming responses
        """
        return self._query(user_input, system_prompt, profile, settings, force_stream)

# Register services with the container
container.register("vectorstore_manager", VectorStoreManager())

# Initialize the vectorstore
container.get_typed("vectorstore_manager", VectorStoreManagerInterface).get_vectorstore()

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


# Register backend factories with the container
def register_backends():
    """Register LLM backend factories with the container."""
    from engine.backends.ollama import query_ollama
    from engine.backends.openai import query_openai
    from engine.backends.gemini import query_gemini
    from engine.backends.claude import query_claude
    from engine.memory_store import search_memory

    # Register memory store
    memory_store = MemoryStoreAdapter(search_memory)
    container.register("memory_store", memory_store)

    # Register LLM backends
    container.register("ollama_backend", LLMBackendAdapter(query_ollama))
    container.register("openai_backend", LLMBackendAdapter(query_openai))
    container.register("gemini_backend", LLMBackendAdapter(query_gemini))
    container.register("claude_backend", LLMBackendAdapter(query_claude))


# Register backends
register_backends()


@error_boundary(fallback_value="I'm sorry, I encountered an error processing your request.", error_type=BackendError)
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

    Raises:
        BackendError: If there's an issue with the LLM backend
        VectorStoreError: If there's an issue with the vectorstore
    """
    # Get dependencies from the container
    memory_store = container.get_typed("memory_store", MemoryStoreInterface)
    vectorstore_manager = container.get_typed("vectorstore_manager", VectorStoreManagerInterface)

    # Get relevant memories
    try:
        mems = memory_store.search_memory(user_input, k=10)
        include_docs = should_include_documents(user_input, mems)
    except Exception as e:
        raise BackendError(
            "Failed to retrieve relevant memories",
            details={"query": user_input},
            cause=e
        )

    # Build context from memories and documents
    context_parts = ["Do not expose private or sensitive information from memory, unless explicitly asked."]

    if mems:
        context_parts.append("MEMORY:\n" + "\n".join(f"- {m.page_content}" for m in mems))

    path = profile.get("project_path", None)
    if path is None and profile.get("mode") == "development":
        logger.warning("Vectorstore path is not defined in the Profile")

    # Include documents if needed
    if include_docs or profile.get("mode") == "development":
        # Get the vectorstore for the current profile
        current_vectorstore = vectorstore_manager.get_vectorstore(profile)

        if current_vectorstore:
            try:
                docs_with_scores = current_vectorstore.similarity_search_with_score(user_input, k=10)
                logger.info(f"Found {len(docs_with_scores)} raw documents relevant to query: {user_input}")
                docs = [doc for doc, score in docs_with_scores if score > 0.7]
                logger.info(f"Found {len(docs)} filtered documents relevant to query: {user_input}")
                if docs:
                    context_parts.append("DOCUMENTS:\n" + "\n".join(f"- {d.page_content}" for d in docs))
            except Exception as e:
                # Log but don't fail the entire request if document search fails
                logger.warning(f"Error during document search: {e}")
                # Add a note about the failure to the context
                context_parts.append("NOTE: Document search failed, results may be limited.")
        else:
            logger.warning("Vectorstore not available for document search")

    # Combine context and create system prompt
    context = "\n".join(context_parts)
    system_prompt = f"{summarize_profile_for_prompt(profile)}\n\nContext:\n{context}"

    if not context_parts:
        logger.warning("No relevant memory or documents found.")

    # Generate response using the appropriate backend
    backend_name = f"{backend}_backend"
    if container.get_or_default(backend_name) is not None:
        llm_backend = container.get_typed(backend_name, LLMBackendInterface)
        try:
            reply = llm_backend.query(user_input, system_prompt, profile, settings, force_stream=force_stream)
        except Exception as e:
            raise BackendError(
                f"Error generating response with {backend} backend",
                details={"backend": backend, "query": user_input},
                cause=e
            )
        return reply

    raise BackendError(
        f"Unknown backend: {backend}",
        details={"available_backends": [name.replace("_backend", "") for name in container._services.keys() if name.endswith("_backend")]}
    )
