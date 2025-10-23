"""
Project Code Indexer for Suhana AI Assistant

This module indexes code from a project directory into a vector store for semantic search.
It supports multiple programming languages and respects code structure during parsing.

Usage:
    python ingest_project.py <project_path> [--target <target_dir>] [--model <model_name>]

Example:
    python ingest_project.py ./my_project --target ./my_vectorstore --model all-MiniLM-L6-v2
"""
import json
import logging
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set

import pathspec
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document

from engine.agent_core import register_backends
from engine.utils import configure_logging, get_embedding_model, save_vectorstore
from engine.project_detector import detect_project_type

# Configure logging
logger = configure_logging(__name__)

register_backends()

# Language-specific file extensions
LANGUAGE_EXTENSIONS: Dict[str, Set[str]] = {
    'python': {'.py', '.pyi', '.pyx', '.pxd'},
    'javascript': {'.js', '.jsx', '.mjs'},
    'typescript': {'.ts', '.tsx'},
    'html': {'.html', '.htm'},
    'css': {'.css', '.scss', '.sass', '.less'},
    'go': {'.go'},
    'java': {'.java'},
    'c': {'.c', '.h'},
    'cpp': {'.cpp', '.hpp', '.cc', '.cxx', '.hxx'},
    'csharp': {'.cs'},
    'ruby': {'.rb'},
    'rust': {'.rs'},
    'php': {'.php'},
    'markdown': {'.md', '.markdown'},
    'yaml': {'.yml', '.yaml'},
    'json': {'.json'},
    'toml': {'.toml'},
    'dockerfile': {'Dockerfile'},
}

