"""
Database access control module for Suhana.

This module provides decorators and utility functions for enforcing
access controls on database operations.
"""

import functools
import logging
from typing import Any, Callable, Dict, List, Optional, TypeVar, cast

from engine.security.access_control import Permission, check_permission

# Type variable for function return type
T = TypeVar('T')

logger = logging.getLogger(__name__)


def db_permission_required(permission: Permission) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for database methods that require a specific permission.

    Args:
        permission: Required permission

    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs) -> T:
            # Extract user_id from args or kwargs
            user_id = None
            if args and isinstance(args[0], str):
                user_id = args[0]
            elif 'user_id' in kwargs:
                user_id = kwargs['user_id']

            # If no user_id is provided, allow the operation (for system operations)
            if not user_id:
                return func(self, *args, **kwargs)

            # Check permission
            if not check_permission(user_id, permission):
                logger.warning(f"Access denied: User {user_id} does not have permission {permission}")
                raise PermissionError(f"User {user_id} does not have permission {permission}")

            return func(self, *args, **kwargs)
        return wrapper
    return decorator


def db_resource_permission_required(permission: Permission) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for database methods that require a specific permission for a resource.

    This decorator checks if the user has permission to access a resource owned by another user.
    If the user is the owner of the resource, it checks for the corresponding "own" permission.

    Args:
        permission: Required permission

    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs) -> T:
            # Extract user_id from args or kwargs
            user_id = None
            if args and isinstance(args[0], str):
                user_id = args[0]
            elif 'user_id' in kwargs:
                user_id = kwargs['user_id']

            # If no user_id is provided, allow the operation (for system operations)
            if not user_id:
                return func(self, *args, **kwargs)

            # Extract resource_owner_id from the database if available
            resource_owner_id = None

            # For conversation methods, extract conversation_id and check ownership
            conversation_id = None
            if len(args) > 1 and isinstance(args[1], str):
                conversation_id = args[1]
            elif 'conversation_id' in kwargs:
                conversation_id = kwargs['conversation_id']

            if conversation_id:
                # Try to get the conversation owner from the database
                try:
                    # This assumes the database adapter has a method to get conversation metadata
                    # We'll need to implement this method in the database adapters
                    conversation_meta = getattr(self, 'get_conversation_meta', None)
                    if conversation_meta:
                        meta = conversation_meta(conversation_id)
                        if meta:
                            resource_owner_id = meta.get('user_id')
                except Exception as e:
                    logger.error(f"Error getting conversation owner: {e}")

            # Check permission
            if not check_permission(user_id, permission, resource_owner_id):
                logger.warning(f"Access denied: User {user_id} does not have permission {permission} for resource owned by {resource_owner_id}")
                raise PermissionError(f"User {user_id} does not have permission {permission} for resource owned by {resource_owner_id}")

            return func(self, *args, **kwargs)
        return wrapper
    return decorator


