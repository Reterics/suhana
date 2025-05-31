"""
Shared utilities for the Suhana AI Assistant.

This module contains shared utilities used across the Suhana codebase.
"""

import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Tuple

from langchain_community.vectorstores import FAISS

# The HuggingFaceEmbeddings class from langchain_community.embeddings is deprecated
# To fix this properly, run: pip install -U langchain-huggingface
try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    # Fallback to deprecated import
    from langchain_community.embeddings import HuggingFaceEmbeddings

from langchain_core.documents import Document
from engine.logging_config import get_logger

# Get a logger for this module
logger = get_logger(__name__)

def configure_logging(name: Optional[str] = None, level: Optional[int] = None) -> logging.Logger:
    """
    Get a logger with the given name.

    This function is maintained for backward compatibility.
    New code should use engine.logging_config.get_logger directly.

    Args:
        name: The name of the logger (defaults to __name__ if None)
        level: The logging level (ignored, use settings.json to configure levels)

    Returns:
        A configured logger instance
    """
    from engine.logging_config import get_logger
    return get_logger(name or __name__)

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
    target_path = Path(target_dir).resolve()
    target_path.mkdir(parents=True, exist_ok=True)
    if not target_path.exists():
        logger.error("Directory creation failed. Check path and permissions:", target_path)

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
) -> Tuple[Optional[FAISS], Optional[Dict[str, Any]]]:
    """
    Load a FAISS vector store from the specified path.

    Args:
        path: Path to the vector store
        embedding_model: The embedding model to use (if None, a default model will be created)

    Returns:
        A tuple of (vectorstore, metadata) where vectorstore is the loaded FAISS vector store
        and metadata is the metadata dictionary, or (None, None) if loading fails
    """
    path_obj = Path(path)

    if not (path_obj / "index.faiss").exists():
        logger.error(f"Vector store not found at {path}")
        return None, None

    if embedding_model is None:
        embedding_model = get_embedding_model()

    # Load metadata if it exists
    metadata = None
    metadata_path = path_obj / "metadata.json"
    if metadata_path.exists():
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load metadata: {e}")

    try:
        vectorstore = FAISS.load_local(
            str(path_obj),
            embedding_model,
            allow_dangerous_deserialization=True
        )
        return vectorstore, metadata
    except Exception as e:
        logger.error(f"Failed to load vector store: {e}")
        return None, None
