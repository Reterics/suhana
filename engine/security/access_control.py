"""
Access control module for Suhana.

This module provides functions for managing user roles and permissions.
"""

import logging
from enum import Enum, auto
from typing import Dict, Optional, Set, Union


class Permission(Enum):
    """
    Enumeration of available permissions.
    """
    # User management permissions
    MANAGE_USERS = auto()  # Create, update, delete users
    VIEW_USERS = auto()    # View user profiles

    # Settings permissions
    MANAGE_GLOBAL_SETTINGS = auto()  # Modify global settings
    VIEW_GLOBAL_SETTINGS = auto()    # View global settings

    # Conversation permissions
    CREATE_CONVERSATION = auto()     # Create new conversations
    VIEW_OWN_CONVERSATIONS = auto()  # View own conversations
    VIEW_ALL_CONVERSATIONS = auto()  # View all users' conversations
    EDIT_OWN_CONVERSATIONS = auto()  # Edit own conversations
    EDIT_ALL_CONVERSATIONS = auto()  # Edit all users' conversations
    DELETE_OWN_CONVERSATIONS = auto() # Delete own conversations
    DELETE_ALL_CONVERSATIONS = auto() # Delete all users' conversations

    # Memory permissions
    CREATE_MEMORY = auto()           # Create memory facts
    VIEW_OWN_MEMORY = auto()         # View own memory
    VIEW_ALL_MEMORY = auto()         # View all users' memory
    EDIT_OWN_MEMORY = auto()         # Edit own memory
    EDIT_ALL_MEMORY = auto()         # Edit all users' memory
    DELETE_OWN_MEMORY = auto()       # Delete own memory
    DELETE_ALL_MEMORY = auto()       # Delete all users' memory

    # Backup permissions
    CREATE_BACKUP = auto()           # Create backups
    RESTORE_BACKUP = auto()          # Restore from backups

    # Security permissions
    MANAGE_ENCRYPTION = auto()       # Manage encryption keys
    MANAGE_PERMISSIONS = auto()      # Manage user permissions


class Role(Enum):
    """
    Enumeration of predefined roles.
    """
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


# Default permissions for predefined roles
DEFAULT_ROLE_PERMISSIONS = {
    Role.ADMIN: {
        Permission.MANAGE_USERS,
        Permission.VIEW_USERS,
        Permission.MANAGE_GLOBAL_SETTINGS,
        Permission.VIEW_GLOBAL_SETTINGS,
        Permission.CREATE_CONVERSATION,
        Permission.VIEW_OWN_CONVERSATIONS,
        Permission.VIEW_ALL_CONVERSATIONS,
        Permission.EDIT_OWN_CONVERSATIONS,
        Permission.EDIT_ALL_CONVERSATIONS,
        Permission.DELETE_OWN_CONVERSATIONS,
        Permission.DELETE_ALL_CONVERSATIONS,
        Permission.CREATE_MEMORY,
        Permission.VIEW_OWN_MEMORY,
        Permission.VIEW_ALL_MEMORY,
        Permission.EDIT_OWN_MEMORY,
        Permission.EDIT_ALL_MEMORY,
        Permission.DELETE_OWN_MEMORY,
        Permission.DELETE_ALL_MEMORY,
        Permission.CREATE_BACKUP,
        Permission.RESTORE_BACKUP,
        Permission.MANAGE_ENCRYPTION,
        Permission.MANAGE_PERMISSIONS
    },
    Role.USER: {
        Permission.VIEW_USERS,
        Permission.VIEW_GLOBAL_SETTINGS,
        Permission.CREATE_CONVERSATION,
        Permission.VIEW_OWN_CONVERSATIONS,
        Permission.EDIT_OWN_CONVERSATIONS,
        Permission.DELETE_OWN_CONVERSATIONS,
        Permission.CREATE_MEMORY,
        Permission.VIEW_OWN_MEMORY,
        Permission.EDIT_OWN_MEMORY,
        Permission.DELETE_OWN_MEMORY
    },
    Role.GUEST: {
        Permission.VIEW_GLOBAL_SETTINGS,
        Permission.CREATE_CONVERSATION,
        Permission.VIEW_OWN_CONVERSATIONS,
        Permission.EDIT_OWN_CONVERSATIONS,
        Permission.CREATE_MEMORY,
        Permission.VIEW_OWN_MEMORY
    }
}


