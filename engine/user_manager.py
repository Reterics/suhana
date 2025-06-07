import json
import os
import uuid
import hashlib
import secrets
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta

from engine.settings_manager import SettingsManager

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

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize the UserManager.

        Args:
            base_dir: Base directory for user files. If None, uses the parent directory of the current file.
        """
        self.base_dir = base_dir or Path(__file__).parent.parent
        self.users_dir = self.base_dir / "users"
        self.users_dir.mkdir(exist_ok=True)

        # Initialize settings manager
        self.settings_manager = SettingsManager(base_dir=self.base_dir)

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

        # Check if username already exists
        user_dir = self.users_dir / username
        if user_dir.exists():
            return False, f"User '{username}' already exists"

        # Create user directory
        user_dir.mkdir(exist_ok=True)

        # Create user profile
        profile = self.DEFAULT_PROFILE.copy()
        profile["name"] = name or username
        profile["created_at"] = datetime.now().isoformat()
        profile["role"] = role if role in self.ROLES else "user"

        # Hash the password
        salt = secrets.token_hex(16)
        password_hash = self._hash_password(password, salt)

        # Create auth file
        auth_data = {
            "username": username,
            "password_hash": password_hash,
            "salt": salt,
            "role": role
        }

        try:
            # Save auth data
            auth_path = user_dir / "auth.json"
            with open(auth_path, "w", encoding="utf-8") as f:
                json.dump(auth_data, f, indent=2)

            # Save profile
            profile_path = user_dir / "profile.json"
            with open(profile_path, "w", encoding="utf-8") as f:
                json.dump(profile, f, indent=2)

            # Create user-specific settings (empty for now, will inherit from global)
            self.settings_manager.save_settings({"version": 1}, username)

            # Create conversations directory
            conversations_dir = user_dir / "conversations"
            conversations_dir.mkdir(exist_ok=True)

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
            Tuple of (success, session_token or None)
        """
        user_dir = self.users_dir / username
        auth_path = user_dir / "auth.json"

        if not auth_path.exists():
            return False, None

        try:
            # Load auth data
            with open(auth_path, "r", encoding="utf-8") as f:
                auth_data = json.load(f)

            # Verify password
            salt = auth_data["salt"]
            stored_hash = auth_data["password_hash"]

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
        profile_path = self.users_dir / user_id / "profile.json"

        if not profile_path.exists():
            return None

        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                return json.load(f)
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
        profile_path = self.users_dir / user_id / "profile.json"

        try:
            # Ensure all required sections exist with defaults if missing
            for section in ["preferences", "personalization", "privacy"]:
                if section not in profile:
                    profile[section] = self.DEFAULT_PROFILE[section]

            with open(profile_path, "w", encoding="utf-8") as f:
                json.dump(profile, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving profile for user '{user_id}': {e}")
            return False

    def list_users(self) -> List[Dict[str, Any]]:
        """
        List all users in the system.

        Returns:
            List of dictionaries containing user information
        """
        users = []

        for user_dir in self.users_dir.iterdir():
            if not user_dir.is_dir():
                continue

            profile_path = user_dir / "profile.json"
            auth_path = user_dir / "auth.json"

            if not profile_path.exists() or not auth_path.exists():
                continue

            try:
                with open(profile_path, "r", encoding="utf-8") as f:
                    profile = json.load(f)

                with open(auth_path, "r", encoding="utf-8") as f:
                    auth_data = json.load(f)

                users.append({
                    "user_id": user_dir.name,
                    "name": profile.get("name", user_dir.name),
                    "role": auth_data.get("role", "user"),
                    "created_at": profile.get("created_at"),
                    "last_login": profile.get("last_login")
                })
            except Exception as e:
                logger.error(f"Error loading user data for '{user_dir.name}': {e}")

        return users

    def delete_user(self, user_id: str) -> bool:
        """
        Delete a user account.

        Args:
            user_id: User ID to delete

        Returns:
            True if user was deleted successfully, False otherwise
        """
        user_dir = self.users_dir / user_id

        if not user_dir.exists():
            return False

        try:
            # Remove all files in user directory
            for item in user_dir.glob("**/*"):
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    for subitem in item.glob("**/*"):
                        if subitem.is_file():
                            subitem.unlink()
                    item.rmdir()

            # Remove user directory
            user_dir.rmdir()

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
        auth_path = self.users_dir / user_id / "auth.json"

        if not auth_path.exists():
            return False, "User not found"

        try:
            # Load auth data
            with open(auth_path, "r", encoding="utf-8") as f:
                auth_data = json.load(f)

            # Verify current password
            salt = auth_data["salt"]
            stored_hash = auth_data["password_hash"]

            if self._hash_password(current_password, salt) != stored_hash:
                return False, "Current password is incorrect"

            # Generate new salt and hash
            new_salt = secrets.token_hex(16)
            new_hash = self._hash_password(new_password, new_salt)

            # Update auth data
            auth_data["salt"] = new_salt
            auth_data["password_hash"] = new_hash

            # Save auth data
            with open(auth_path, "w", encoding="utf-8") as f:
                json.dump(auth_data, f, indent=2)

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
        profile = self.get_profile(user_id)

        if profile:
            profile["last_login"] = datetime.now().isoformat()
            self.save_profile(user_id, profile)

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

    def update_preferences(self, user_id: str, preferences: Dict[str, Any]) -> bool:
        """
        Update a user's preferences.

        Args:
            user_id: User ID to update preferences for
            preferences: Dictionary containing preference updates

        Returns:
            True if preferences were updated successfully, False otherwise
        """
        profile = self.get_profile(user_id)

        if not profile:
            return False

        # Ensure preferences section exists
        if "preferences" not in profile:
            profile["preferences"] = self.DEFAULT_PROFILE["preferences"]

        # Update only the specified preferences
        for key, value in preferences.items():
            profile["preferences"][key] = value

        return self.save_profile(user_id, profile)

    def get_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Get a user's preferences.

        Args:
            user_id: User ID to get preferences for

        Returns:
            Dictionary containing user preferences, or empty dict if user doesn't exist
        """
        profile = self.get_profile(user_id)

        if not profile:
            return {}

        return profile.get("preferences", {})

    def update_personalization(self, user_id: str, personalization: Dict[str, Any]) -> bool:
        """
        Update a user's personalization settings.

        Args:
            user_id: User ID to update personalization for
            personalization: Dictionary containing personalization updates

        Returns:
            True if personalization was updated successfully, False otherwise
        """
        profile = self.get_profile(user_id)

        if not profile:
            return False

        # Ensure personalization section exists
        if "personalization" not in profile:
            profile["personalization"] = self.DEFAULT_PROFILE["personalization"]

        # Update only the specified personalization settings
        for key, value in personalization.items():
            profile["personalization"][key] = value

        return self.save_profile(user_id, profile)

    def get_personalization(self, user_id: str) -> Dict[str, Any]:
        """
        Get a user's personalization settings.

        Args:
            user_id: User ID to get personalization for

        Returns:
            Dictionary containing user personalization, or empty dict if user doesn't exist
        """
        profile = self.get_profile(user_id)

        if not profile:
            return {}

        return profile.get("personalization", {})

    def update_privacy_settings(self, user_id: str, privacy_settings: Dict[str, Any]) -> bool:
        """
        Update a user's privacy settings.

        Args:
            user_id: User ID to update privacy settings for
            privacy_settings: Dictionary containing privacy setting updates

        Returns:
            True if privacy settings were updated successfully, False otherwise
        """
        profile = self.get_profile(user_id)

        if not profile:
            return False

        # Ensure privacy section exists
        if "privacy" not in profile:
            profile["privacy"] = self.DEFAULT_PROFILE["privacy"]

        # Update only the specified privacy settings
        for key, value in privacy_settings.items():
            profile["privacy"][key] = value

        return self.save_profile(user_id, profile)

    def get_privacy_settings(self, user_id: str) -> Dict[str, Any]:
        """
        Get a user's privacy settings.

        Args:
            user_id: User ID to get privacy settings for

        Returns:
            Dictionary containing user privacy settings, or empty dict if user doesn't exist
        """
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

    def export_user_data(self, user_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Export all data for a user.

        Args:
            user_id: User ID to export data for

        Returns:
            Tuple of (success, data or error message)
        """
        try:
            user_dir = self.users_dir / user_id

            if not user_dir.exists():
                return False, {"error": f"User '{user_id}' not found"}

            # Get profile data
            profile = self.get_profile(user_id)

            # Get user settings
            settings = self.settings_manager.get_settings(user_id)

            # Get conversation metadata
            from engine.conversation_store import ConversationStore
            conversation_store = ConversationStore(base_dir=self.base_dir, user_manager=self)
            conversations = []

            for category in conversation_store.list_categories(user_id):
                category_conversations = conversation_store.list_conversation_meta(user_id, category)
                conversations.extend(category_conversations)

            # Compile export data
            export_data = {
                "user_id": user_id,
                "profile": profile,
                "settings": settings,
                "conversations": conversations,
                "export_date": datetime.now().isoformat()
            }

            return True, export_data
        except Exception as e:
            error_msg = f"Error exporting data for user '{user_id}': {e}"
            logger.error(error_msg)
            return False, {"error": error_msg}

    def import_user_data(self, user_id: str, import_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Import data for a user.

        Args:
            user_id: User ID to import data for
            import_data: Dictionary containing user data to import

        Returns:
            Tuple of (success, message)
        """
        try:
            # Validate import data
            if "profile" not in import_data:
                return False, "Import data missing profile information"

            # Update profile
            profile = import_data.get("profile", {})
            self.save_profile(user_id, profile)

            # Update settings if present
            if "settings" in import_data:
                self.settings_manager.save_settings(import_data["settings"], user_id)

            return True, f"User data imported successfully for '{user_id}'"
        except Exception as e:
            error_msg = f"Error importing data for user '{user_id}': {e}"
            logger.error(error_msg)
            return False, error_msg
