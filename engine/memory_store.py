# engine/memory_store.py
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from langchain_community.vectorstores import FAISS

# The HuggingFaceEmbeddings class from langchain_community.embeddings is deprecated
# To fix this properly, run: pip install -U langchain-huggingface
try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    # Fallback to deprecated import
    from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# Default embedding model
EMBED_MODEL = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

class MemoryStore:
    """
    Manages memory storage with support for user-specific memory and shared knowledge.

    This class handles:
    - Separate memory storage for each user
    - Shared knowledge base across users
    - Privacy controls for user memory
    - Memory management tools
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize the MemoryStore.

        Args:
            base_dir: Base directory for memory files. If None, uses the parent directory of the current file.
        """
        self.base_dir = base_dir or Path(__file__).parent.parent

        # Shared memory path
        self.shared_memory_path = self.base_dir / "memory"
        self.shared_memory_path.mkdir(exist_ok=True)

        # User-specific memory path
        self.users_dir = self.base_dir / "users"
        self.users_dir.mkdir(exist_ok=True)

        # Embedding model
        self.embed_model = EMBED_MODEL

    def get_user_memory_path(self, user_id: str) -> Path:
        """
        Get the path to a user's memory directory.

        Args:
            user_id: User ID to get memory directory for

        Returns:
            Path to the user's memory directory
        """
        user_memory_dir = self.users_dir / user_id / "memory"
        user_memory_dir.mkdir(parents=True, exist_ok=True)
        return user_memory_dir

    def load_memory_store(self, user_id: Optional[str] = None) -> FAISS:
        """
        Load a memory store.

        Args:
            user_id: Optional user ID. If None, loads shared memory.

        Returns:
            FAISS vector store
        """
        memory_path = self.get_user_memory_path(user_id) if user_id else self.shared_memory_path

        if (memory_path / "index.faiss").exists():
            return FAISS.load_local(str(memory_path), self.embed_model, allow_dangerous_deserialization=True)
        else:
            return FAISS.from_documents([], self.embed_model)  # empty store

    def save_memory_store(self, store: FAISS, user_id: Optional[str] = None) -> None:
        """
        Save a memory store.

        Args:
            store: FAISS vector store to save
            user_id: Optional user ID. If None, saves to shared memory.
        """
        memory_path = self.get_user_memory_path(user_id) if user_id else self.shared_memory_path
        store.save_local(str(memory_path))

    def add_memory_fact(self, text: str, user_id: Optional[str] = None, private: bool = True) -> bool:
        """
        Add a memory fact.

        Args:
            text: Text to add to memory
            user_id: Optional user ID. If None, adds to shared memory.
            private: Whether the memory is private to the user. If False and user_id is provided,
                    adds to both user memory and shared memory.

        Returns:
            True if memory was added successfully, False otherwise
        """
        try:
            doc = Document(page_content=text)

            # Add to user memory if user_id is provided
            if user_id:
                user_store = self.load_memory_store(user_id)
                user_store.add_documents([doc])
                self.save_memory_store(user_store, user_id)

            # Add to shared memory if not private or no user_id
            if not private or not user_id:
                shared_store = self.load_memory_store()
                shared_store.add_documents([doc])
                self.save_memory_store(shared_store)

            return True
        except Exception as e:
            logger.error(f"Error adding memory fact: {e}")
            return False

    def search_memory(self, query: str, user_id: Optional[str] = None,
                     include_shared: bool = True, k: int = 3) -> List[Document]:
        """
        Search memory.

        Args:
            query: Query to search for
            user_id: Optional user ID. If None, searches only shared memory.
            include_shared: Whether to include shared memory in search results
            k: Number of results to return

        Returns:
            List of documents matching the query
        """
        results = []

        # Search user memory if user_id is provided
        if user_id:
            user_store = self.load_memory_store(user_id)
            user_results = user_store.similarity_search(query, k=k)
            results.extend(user_results)

        # Search shared memory if include_shared is True
        if include_shared:
            shared_store = self.load_memory_store()
            shared_results = shared_store.similarity_search(query, k=k)

            # Add shared results that aren't already in user results
            for doc in shared_results:
                if doc.page_content not in [d.page_content for d in results]:
                    results.append(doc)

        # Limit to k results
        return results[:k]

    def recall_memory(self, user_id: Optional[str] = None,
                     include_shared: bool = True, k: int = 50) -> List[str]:
        """
        Recall memory facts.

        Args:
            user_id: Optional user ID. If None, recalls only shared memory.
            include_shared: Whether to include shared memory in recall
            k: Maximum number of facts to recall

        Returns:
            List of memory facts
        """
        results = []

        # Recall user memory if user_id is provided
        if user_id:
            user_store = self.load_memory_store(user_id)
            user_results = user_store.similarity_search("", k=k)
            results.extend([doc.page_content for doc in user_results])

        # Recall shared memory if include_shared is True
        if include_shared:
            shared_store = self.load_memory_store()
            shared_results = shared_store.similarity_search("", k=k)

            # Add shared results that aren't already in user results
            for doc in shared_results:
                if doc.page_content not in results:
                    results.append(doc.page_content)

        # Limit to k results
        return results[:k]

    def forget_memory(self, keyword: str, user_id: Optional[str] = None,
                     forget_shared: bool = False) -> Tuple[int, int]:
        """
        Forget memory facts containing a keyword.

        Args:
            keyword: Keyword to search for in memory facts
            user_id: Optional user ID. If None, forgets only from shared memory.
            forget_shared: Whether to forget from shared memory as well

        Returns:
            Tuple of (user_forgotten_count, shared_forgotten_count)
        """
        user_forgotten = 0
        shared_forgotten = 0

        # Forget from user memory if user_id is provided
        if user_id:
            user_store = self.load_memory_store(user_id)
            all_user_docs = user_store.similarity_search("", k=50)
            remaining_user_docs = [doc for doc in all_user_docs
                                if keyword.lower() not in doc.page_content.lower()]

            user_forgotten = len(all_user_docs) - len(remaining_user_docs)

            if user_forgotten > 0:
                new_user_store = FAISS.from_documents(remaining_user_docs, self.embed_model)
                self.save_memory_store(new_user_store, user_id)

        # Forget from shared memory if forget_shared is True or no user_id
        if forget_shared or not user_id:
            shared_store = self.load_memory_store()
            all_shared_docs = shared_store.similarity_search("", k=50)
            remaining_shared_docs = [doc for doc in all_shared_docs
                                   if keyword.lower() not in doc.page_content.lower()]

            shared_forgotten = len(all_shared_docs) - len(remaining_shared_docs)

            if shared_forgotten > 0:
                new_shared_store = FAISS.from_documents(remaining_shared_docs, self.embed_model)
                self.save_memory_store(new_shared_store)

        return user_forgotten, shared_forgotten

    def clear_memory(self, user_id: Optional[str] = None, clear_shared: bool = False) -> bool:
        """
        Clear all memory.

        Args:
            user_id: Optional user ID. If None, clears only shared memory.
            clear_shared: Whether to clear shared memory as well

        Returns:
            True if memory was cleared successfully, False otherwise
        """
        try:
            # Clear user memory if user_id is provided
            if user_id:
                user_memory_path = self.get_user_memory_path(user_id)
                empty_store = FAISS.from_documents([], self.embed_model)
                self.save_memory_store(empty_store, user_id)

            # Clear shared memory if clear_shared is True or no user_id
            if clear_shared or not user_id:
                empty_store = FAISS.from_documents([], self.embed_model)
                self.save_memory_store(empty_store)

            return True
        except Exception as e:
            logger.error(f"Error clearing memory: {e}")
            return False

    def get_memory_stats(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get memory statistics.

        Args:
            user_id: Optional user ID. If None, gets stats for shared memory only.

        Returns:
            Dictionary containing memory statistics
        """
        stats = {}

        # Get user memory stats if user_id is provided
        if user_id:
            user_store = self.load_memory_store(user_id)
            user_docs = user_store.similarity_search("", k=1000)
            stats["user_memory_count"] = len(user_docs)

        # Get shared memory stats
        shared_store = self.load_memory_store()
        shared_docs = shared_store.similarity_search("", k=1000)
        stats["shared_memory_count"] = len(shared_docs)

        return stats


# Create a global instance for backward compatibility
memory_store = MemoryStore()

# Legacy functions for backward compatibility
def load_memory_store():
    return memory_store.load_memory_store()

def save_memory_store(store):
    memory_store.save_memory_store(store)

def add_memory_fact(text):
    return memory_store.add_memory_fact(text)

def search_memory(query, k=3):
    return memory_store.search_memory(query, k=k)

def recall_memory() -> list[str]:
    return memory_store.recall_memory()

def forget_memory(keyword: str) -> int:
    user_forgotten, shared_forgotten = memory_store.forget_memory(keyword)
    return shared_forgotten
