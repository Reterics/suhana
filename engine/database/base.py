"""
Base database adapter for Suhana.

This module defines the base interface for all database adapters.
"""

import abc
import logging
from typing import Dict, Any, List, Optional, Tuple, Type
from pathlib import Path

from engine.security.database_access import apply_database_access_controls

logger = logging.getLogger(__name__)


class DatabaseAdapter(abc.ABC):
    """
    Abstract base class for database adapters.

    All database adapters must implement these methods to provide
    consistent storage capabilities across different database backends.
    """

    def apply_access_controls(self) -> None:
        """
        Apply access controls to the database adapter methods.

        This method wraps the adapter methods with access control decorators
        to enforce permission checks for all database operations.
        """
        apply_database_access_controls(self)

    @abc.abstractmethod
    def __init__(self, connection_string: str, **kwargs):
        """
        Initialize the database adapter.

        Args:
            connection_string: Connection string for the database
            **kwargs: Additional connection parameters
        """
        pass

    @abc.abstractmethod
    def connect(self) -> bool:
        """
        Connect to the database.

        Returns:
            bool: True if connection successful, False otherwise
        """
        pass

    @abc.abstractmethod
    def disconnect(self) -> bool:
        """
        Disconnect from the database.

        Returns:
            bool: True if disconnection successful, False otherwise
        """
        pass

    @abc.abstractmethod
    def initialize_schema(self) -> bool:
        """
        Initialize the database schema.

        Creates all necessary tables, indexes, and constraints.

        Returns:
            bool: True if initialization successful, False otherwise
        """
        pass

    @abc.abstractmethod
    def migrate_from_files(self, base_dir: Path) -> Tuple[int, int, int]:
        """
        Migrate data from file-based storage to database.

        Args:
            base_dir: Base directory containing file-based storage

        Returns:
            Tuple[int, int, int]: Count of migrated (users, conversations, settings)
        """
        pass

    # User methods

    @abc.abstractmethod
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user profile by ID.

        Args:
            user_id: User ID

        Returns:
            Optional[Dict[str, Any]]: User profile or None if not found
        """
        pass

    @abc.abstractmethod
    def list_users(self) -> List[Dict[str, Any]]:
        """
        List all users.

        Returns:
            List[Dict[str, Any]]: List of user profiles
        """
        pass

    @abc.abstractmethod
    def create_user(self, user_data: Dict[str, Any]) -> str:
        """
        Create a new user.

        Args:
            user_data: User profile data

        Returns:
            str: ID of the created user
        """
        pass

    @abc.abstractmethod
    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> bool:
        """
        Update user profile.

        Args:
            user_id: User ID
            user_data: Updated user profile data

        Returns:
            bool: True if update successful, False otherwise
        """
        pass

    @abc.abstractmethod
    def delete_user(self, user_id: str) -> bool:
        """
        Delete user.

        Args:
            user_id: User ID

        Returns:
            bool: True if deletion successful, False otherwise
        """
        pass

    # Settings methods

    @abc.abstractmethod
    def get_settings(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get settings.

        Args:
            user_id: User ID for user-specific settings, None for global settings

        Returns:
            Dict[str, Any]: Settings
        """
        pass

    @abc.abstractmethod
    def save_settings(self, settings: Dict[str, Any], user_id: Optional[str] = None) -> bool:
        """
        Save settings.

        Args:
            settings: Settings data
            user_id: User ID for user-specific settings, None for global settings

        Returns:
            bool: True if save successful, False otherwise
        """
        pass

    # Conversation methods

    @abc.abstractmethod
    def list_conversations(self, user_id: str, category: Optional[str] = None) -> List[str]:
        """
        List conversations.

        Args:
            user_id: User ID
            category: Category name (optional)

        Returns:
            List[str]: List of conversation IDs
        """
        pass

    @abc.abstractmethod
    def list_conversation_meta(self, user_id: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List conversation metadata.

        Args:
            user_id: User ID
            category: Category name (optional)

        Returns:
            List[Dict[str, Any]]: List of conversation metadata
        """
        pass

    @abc.abstractmethod
    def load_conversation(self, user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Load conversation.

        Args:
            user_id: User ID
            conversation_id: Conversation ID

        Returns:
            Optional[Dict[str, Any]]: Conversation data or None if not found
        """
        pass

    @abc.abstractmethod
    def save_conversation(self, user_id: str, conversation_id: str, data: Dict[str, Any]) -> bool:
        """
        Save conversation.

        Args:
            user_id: User ID
            conversation_id: Conversation ID
            data: Conversation data

        Returns:
            bool: True if save successful, False otherwise
        """
        pass

    @abc.abstractmethod
    def create_new_conversation(self, user_id: str, title: Optional[str] = None, category: Optional[str] = None) -> str:
        """
        Create a new conversation.

        Args:
            user_id: User ID
            title: Conversation title (optional)
            category: Category name (optional)

        Returns:
            str: ID of the created conversation
        """
        pass

    @abc.abstractmethod
    def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """
        Delete conversation.

        Args:
            user_id: User ID
            conversation_id: Conversation ID

        Returns:
            bool: True if deletion successful, False otherwise
        """
        pass

    @abc.abstractmethod
    def list_categories(self, user_id: str) -> List[str]:
        """
        List categories.

        Args:
            user_id: User ID

        Returns:
            List[str]: List of category names
        """
        pass

    @abc.abstractmethod
    def create_category(self, user_id: str, category: str) -> bool:
        """
        Create a new category.

        Args:
            user_id: User ID
            category: Category name

        Returns:
            bool: True if creation successful, False otherwise
        """
        pass

    @abc.abstractmethod
    def move_conversation_to_category(self, user_id: str, conversation_id: str, category: str) -> bool:
        """
        Move conversation to category.

        Args:
            user_id: User ID
            conversation_id: Conversation ID
            category: Target category name

        Returns:
            bool: True if move successful, False otherwise
        """
        pass

    # Memory methods

    @abc.abstractmethod
    def add_memory_fact(self, user_id: Optional[str], text: str, private: bool = True) -> bool:
        """
        Add memory fact.

        Args:
            user_id: User ID (None for shared memory)
            text: Memory fact text
            private: Whether the memory is private to the user

        Returns:
            bool: True if addition successful, False otherwise
        """
        pass

    @abc.abstractmethod
    def search_memory(self, query: str, user_id: Optional[str] = None, include_shared: bool = True, k: int = 3) -> List[Dict[str, Any]]:
        """
        Search memory.

        Args:
            query: Search query
            user_id: User ID (None for shared memory only)
            include_shared: Whether to include shared memory in search
            k: Number of results to return

        Returns:
            List[Dict[str, Any]]: List of memory facts
        """
        pass

    @abc.abstractmethod
    def forget_memory(self, keyword: str, user_id: Optional[str] = None, forget_shared: bool = False) -> int:
        """
        Forget memory facts containing keyword.

        Args:
            keyword: Keyword to search for
            user_id: User ID (None for shared memory only)
            forget_shared: Whether to forget shared memory

        Returns:
            int: Number of memory facts forgotten
        """
        pass

    @abc.abstractmethod
    def clear_memory(self, user_id: Optional[str] = None, clear_shared: bool = False) -> int:
        """
        Clear memory.

        Args:
            user_id: User ID (None for shared memory only)
            clear_shared: Whether to clear shared memory

        Returns:
            int: Number of memory facts cleared
        """
        pass

    # API Key Management

    @abc.abstractmethod
    def get_api_key(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get API key information.

        Args:
            key: API key

        Returns:
            Dict containing API key information or None if not found
        """
        pass

    @abc.abstractmethod
    def get_user_api_keys(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all API keys for a user.

        Args:
            user_id: User ID

        Returns:
            List of dictionaries containing API key information
        """
        pass

    @abc.abstractmethod
    def create_api_key(self, user_id: str, key: str, name: Optional[str] = None,
                      rate_limit: int = 60, permissions: Optional[List[str]] = None) -> bool:
        """
        Create a new API key.

        Args:
            user_id: User ID
            key: API key
            name: Name for the API key
            rate_limit: Rate limit in requests per minute
            permissions: List of permissions

        Returns:
            bool: True if successful, False otherwise
        """
        pass

    @abc.abstractmethod
    def update_api_key_usage(self, key: str) -> bool:
        """
        Update API key usage statistics.

        Args:
            key: API key

        Returns:
            bool: True if successful, False otherwise
        """
        pass

    @abc.abstractmethod
    def revoke_api_key(self, key: str) -> bool:
        """
        Revoke an API key.

        Args:
            key: API key

        Returns:
            bool: True if successful, False otherwise
        """
        pass

    @abc.abstractmethod
    def get_api_key_usage_stats(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get API key usage statistics.

        Args:
            user_id: User ID (if None, gets stats for all users)

        Returns:
            List of dictionaries containing API key usage statistics
        """
        pass
