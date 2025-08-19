import json
import hashlib
import secrets
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta

from engine.settings_manager import SettingsManager
from engine.database.base import DatabaseAdapter
from engine.engine_config import get_database_adapter

logger = logging.getLogger(__name__)

class UserManager:
    """
    Manages user accounts, authentication, and profile data.

    This class handles:
    - User creation and authentication
    - Profile management for multiple users
    - User session management
    - User roles and permissions
    """

    # Default user roles and their permissions
    ROLES = {
        "admin": {
            "can_manage_users": True,
            "can_manage_settings": True,
            "can_access_all_conversations": True,
        },
        "user": {
            "can_manage_users": False,
            "can_manage_settings": False,
            "can_access_all_conversations": False,
        },
        "guest": {
            "can_manage_users": False,
            "can_manage_settings": False,
            "can_access_all_conversations": False,
        }
    }

    # Default profile template
    DEFAULT_PROFILE = {
        "name": "User",
        "created_at": None,  # Will be set at creation time
        "last_login": None,
        "role": "user",
        "avatar": None,  # Path to user avatar image or None for default
        "preferences": {
            "preferred_language": "English",
            "communication_style": "friendly, brief, couple of sentences max",
            "focus": "general",
            "theme": "system",  # system, light, dark
            "font_size": "medium",  # small, medium, large
            "notification_level": "all",  # all, mentions, none
            "timezone": "UTC",
            "date_format": "YYYY-MM-DD",
            "time_format": "24h"  # 12h, 24h
        },
        "personalization": {
            "interests": [],  # List of user interests
            "expertise": [],  # List of user expertise areas
            "learning_goals": [],  # List of learning goals
            "favorite_tools": [],  # List of favorite tools/features
            "custom_shortcuts": {}  # Custom keyboard shortcuts
        },
        "privacy": {
            "share_conversations": False,  # Whether to allow sharing conversations
            "allow_analytics": True,  # Whether to allow usage analytics
            "store_history": True  # Whether to store conversation history
        },
        "history": []
    }

    def __init__(self, base_dir: Optional[Path] = None, db_adapter: Optional[DatabaseAdapter] = None):
        """
        Initialize the UserManager.

        Args:
            base_dir: Base directory for user files. If None, uses the parent directory of the current file.
            db_adapter: Database adapter to use for storage. If None, uses the default adapter from engine_config.
        """
        self.base_dir = base_dir or Path(__file__).parent.parent
        self.users_dir = self.base_dir / "users"
        # Filesystem user directory is no longer used.

        # Initialize settings manager
        self.settings_manager = SettingsManager()

        # Initialize database adapter
        self.db = db_adapter or get_database_adapter()

        # Ensure database schema is initialized
        self.db.initialize_schema()

        # Active sessions (token -> user_id)
        self._sessions = {}

    def create_user(self, username: str, password: str, name: str = None, role: str = "user") -> Tuple[bool, str]:
        """
        Create a new user account.

        Args:
            username: Unique username for the new user
            password: Password for the new user
            name: Display name for the user (defaults to username if not provided)
            role: User role (admin or user)

        Returns:
            Tuple of (success, message)
        """
        # Validate username (alphanumeric and underscore only)
        if not username.isalnum() and not all(c.isalnum() or c == '_' for c in username):
            return False, "Username must contain only letters, numbers, and underscores"

        # Create user profile
        profile = self.DEFAULT_PROFILE.copy()
        profile["name"] = name or username
        profile["created_at"] = datetime.now().replace(tzinfo=None).isoformat()
        profile["role"] = role if role in self.ROLES else "user"
        # If creating a guest, ensure privacy defaults are more restrictive
        if profile["role"] == "guest":
            try:
                if "privacy" not in profile:
                    profile["privacy"] = self.DEFAULT_PROFILE["privacy"].copy()
                profile["privacy"]["store_history"] = False
                profile["privacy"]["allow_analytics"] = False
            except Exception:
                pass

        # Hash the password
        salt = secrets.token_hex(16)
        password_hash = self._hash_password(password, salt)

        # Create user data for database
        user_id = username  # Use username as user_id for compatibility
        profile["salt"] = salt
        user_data = {
            "id": user_id,
            "username": username,
            "password_hash": password_hash,
            "salt": salt,  # Store salt in the profile for password verification
            "created_at": datetime.now().replace(tzinfo=None).isoformat(),
            "profile": json.dumps(profile)
        }

        try:
            # Create user in database
            created_user_id = self.db.create_user(user_data)

            if not created_user_id:
                return False, f"Failed to create user '{username}' in database"

            # Register user role with access control manager
            try:
                from engine.security.access_control import get_access_control_manager
                acm = get_access_control_manager()
                acm.add_user(username, role)
            except Exception as e:
                logger.warning(f"Failed to register user '{username}' with access control: {e}")

            # Create user-specific settings (empty for now, will inherit from global)
            self.settings_manager.save_settings({"version": 1}, username)

            return True, f"User '{username}' created successfully"
        except Exception as e:
            logger.error(f"Error creating user '{username}': {e}")
            return False, f"Error creating user: {str(e)}"

    def authenticate(self, username: str, password: str) -> Tuple[bool, Optional[str]]:
        """
        Authenticate a user with username and password.

        Args:
            username: Username to authenticate
            password: Password to verify

        Returns:
            Tuple of (success, session_token, or None)
        """
        try:
            # Get user from database
            user = self.db.get_user(username)

            if not user:
                return False, None

            # Get salt from user data
            # Check if salt is in user data directly or in profile
            if "salt" in user:
                salt = user["salt"]
            elif user["profile"] and "salt" in user["profile"]:
                salt = user["profile"]["salt"]
            else:
                logger.error(f"Error authenticating user '{username}': No salt")
                return False, None

            # Verify password
            stored_hash = user["password_hash"]

            if self._hash_password(password, salt) == stored_hash:
                # Create session token
                token = self._generate_session_token()

                # Store session
                expiry = datetime.now() + timedelta(hours=24)
                self._sessions[token] = {
                    "user_id": username,
                    "expires": expiry.isoformat()
                }

                # Update last login
                self._update_last_login(username)

                return True, token

            logger.error(f"Error authenticating user '{username}': Password is incorrect")
            return False, None
        except Exception as e:
            logger.error(f"Error authenticating user '{username}': {e}")
            return False, None

    def validate_session(self, token: str) -> Optional[str]:
        """
        Validate a session token and return the associated user ID.

        Args:
            token: Session token to validate

        Returns:
            User ID if token is valid, None otherwise
        """
        if token not in self._sessions:
            return None

        session = self._sessions[token]
        expiry = datetime.fromisoformat(session["expires"])

        if datetime.now() > expiry:
            # Session expired
            del self._sessions[token]
            return None

        return session["user_id"]

    def logout(self, token: str) -> bool:
        """
        Invalidate a session token.

        Args:
            token: Session token to invalidate

        Returns:
            True if token was invalidated, False otherwise
        """
        if token in self._sessions:
            del self._sessions[token]
            return True
        return False

    def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a user's profile data.

        Args:
            user_id: User ID to get profile for

        Returns:
            Dictionary containing the user's profile, or None if user doesn't exist
        """
        try:
            # Get user from database
            user = self.db.get_user(user_id)

            if isinstance(user["profile"], str):
                return json.loads(user["profile"])
            else:
                return user["profile"]
        except Exception as e:
            logger.error(f"Error loading profile for user '{user_id}': {e}")
            return None

    def save_profile(self, user_id: str, profile: Dict[str, Any]) -> bool:
        """
        Save a user's profile data.

        Args:
            user_id: User ID to save profile for
            profile: Dictionary containing the user's profile data

        Returns:
            True if profile was saved successfully, False otherwise
        """
        try:
            # Ensure all required sections exist with defaults if missing
            for section in ["preferences", "personalization", "privacy"]:
                if section not in profile:
                    profile[section] = self.DEFAULT_PROFILE[section]

            return self.db.update_user(user_id, {
                "profile": json.dumps(profile)
            })
        except Exception as e:
            logger.error(f"Error saving profile for user '{user_id}': {e}")
            return False

    def list_users(self) -> List[Dict[str, Any]]:
        """
        List all users in the system.

        Returns:
            List of dictionaries containing user information
        """
        try:
            # Get users from database
            db_users = self.db.list_users()

            # Format user data
            users = []
            for user in db_users:
                profile = json.loads(user["profile"])

                # Determine role (might be in profile or directly in user data)
                role = "user"  # Default role
                if "role" in profile:
                    role = profile["role"]

                users.append({
                    "user_id": user["id"],
                    "name": profile.get("name", user["username"]),
                    "role": role,
                    "created_at": user.get("created_at") or profile.get("created_at"),
                    "last_login": user.get("last_login") or profile.get("last_login")
                })

            return users
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            return []

    def delete_user(self, user_id: str) -> bool:
        """
        Delete a user account.

        Args:
            user_id: User ID to delete

        Returns:
            True if user was deleted successfully, False otherwise
        """
        try:
            # Delete user from database
            success = self.db.delete_user(user_id)

            if not success:
                return False


            # Remove any active sessions for this user
            for token, session in list(self._sessions.items()):
                if session["user_id"] == user_id:
                    del self._sessions[token]

            return True
        except Exception as e:
            logger.error(f"Error deleting user '{user_id}': {e}")
            return False

    def change_password(self, user_id: str, current_password: str, new_password: str) -> Tuple[bool, str]:
        """
        Change a user's password.

        Args:
            user_id: User ID to change password for
            current_password: Current password for verification
            new_password: New password to set

        Returns:
            Tuple of (success, message)
        """
        try:
            # Get user from database
            user = self.db.get_user(user_id)

            if not user:
                return False, "User not found"

            # Get salt from user data
            # Check if salt is in user data directly or in profile
            if "salt" in user:
                salt = user["salt"]
            else:
                return False, "Authentication data not found"

            # Verify current password
            stored_hash = user["password_hash"]

            if self._hash_password(current_password, salt) != stored_hash:
                return False, "Current password is incorrect"

            # Generate new salt and hash
            new_salt = secrets.token_hex(16)
            new_hash = self._hash_password(new_password, new_salt)

            # Update user in database
            success = self.db.update_user(user_id, {
                "password_hash": new_hash,
                "salt": new_salt
            })

            if not success:
                return False, "Failed to update password in database"

            return True, "Password changed successfully"
        except Exception as e:
            logger.error(f"Error changing password for user '{user_id}': {e}")
            return False, f"Error changing password: {str(e)}"

    def _hash_password(self, password: str, salt: str) -> str:
        """
        Hash a password with the given salt.

        Args:
            password: Password to hash
            salt: Salt to use for hashing

        Returns:
            Hashed password
        """
        # Combine password and salt
        salted = password + salt

        # Hash with SHA-256
        return hashlib.sha256(salted.encode()).hexdigest()

    def _generate_session_token(self) -> str:
        """
        Generate a random session token.

        Returns:
            Random session token
        """
        return secrets.token_hex(32)

    def _update_last_login(self, user_id: str) -> None:
        """
        Update the last login timestamp for a user.

        Args:
            user_id: User ID to update
        """
        try:
            # Get user from database
            user = self.db.get_user(user_id)

            if user:
                # Update last_login in database
                self.db.update_user(user_id, {
                    "last_login": datetime.now().replace(tzinfo=None).isoformat()
                })

                # Also update profile for consistency
                profile = user["profile"] if isinstance(user["profile"], dict) else json.loads(user["profile"])

                profile["last_login"] = datetime.now().replace(tzinfo=None).isoformat()

                self.db.update_user(user_id, {
                    "profile": json.dumps(profile)
                })
        except Exception as e:
            logger.error(f"Error updating last login for user '{user_id}': {e}")

    def set_avatar(self, user_id: str, avatar_path: Optional[str]) -> bool:
        """
        Set a user's avatar.

        Args:
            user_id: User ID to set avatar for
            avatar_path: Path to avatar image file, or None to use default

        Returns:
            True if avatar was set successfully, False otherwise
        """
        profile = self.get_profile(user_id)

        if not profile:
            return False

        profile["avatar"] = avatar_path
        return self.save_profile(user_id, profile)

    def get_avatar(self, user_id: str) -> Optional[str]:
        """
        Get a user's avatar path.

        Args:
            user_id: User ID to get avatar for

        Returns:
            Path to avatar image file, or None if not set or user doesn't exist
        """
        profile = self.get_profile(user_id)

        if not profile:
            return None

        return profile.get("avatar")

    def _ensure_profile_section(self, profile: Dict[str, Any], section: str) -> None:
        """Ensure a section exists in the given profile."""
        if section not in profile:
            profile[section] = self.DEFAULT_PROFILE[section].copy()


    def _update_profile_section(self, user_id: str, section: str, updates: Dict[str, Any]) -> bool:
        """Generic method to update a specific section of a user's profile."""
        profile = self.get_profile(user_id)
        if not profile:
            return False
        self._ensure_profile_section(profile, section)
        for key, value in updates.items():
            profile[section][key] = value
        return self.save_profile(user_id, profile)

    def update_preferences(self, user_id: str, preferences: Dict[str, Any]) -> bool:
        """Update a user's preferences."""
        return self._update_profile_section(user_id, "preferences", preferences)

    def get_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get a user's preferences."""
        profile = self.get_profile(user_id)
        if not profile:
            return {}
        return profile.get("preferences", {})

    def update_personalization(self, user_id: str, personalization: Dict[str, Any]) -> bool:
        """Update a user's personalization settings."""
        return self._update_profile_section(user_id, "personalization", personalization)

    def get_personalization(self, user_id: str) -> Dict[str, Any]:
        """Get a user's personalization settings."""
        profile = self.get_profile(user_id)
        if not profile:
            return {}
        return profile.get("personalization", {})

    def update_privacy_settings(self, user_id: str, privacy_settings: Dict[str, Any]) -> bool:
        """Update a user's privacy settings."""
        return self._update_profile_section(user_id, "privacy", privacy_settings)

    def get_privacy_settings(self, user_id: str) -> Dict[str, Any]:
        """Get a user's privacy settings."""
        profile = self.get_profile(user_id)
        if not profile:
            return {}
        return profile.get("privacy", {})

    def add_interest(self, user_id: str, interest: str) -> bool:
        """
        Add an interest to a user's profile.

        Args:
            user_id: User ID to add interest for
            interest: Interest to add

        Returns:
            True if interest was added successfully, False otherwise
        """
        profile = self.get_profile(user_id)

        if not profile:
            return False

        # Ensure personalization section exists
        if "personalization" not in profile:
            profile["personalization"] = self.DEFAULT_PROFILE["personalization"]

        # Ensure interests list exists
        if "interests" not in profile["personalization"]:
            profile["personalization"]["interests"] = []

        # Add interest if not already present
        if interest not in profile["personalization"]["interests"]:
            profile["personalization"]["interests"].append(interest)

        return self.save_profile(user_id, profile)

    def remove_interest(self, user_id: str, interest: str) -> bool:
        """
        Remove an interest from a user's profile.

        Args:
            user_id: User ID to remove interest for
            interest: Interest to remove

        Returns:
            True if interest was removed successfully, False otherwise
        """
        profile = self.get_profile(user_id)

        if not profile:
            return False

        # Check if personalization and interests exist
        if ("personalization" not in profile or
            "interests" not in profile["personalization"]):
            return True  # Nothing to remove

        # Remove interest if present
        if interest in profile["personalization"]["interests"]:
            profile["personalization"]["interests"].remove(interest)

        return self.save_profile(user_id, profile)
