# POC - Not ready for production
import sys
from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader

project_path = Path(sys.argv[1])
target_store = Path("vectorstore_dev")
target_store.mkdir(parents=True, exist_ok=True)

embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=64)

extensions = (".py", ".ts", ".tsx", ".js", ".json", ".yml", ".md")
docs = []

for path in project_path.rglob("*"):
    if path.suffix in extensions and path.is_file():
        loader = TextLoader(str(path), encoding="utf-8")
        try:
            docs += loader.load_and_split(splitter)
        except Exception as e:
            print(f"⚠️ Failed: {path.name} → {e}")

if docs:
    vs = FAISS.from_documents(docs, embedding_model)
    vs.save_local(str(target_store))
    print(f"✅ Project indexed to {target_store}")
else:
    print("❌ No valid files found")