# Mapping from file extension to language string for language identification
EXTENSION_TO_LANGUAGE: Dict[str, Optional[str]] = {
    '.py': 'python',
    '.js': 'js',
    '.jsx': 'js',
    '.ts': 'ts',
    '.tsx': 'ts',
    '.html': 'html',
    '.css': 'css',
    '.go': 'go',
    '.java': 'java',
    '.c': 'cpp',      # Use 'cpp' for C/C++
    '.cpp': 'cpp',
    '.cs': 'csharp',
    '.rb': 'ruby',
    '.rs': 'rust',
    '.php': 'php',
    '.md': 'markdown',
    '.json': 'json',
}


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Index project code for semantic search')
    parser.add_argument('project_path', type=str, help='Path to the project directory')
    parser.add_argument(
        '--target',
        type=str,
        default='vectorstore_dev',
        help='Target directory for the vector store'
    )
    parser.add_argument(
        '--model',
        type=str,
        default='all-MiniLM-L6-v2',
        help='HuggingFace embedding model name'
    )
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=512,
        help='Size of text chunks for indexing'
    )
    parser.add_argument(
        '--chunk-overlap',
        type=int,
        default=64,
        help='Overlap between text chunks'
    )
    parser.add_argument(
        '--exclude',
        type=str,
        nargs='+',
        default=[],
        help='Additional directories or files to exclude (common patterns like .git, node_modules, etc. are excluded by default)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    return parser.parse_args()

def get_all_supported_extensions() -> Set[str]:
    """Get a set of all supported file extensions."""
    extensions = set()
    for ext_set in LANGUAGE_EXTENSIONS.values():
        extensions.update(ext_set)
    return extensions

def get_language_for_file(file_path: Path) -> Optional[str]:
    """Determine the programming language for a given file path."""
    # Check for exact filename matches first (e.g., Dockerfile)
    filename = file_path.name
    for lang, extensions in LANGUAGE_EXTENSIONS.items():
        if filename in extensions:
            return EXTENSION_TO_LANGUAGE.get(filename)

    # Then check by extension
    extension = file_path.suffix.lower()
    return EXTENSION_TO_LANGUAGE.get(extension)

def get_appropriate_splitter(
    file_path: Path,
    default_chunk_size: int,
    default_chunk_overlap: int
) -> RecursiveCharacterTextSplitter:
    """Get the appropriate text splitter for a given file."""
    # Use a single constructor without the language parameter
    # as TextSplitter.__init__() doesn't accept a 'language' parameter
    return RecursiveCharacterTextSplitter(
        chunk_size=default_chunk_size,
        chunk_overlap=default_chunk_overlap
    )

def should_exclude(path: Path, spec: Optional[pathspec.PathSpec]) -> bool:
    """Decide whether a path should be excluded.

    Applies built-in exclusions first (dot-prefixed dirs, common build/output dirs).
    If a .gitignore spec is provided, it is also applied; otherwise, only built-ins are used.
    """
    # Built-in exclusions by path parts
    for part in path.parts:
        if part.startswith('.') or part in {
            'node_modules', 'dist', 'build', 'venv', '.venv', 'logs',
            '__pycache__', 'vectorstore'
        }:
            return True

    # If no gitignore spec, do not exclude further
    if spec is None:
        return False

    # Apply .gitignore-style matching relative to project root if available
    base = getattr(spec, 'root', None)
    try:
        rel_path = str(path.relative_to(base)) if base else str(path)
    except Exception:
        rel_path = str(path)
    return spec.match_file(rel_path)

def process_file(
    file_path: Path,
    chunk_size: int,
    chunk_overlap: int
) -> List[Document]:
    """Process a single file and return the resulting documents."""
    try:
        # Get language-appropriate splitter
        splitter = get_appropriate_splitter(file_path, chunk_size, chunk_overlap)

        # Load and split the file
        loader = TextLoader(str(file_path), encoding="utf-8")
        documents = loader.load_and_split(splitter)

        # Add metadata about the file
        for doc in documents:
            if not doc.metadata:
                doc.metadata = {}
            doc.metadata.update({
                'source': str(file_path),
                'filename': file_path.name,
                'extension': file_path.suffix,
                'path': str(file_path.parent),
            })

        logger.debug(f"Processed: {file_path.name} → {len(documents)} chunks")
        return documents

    except Exception as e:
        logger.warning(f"Failed to process {file_path.name}: {str(e)}")
        return []

def load_gitignore_spec(project_path: Path) -> Optional[pathspec.PathSpec]:
    gitignore_path = project_path / ".gitignore"
    if not gitignore_path.exists():
        logger.debug(".gitignore not found; proceeding without it")
        return None
    lines = gitignore_path.read_text().splitlines()
    filtered_lines = [line for line in lines if line.strip() and not line.strip().startswith("#")]
    spec = pathspec.PathSpec.from_lines("gitwildmatch", filtered_lines)
    # Attach root attribute to help relative matching
    setattr(spec, 'root', project_path)
    return spec

def index_project(
    project_path: Path,
    target_store: Path,
    embedding_model_name: str,
    chunk_size: int,
    chunk_overlap: int,
    verbose: bool
) -> Tuple[int, int]:
    """
    Index a project directory into a vector store.

    Args:
        project_path: Path to the project directory
        target_store: Path to save the vector store
        embedding_model_name: Name of the HuggingFace embedding model
        chunk_size: Size of text chunks for indexing
        chunk_overlap: Overlap between text chunks
        verbose: Whether to enable verbose logging

    Notes:
        The following are automatically excluded without needing to specify:
        - Files and folders starting with a dot (like .git, .venv)
        - Common package-related folders (node_modules, dist, build, venv, logs)

    Returns:
        Tuple of (number of files processed, number of chunks indexed)
    """
    if verbose:
        logger.setLevel(logging.DEBUG)

    # Create target directory
    target_store.mkdir(parents=True, exist_ok=True)

    # Initialize embedding model
    logger.info(f"Initializing embedding model: {embedding_model_name}")
    embedding_model = get_embedding_model(model_name=embedding_model_name)

    # Get all supported extensions
    supported_extensions = get_all_supported_extensions()
    gitignore_excludes = load_gitignore_spec(project_path)

    # Process files
    all_documents = []
    files_processed = 0

    logger.info(f"Scanning project directory: {project_path}")
    for path in project_path.rglob("*"):
        # Skip directories and excluded paths
        if not path.is_file() or should_exclude(path, gitignore_excludes):
            continue

        # Skip unsupported file types
        if path.suffix.lower() not in supported_extensions and path.name not in supported_extensions:
            continue

        # Process the file
        documents = process_file(path, chunk_size, chunk_overlap)
        if documents:
            all_documents.extend(documents)
            files_processed += 1

    # Create and save vector store
    if all_documents:
        logger.info(f"Creating vector store with {len(all_documents)} chunks from {files_processed} files")

        # Detect project type and extract metadata
        project_metadata = detect_project_type(project_path)

        # Create metadata about the indexing
        metadata = {
            'files_processed': files_processed,
            'chunks_indexed': len(all_documents),
            'embedding_model': embedding_model_name,
            'chunk_size': chunk_size,
            'chunk_overlap': chunk_overlap,
            'project_path': str(project_path),
            'project_info': project_metadata,
        }

        # Save vector store
        save_vectorstore(all_documents, embedding_model, target_store)

        # Save metadata
        with open(project_path / 'metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"✅ Project indexed to {target_store}")
        return files_processed, len(all_documents)
    else:
        logger.error("❌ No valid files found or all files failed processing")
        return 0, 0

def main():
    """Main entry point for the script."""
    args = parse_arguments()

    project_path = Path(args.project_path)
    target_store = Path(args.target)

    if not project_path.exists() or not project_path.is_dir():
        logger.error(f"Project path does not exist or is not a directory: {project_path}")
        sys.exit(1)

    files_processed, chunks_indexed = index_project(
        project_path=project_path,
        target_store=target_store,
        embedding_model_name=args.model,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        verbose=args.verbose
    )

    if files_processed == 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
