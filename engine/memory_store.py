from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

MEMORY_PATH = Path(__file__).parent.parent / "memory"
EMBED_MODEL = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def load_memory_store():
    if (MEMORY_PATH / "index.faiss").exists():
        return FAISS.load_local(str(MEMORY_PATH), EMBED_MODEL, allow_dangerous_deserialization=True)
    else:
        return FAISS.from_documents([], EMBED_MODEL)  # empty store

def save_memory_store(store):
    store.save_local(str(MEMORY_PATH))

def add_memory_fact(text):
    doc = Document(page_content=text)
    index_path = MEMORY_PATH / "index.faiss"
    if index_path.exists():
        store = load_memory_store()
        store.add_documents([doc])
    else:
        store = FAISS.from_documents([doc], EMBED_MODEL)

    save_memory_store(store)

def search_memory(query, k=3):
    store = load_memory_store()
    return store.similarity_search(query, k=k)

def recall_memory() -> list[str]:
    store = load_memory_store()
    return [doc.page_content for doc in store.similarity_search("", k=50)]  # rough full recall

def forget_memory(keyword: str) -> int:
    store = load_memory_store()
    all_docs = store.similarity_search("", k=50)
    remaining = [doc for doc in all_docs if keyword.lower() not in doc.page_content.lower()]
    if len(remaining) == len(all_docs):
        return 0  # nothing matched

    new_store = FAISS.from_documents(remaining, EMBED_MODEL)
    save_memory_store(new_store)
    return len(all_docs) - len(remaining)