class AccessControlManager:
    """
    Manages user roles and permissions.
    """

    def __init__(self):
        """
        Initialize the access control manager.
        """
        self.logger = logging.getLogger(__name__)
        self.user_roles: Dict[str, Role] = {}
        self.user_permissions: Dict[str, Set[Permission]] = {}
        self.custom_roles: Dict[str, Set[Permission]] = {}

    def add_user(self, user_id: str, role: Union[Role, str] = Role.USER) -> None:
        """
        Add a user with the specified role.

        Args:
            user_id: User ID
            role: User role (default: Role.USER)
        """
        try:
            # Convert string role to Role enum if needed
            if isinstance(role, str):
                try:
                    role = Role(role)
                except ValueError:
                    # Check if it's a custom role
                    if role in self.custom_roles:
                        self.user_roles[user_id] = role
                        self.user_permissions[user_id] = self.custom_roles[role].copy()
                        return
                    else:
                        self.logger.warning(f"Invalid role: {role}, using default role USER")
                        role = Role.USER

            # Assign role and default permissions
            self.user_roles[user_id] = role
            self.user_permissions[user_id] = DEFAULT_ROLE_PERMISSIONS[role].copy()
        except Exception as e:
            self.logger.error(f"Error adding user {user_id} with role {role}: {e}")

    def remove_user(self, user_id: str) -> None:
        """
        Remove a user.

        Args:
            user_id: User ID
        """
        try:
            if user_id in self.user_roles:
                del self.user_roles[user_id]

            if user_id in self.user_permissions:
                del self.user_permissions[user_id]
        except Exception as e:
            self.logger.error(f"Error removing user {user_id}: {e}")

    def get_user_role(self, user_id: str) -> Optional[Union[Role, str]]:
        """
        Get the role of a user.

        Args:
            user_id: User ID

        Returns:
            Optional[Union[Role, str]]: User role or None if user not found
        """
        return self.user_roles.get(user_id)

    def set_user_role(self, user_id: str, role: Union[Role, str]) -> None:
        """
        Set the role of a user.

        Args:
            user_id: User ID
            role: User role
        """
        try:
            # Convert string role to Role enum if needed
            if isinstance(role, str):
                try:
                    role = Role(role)
                except ValueError:
                    # Check if it's a custom role
                    if role in self.custom_roles:
                        self.user_roles[user_id] = role
                        self.user_permissions[user_id] = self.custom_roles[role].copy()
                        return
                    else:
                        self.logger.warning(f"Invalid role: {role}, using default role USER")
                        role = Role.USER

            # Assign role and default permissions
            self.user_roles[user_id] = role
            self.user_permissions[user_id] = DEFAULT_ROLE_PERMISSIONS[role].copy()
        except Exception as e:
            self.logger.error(f"Error setting role {role} for user {user_id}: {e}")

    def create_custom_role(self, role_name: str, permissions: Set[Permission]) -> None:
        """
        Create a custom role with the specified permissions.

        Args:
            role_name: Name of the custom role
            permissions: Set of permissions for the role
        """
        try:
            self.custom_roles[role_name] = permissions.copy()
        except Exception as e:
            self.logger.error(f"Error creating custom role {role_name}: {e}")

    def delete_custom_role(self, role_name: str) -> None:
        """
        Delete a custom role.

        Args:
            role_name: Name of the custom role
        """
        try:
            if role_name in self.custom_roles:
                del self.custom_roles[role_name]

                # Update users with this role to the default USER role
                for user_id, role in self.user_roles.items():
                    if role == role_name:
                        self.set_user_role(user_id, Role.USER)
        except Exception as e:
            self.logger.error(f"Error deleting custom role {role_name}: {e}")

    def get_user_permissions(self, user_id: str) -> Set[Permission]:
        """
        Get the permissions of a user. If the user has not been registered with
        the access control manager yet, assign the default USER role on the fly.

        Args:
            user_id: User ID

        Returns:
            Set[Permission]: Set of user permissions
        """
        # Auto-register unknown users with default USER role to ensure sane defaults
        if user_id not in self.user_permissions:
            try:
                self.user_roles[user_id] = Role.USER
                self.user_permissions[user_id] = DEFAULT_ROLE_PERMISSIONS[Role.USER].copy()
            except Exception as e:
                self.logger.error(f"Error auto-registering user {user_id} with default permissions: {e}")
                return set()
        return self.user_permissions.get(user_id, set())

    def add_user_permission(self, user_id: str, permission: Permission) -> None:
        """
        Add a permission to a user.

        Args:
            user_id: User ID
            permission: Permission to add
        """
        try:
            if user_id not in self.user_permissions:
                self.user_permissions[user_id] = set()

            self.user_permissions[user_id].add(permission)
        except Exception as e:
            self.logger.error(f"Error adding permission {permission} to user {user_id}: {e}")

    def remove_user_permission(self, user_id: str, permission: Permission) -> None:
        """
        Remove a permission from a user.

        Args:
            user_id: User ID
            permission: Permission to remove
        """
        try:
            if user_id in self.user_permissions:
                self.user_permissions[user_id].discard(permission)
        except Exception as e:
            self.logger.error(f"Error removing permission {permission} from user {user_id}: {e}")

    def has_permission(self, user_id: str, permission: Permission) -> bool:
        """
        Check if a user has a specific permission.

        Args:
            user_id: User ID
            permission: Permission to check

        Returns:
            bool: True if user has the permission, False otherwise
        """
        try:
            return permission in self.get_user_permissions(user_id)
        except Exception as e:
            self.logger.error(f"Error checking permission {permission} for user {user_id}: {e}")
            return False

    def check_permission(self, user_id: str, permission: Permission, resource_owner_id: Optional[str] = None) -> bool:
        """
        Check if a user has permission to access a resource.

        Args:
            user_id: User ID
            permission: Permission to check
            resource_owner_id: ID of the resource owner (optional)

        Returns:
            bool: True if user has permission, False otherwise
        """
        try:
            # If user is the resource owner, check for "own" permissions
            if resource_owner_id and user_id == resource_owner_id:
                # Map "all" permissions to corresponding "own" permissions
                own_permission_map = {
                    Permission.VIEW_ALL_CONVERSATIONS: Permission.VIEW_OWN_CONVERSATIONS,
                    Permission.EDIT_ALL_CONVERSATIONS: Permission.EDIT_OWN_CONVERSATIONS,
                    Permission.DELETE_ALL_CONVERSATIONS: Permission.DELETE_OWN_CONVERSATIONS,
                    Permission.VIEW_ALL_MEMORY: Permission.VIEW_OWN_MEMORY,
                    Permission.EDIT_ALL_MEMORY: Permission.EDIT_OWN_MEMORY,
                    Permission.DELETE_ALL_MEMORY: Permission.DELETE_OWN_MEMORY
                }

                # If checking for an "all" permission, also check the corresponding "own" permission
                if permission in own_permission_map:
                    return self.has_permission(user_id, permission) or self.has_permission(user_id, own_permission_map[permission])

            # Otherwise, check the exact permission
            return self.has_permission(user_id, permission)
        except Exception as e:
            self.logger.error(f"Error checking permission {permission} for user {user_id} on resource owned by {resource_owner_id}: {e}")
            return False

    def save_to_database(self, db_adapter) -> bool:
        """
        Save access control data to the database.

        Args:
            db_adapter: Database adapter

        Returns:
            bool: True if save successful, False otherwise
        """
        try:
            # Convert data to serializable format
            data = {
                "user_roles": {user_id: role.value if isinstance(role, Role) else role for user_id, role in self.user_roles.items()},
                "user_permissions": {user_id: [perm.name for perm in perms] for user_id, perms in self.user_permissions.items()},
                "custom_roles": {role: [perm.name for perm in perms] for role, perms in self.custom_roles.items()}
            }

            # Save to database
            return db_adapter.save_access_control(data)
        except Exception as e:
            self.logger.error(f"Error saving access control data to database: {e}")
            return False

    def load_from_database(self, db_adapter) -> bool:
        """
        Load access control data from the database.

        Args:
            db_adapter: Database adapter

        Returns:
            bool: True if load successful, False otherwise
        """
        try:
            # Load from database
            data = db_adapter.load_access_control()

            if not data:
                return False

            # Convert data from serializable format
            self.user_roles = {}
            for user_id, role in data.get("user_roles", {}).items():
                try:
                    self.user_roles[user_id] = Role(role)
                except ValueError:
                    self.user_roles[user_id] = role

            self.user_permissions = {}
            for user_id, perms in data.get("user_permissions", {}).items():
                self.user_permissions[user_id] = {Permission[perm] for perm in perms}

            self.custom_roles = {}
            for role, perms in data.get("custom_roles", {}).items():
                self.custom_roles[role] = {Permission[perm] for perm in perms}

            return True
        except Exception as e:
            self.logger.error(f"Error loading access control data from database: {e}")
            return False


