import subprocess
from pathlib import Path

from engine.profile import summarize_profile_for_prompt, save_profile_meta
from engine.backends.ollama import query_ollama
from engine.backends.openai import query_openai
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from engine.memory_store import search_memory

# Global/shared components
embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
VECTORSTORE_PATH = Path(__file__).parent.parent / "vectorstore"
INDEX_FILE = VECTORSTORE_PATH / "index.faiss"
current_vector_mode = None

def get_vectorstore(profile = None):
    global current_vector_mode
    global vectorstore
    mode = current_vector_mode
    path = None
    if profile is not None:
        mode = profile.get("mode", "normal")
        path = profile.get("project_path", None)
    if mode is None or path is None:
        mode = "normal"

    if mode == current_vector_mode:
        return vectorstore

    current_vector_mode = mode
    if mode == "development" and profile.get("project_path"):
        path = Path(profile["project_path"]).name
    else:
        path = VECTORSTORE_PATH

    if not Path(f"{path}/index.faiss").exists():
        if mode == "development":
            print("📭 Vectorstore not found — please run ingest_project.py.")
            return None
        elif mode == "normal":
            print("📭 Vectorstore not found — running ingest.py...")
            subprocess.run(["python", "ingest.py"], check=True)

    return FAISS.load_local(str(path), embedding_model, allow_dangerous_deserialization=True)

vectorstore = get_vectorstore()

def should_include_documents(user_input: str, mems: list) -> bool:
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


def handle_input(user_input: str, backend: str, profile: dict, settings: dict, force_stream=False) -> str:
    mems = search_memory(user_input, k=10)
    include_docs = should_include_documents(user_input, mems)

    context_parts = []
    if mems:
        context_parts.append("MEMORY:\n" + "\n".join(f"- {m.page_content}" for m in mems))

    if include_docs:
        docs_with_scores = vectorstore.similarity_search_with_score(user_input, k=10)
        docs = [doc for doc, score in docs_with_scores if score < 0.3]
        if docs:
            context_parts.append("DOCUMENTS:\n" + "\n".join(f"- {d.page_content}" for d in docs))
    context = "\n".join(context_parts)
    system_prompt = f"{summarize_profile_for_prompt(profile)}\n\nContext:\n{context}"
    if not context_parts:
        print("[⚠️] No relevant memory or documents found.")

    if backend == "ollama":
        reply = query_ollama(user_input, system_prompt, profile, settings, force_stream=force_stream)
    elif backend == "openai":
        reply = query_openai(user_input, system_prompt, profile, settings, force_stream=force_stream)
    else:
        reply = "[❌ Unknown backend]"

    return reply
