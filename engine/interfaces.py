"""
Interfaces for Suhana components

This module defines interfaces for various components in the Suhana application,
enabling better dependency injection and testability.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Generator, Union

class VectorStoreInterface(ABC):
    """Interface for vector store operations."""

    @abstractmethod
    def similarity_search_with_score(self, query: str, k: int = 4) -> List[tuple]:
        """
        Search for similar documents with scores.

        Args:
            query: The query string
            k: Number of results to return

        Returns:
            List of (document, score) tuples
        """
        pass

class VectorStoreManagerInterface(ABC):
    """Interface for vector store manager."""

    @property
    @abstractmethod
    def current_vector_mode(self) -> Optional[str]:
        """Get the current vector mode."""
        pass

    @abstractmethod
    def get_vectorstore(self, profile: Optional[Dict[str, Any]] = None) -> Optional[VectorStoreInterface]:
        """
        Get the appropriate vectorstore based on the profile and mode.

        Args:
            profile: User profile containing mode and project path

        Returns:
            Vectorstore or None if not available
        """
        pass

    @abstractmethod
    def reset_vectorstore(self) -> None:
        """
        Reset the vectorstore, forcing it to be reloaded on the next get_vectorstore call.
        """
        pass

class MemoryStoreInterface(ABC):
    """Interface for memory store operations."""

    @abstractmethod
    def search_memory(self, query: str, k: int = 10) -> List[Any]:
        """
        Search for relevant memories.

        Args:
            query: The query string
            k: Number of results to return

        Returns:
            List of memory items
        """
        pass

class LLMBackendInterface(ABC):
    """Interface for LLM backend operations."""

    @abstractmethod
    def query(
        self,
        user_input: str,
        system_prompt: str,
        profile: Dict[str, Any],
        settings: Dict[str, Any],
        force_stream: bool = False
    ) -> Union[str, Generator[str, None, None]]:
        """
        Query the LLM backend.

        Args:
            user_input: The user's query
            system_prompt: The system prompt
            profile: User profile information
            settings: Application settings
            force_stream: Whether to force streaming mode

        Returns:
            The generated response or a generator for streaming responses
        """
        pass