# Singleton instance
_access_control_manager = None


def get_access_control_manager() -> AccessControlManager:
    """
    Get the singleton instance of the access control manager.

    Returns:
        AccessControlManager: Access control manager instance
    """
    global _access_control_manager
    if _access_control_manager is None:
        _access_control_manager = AccessControlManager()
    return _access_control_manager


def check_permission(user_id: str, permission: Permission, resource_owner_id: Optional[str] = None) -> bool:
    """
    Check if a user has permission to access a resource.

    Args:
        user_id: User ID
        permission: Permission to check
        resource_owner_id: ID of the resource owner (optional)

    Returns:
        bool: True if user has permission, False otherwise
    """
    return get_access_control_manager().check_permission(user_id, permission, resource_owner_id)


def permission_required(permission: Permission):
    """
    Decorator for functions that require a specific permission.

    Args:
        permission: Required permission

    Returns:
        Decorated function
    """
    def decorator(func):
        def wrapper(user_id, *args, **kwargs):
            if not check_permission(user_id, permission):
                raise PermissionError(f"User {user_id} does not have permission {permission}")
            return func(user_id, *args, **kwargs)
        return wrapper
    return decorator


def resource_permission_required(permission: Permission, resource_owner_id_arg: str = "resource_owner_id"):
    """
    Decorator for functions that require a specific permission for a resource.

    Args:
        permission: Required permission
        resource_owner_id_arg: Name of the argument containing the resource owner ID

    Returns:
        Decorated function
    """
    def decorator(func):
        def wrapper(user_id, *args, **kwargs):
            resource_owner_id = kwargs.get(resource_owner_id_arg)
            if not check_permission(user_id, permission, resource_owner_id):
                raise PermissionError(f"User {user_id} does not have permission {permission} for resource owned by {resource_owner_id}")
            return func(user_id, *args, **kwargs)
        return wrapper
    return decorator
