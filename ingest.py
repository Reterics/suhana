"""
Knowledge Base Indexer for Suhana AI Assistant

This module indexes documents from the knowledge directory into a vector store for semantic search.
It supports text and markdown files.

Usage:
    python ingest.py
"""

import sys
from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import CharacterTextSplitter
from engine.utils import configure_logging, get_embedding_model, save_vectorstore

# Configure logging
logger = configure_logging(__name__)

def index_knowledge_base():
    """Index documents from the knowledge directory into a vector store."""
    knowledge_dir = Path("knowledge")
    embedding_model = get_embedding_model("all-MiniLM-L6-v2")
    text_splitter = CharacterTextSplitter(chunk_size=512, chunk_overlap=64)

    docs = []

    if not knowledge_dir.is_dir():
        logger.error("❌ 'knowledge/' folder not found.")
        return False

    for file_path in knowledge_dir.iterdir():
        if file_path.suffix.lower() in (".txt", ".md") and file_path.is_file():
            logger.info(f"📄 Loading: {file_path.name}")
            loader = TextLoader(str(file_path), encoding="utf-8")
            try:
                split_docs = loader.load_and_split(text_splitter)
                docs.extend(split_docs)
            except Exception as e:
                logger.warning(f"⚠️ Failed to load {file_path.name}: {e}")

    if not docs:
        logger.error("❌ No documents found or failed to process any.")
        return False

    save_vectorstore(docs, embedding_model, "vectorstore")
    logger.info("✅ Vectorstore updated.")
    return True

def main():
    """Main entry point for the script."""
    success = index_knowledge_base()
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
