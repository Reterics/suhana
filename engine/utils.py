"""
Shared utilities for the Suhana AI Assistant.

This module contains shared utilities used across the Suhana codebase.
"""

import logging
import json
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

# Configure a logger for this module
logger = logging.getLogger(__name__)

def configure_logging(name: Optional[str] = None, level: int = logging.INFO) -> logging.Logger:
    """
    Configure logging with a consistent format.

    Args:
        name: The name of the logger (defaults to __name__ if None)
        level: The logging level (defaults to INFO)

    Returns:
        A configured logger instance
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(name or __name__)

def get_embedding_model(model_name: str = "all-MiniLM-L6-v2") -> HuggingFaceEmbeddings:
    """
    Get a HuggingFace embedding model with the specified name.

    Args:
        model_name: The name of the HuggingFace model to use

    Returns:
        A HuggingFaceEmbeddings instance
    """
    return HuggingFaceEmbeddings(model_name=model_name)

def save_vectorstore(
    documents: List[Document],
    embedding_model: HuggingFaceEmbeddings,
    target_dir: Union[str, Path],
    metadata: Optional[Dict[str, Any]] = None
) -> FAISS:
    """
    Create and save a FAISS vector store from documents.

    Args:
        documents: List of documents to index
        embedding_model: The embedding model to use
        target_dir: Directory to save the vector store
        metadata: Optional metadata to save with the vector store

    Returns:
        The created FAISS vector store
    """
    target_path = Path(target_dir)
    target_path.mkdir(parents=True, exist_ok=True)

    # Create vector store
    vectorstore = FAISS.from_documents(documents, embedding_model)
    vectorstore.save_local(str(target_path))

    # Save metadata if provided
    if metadata:
        with open(target_path / 'metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)

    return vectorstore

def load_vectorstore(
    path: Union[str, Path],
    embedding_model: Optional[HuggingFaceEmbeddings] = None
) -> Optional[FAISS]:
    """
    Load a FAISS vector store from the specified path.

    Args:
        path: Path to the vector store
        embedding_model: The embedding model to use (if None, a default model will be created)

    Returns:
        The loaded FAISS vector store or None if loading fails
    """
    path_obj = Path(path)

    if not (path_obj / "index.faiss").exists():
        logger.error(f"❌ Vector store not found at {path}")
        return None

    if embedding_model is None:
        embedding_model = get_embedding_model()

    try:
        return FAISS.load_local(
            str(path_obj),
            embedding_model,
            allow_dangerous_deserialization=True
        )
    except Exception as e:
        logger.error(f"❌ Failed to load vector store: {e}")
        return None
