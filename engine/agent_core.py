import subprocess
from pathlib import Path

from engine.profile import summarize_profile_for_prompt, save_profile
from engine.backends.ollama import query_ollama
from engine.backends.openai import query_openai
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

# Global/shared components
embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
VECTORSTORE_PATH = Path(__file__).parent.parent / "vectorstore"
INDEX_FILE = VECTORSTORE_PATH / "index.faiss"

def get_vectorstore():
    if not INDEX_FILE.exists():
        print("📭 Vectorstore not found — running ingest.py...")
        subprocess.run(["python", "ingest.py"], check=True)

    return FAISS.load_local(
        str(VECTORSTORE_PATH),
        embedding_model,
        allow_dangerous_deserialization=True
    )

vectorstore = get_vectorstore()

def handle_input(user_input: str, backend: str, profile: dict, settings: dict) -> str:
    docs = vectorstore.similarity_search(user_input, k=3)
    context = "\n".join([d.page_content for d in docs])
    system_prompt = f"{summarize_profile_for_prompt(profile)}\nContext: {context}"

    if backend == "ollama":
        reply = query_ollama(user_input, system_prompt, profile, settings)
    elif backend == "openai":
        reply = query_openai(user_input, system_prompt, profile, settings)
    else:
        reply = "[❌ Unknown backend]"

    save_profile(profile)
    return reply
