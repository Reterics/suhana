import os
from langchain.vectorstores import FAISS
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.document_loaders import TextLoader
from langchain.text_splitter import CharacterTextSplitter

knowledge_dir = "knowledge"
embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
text_splitter = CharacterTextSplitter(chunk_size=512, chunk_overlap=64)

docs = []

if not os.path.isdir(knowledge_dir):
    print("❌ 'knowledge/' folder not found.")
    exit(1)

for fname in os.listdir(knowledge_dir):
    path = os.path.join(knowledge_dir, fname)
    if fname.endswith((".txt", ".md")) and os.path.isfile(path):
        print(f"📄 Loading: {fname}")
        loader = TextLoader(path, encoding="utf-8")
        try:
            split_docs = loader.load_and_split(text_splitter)
            docs.extend(split_docs)
        except Exception as e:
            print(f"⚠️ Failed to load {fname}: {e}")

if not docs:
    print("❌ No documents found or failed to process any.")
    exit(1)


vectorstore = FAISS.from_documents(docs, embedding_model)
vectorstore.save_local("vectorstore")
print("✅ Vectorstore updated.")