def apply_database_access_controls(db_adapter: Any) -> None:
    """
    Apply access control decorators to database adapter methods.

    This function wraps the database adapter methods with the appropriate
    access control decorators based on the operation type.

    Args:
        db_adapter: Database adapter instance
    """
    # User methods
    if hasattr(db_adapter, 'list_users'):
        db_adapter.list_users = db_permission_required(Permission.VIEW_USERS)(db_adapter.list_users)

    if hasattr(db_adapter, 'get_user'):
        db_adapter.get_user = db_permission_required(Permission.VIEW_USERS)(db_adapter.get_user)

    if hasattr(db_adapter, 'create_user'):
        db_adapter.create_user = db_permission_required(Permission.MANAGE_USERS)(db_adapter.create_user)

    if hasattr(db_adapter, 'update_user'):
        db_adapter.update_user = db_permission_required(Permission.MANAGE_USERS)(db_adapter.update_user)

    if hasattr(db_adapter, 'delete_user'):
        db_adapter.delete_user = db_permission_required(Permission.MANAGE_USERS)(db_adapter.delete_user)

    # Settings methods
    if hasattr(db_adapter, 'get_settings'):
        original_get_settings = db_adapter.get_settings

        @functools.wraps(original_get_settings)
        def get_settings_with_permission(user_id: Optional[str] = None) -> Dict[str, Any]:
            # If getting global settings, require VIEW_GLOBAL_SETTINGS permission
            if user_id is None:
                if not check_permission(cast(str, user_id), Permission.VIEW_GLOBAL_SETTINGS):
                    logger.warning(f"Access denied: User {user_id} does not have permission to view global settings")
                    raise PermissionError(f"User {user_id} does not have permission to view global settings")

            return original_get_settings(user_id)

        db_adapter.get_settings = get_settings_with_permission

    if hasattr(db_adapter, 'save_settings'):
        original_save_settings = db_adapter.save_settings

        @functools.wraps(original_save_settings)
        def save_settings_with_permission(settings: Dict[str, Any], user_id: Optional[str] = None) -> bool:
            # If saving global settings, require MANAGE_GLOBAL_SETTINGS permission
            if user_id is None:
                if not check_permission(cast(str, user_id), Permission.MANAGE_GLOBAL_SETTINGS):
                    logger.warning(f"Access denied: User {user_id} does not have permission to manage global settings")
                    raise PermissionError(f"User {user_id} does not have permission to manage global settings")

            return original_save_settings(settings, user_id)

        db_adapter.save_settings = save_settings_with_permission

    # Conversation methods
    if hasattr(db_adapter, 'list_conversations'):
        db_adapter.list_conversations = db_resource_permission_required(Permission.VIEW_ALL_CONVERSATIONS)(db_adapter.list_conversations)

    if hasattr(db_adapter, 'list_conversation_meta'):
        db_adapter.list_conversation_meta = db_resource_permission_required(Permission.VIEW_ALL_CONVERSATIONS)(db_adapter.list_conversation_meta)

    if hasattr(db_adapter, 'load_conversation'):
        db_adapter.load_conversation = db_resource_permission_required(Permission.VIEW_ALL_CONVERSATIONS)(db_adapter.load_conversation)

    if hasattr(db_adapter, 'save_conversation'):
        db_adapter.save_conversation = db_resource_permission_required(Permission.EDIT_ALL_CONVERSATIONS)(db_adapter.save_conversation)

    if hasattr(db_adapter, 'create_new_conversation'):
        db_adapter.create_new_conversation = db_permission_required(Permission.CREATE_CONVERSATION)(db_adapter.create_new_conversation)

    if hasattr(db_adapter, 'delete_conversation'):
        db_adapter.delete_conversation = db_resource_permission_required(Permission.DELETE_ALL_CONVERSATIONS)(db_adapter.delete_conversation)

    # Memory methods
    if hasattr(db_adapter, 'add_memory_fact'):
        db_adapter.add_memory_fact = db_permission_required(Permission.CREATE_MEMORY)(db_adapter.add_memory_fact)

    if hasattr(db_adapter, 'search_memory'):
        original_search_memory = db_adapter.search_memory

        @functools.wraps(original_search_memory)
        def search_memory_with_permission(query: str, user_id: Optional[str] = None, include_shared: bool = True, k: int = 3) -> List[Dict[str, Any]]:
            # If searching all memory, require VIEW_ALL_MEMORY permission
            if user_id is None and not check_permission(cast(str, user_id), Permission.VIEW_ALL_MEMORY):
                logger.warning(f"Access denied: User {user_id} does not have permission to view all memory")
                raise PermissionError(f"User {user_id} does not have permission to view all memory")

            # If including shared memory, require VIEW_ALL_MEMORY permission
            if include_shared and not check_permission(cast(str, user_id), Permission.VIEW_ALL_MEMORY):
                logger.warning(f"Access denied: User {user_id} does not have permission to view shared memory")
                # Don't raise an error, just exclude shared memory
                include_shared = False

            return original_search_memory(query, user_id, include_shared, k)

        db_adapter.search_memory = search_memory_with_permission

    if hasattr(db_adapter, 'forget_memory'):
        original_forget_memory = db_adapter.forget_memory

        @functools.wraps(original_forget_memory)
        def forget_memory_with_permission(keyword: str, user_id: Optional[str] = None, forget_shared: bool = False) -> int:
            # If forgetting all memory, require DELETE_ALL_MEMORY permission
            if user_id is None and not check_permission(cast(str, user_id), Permission.DELETE_ALL_MEMORY):
                logger.warning(f"Access denied: User {user_id} does not have permission to delete all memory")
                raise PermissionError(f"User {user_id} does not have permission to delete all memory")

            # If forgetting shared memory, require DELETE_ALL_MEMORY permission
            if forget_shared and not check_permission(cast(str, user_id), Permission.DELETE_ALL_MEMORY):
                logger.warning(f"Access denied: User {user_id} does not have permission to delete shared memory")
                # Don't raise an error, just don't forget shared memory
                forget_shared = False

            return original_forget_memory(keyword, user_id, forget_shared)

        db_adapter.forget_memory = forget_memory_with_permission

    if hasattr(db_adapter, 'clear_memory'):
        original_clear_memory = db_adapter.clear_memory

        @functools.wraps(original_clear_memory)
        def clear_memory_with_permission(user_id: Optional[str] = None, clear_shared: bool = False) -> int:
            # If clearing all memory, require DELETE_ALL_MEMORY permission
            if user_id is None and not check_permission(cast(str, user_id), Permission.DELETE_ALL_MEMORY):
                logger.warning(f"Access denied: User {user_id} does not have permission to clear all memory")
                raise PermissionError(f"User {user_id} does not have permission to clear all memory")

            # If clearing shared memory, require DELETE_ALL_MEMORY permission
            if clear_shared and not check_permission(cast(str, user_id), Permission.DELETE_ALL_MEMORY):
                logger.warning(f"Access denied: User {user_id} does not have permission to clear shared memory")
                # Don't raise an error, just don't clear shared memory
                clear_shared = False

            return original_clear_memory(user_id, clear_shared)

        db_adapter.clear_memory = clear_memory_with_permission
