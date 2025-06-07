import json
import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import logging

from engine.user_manager import UserManager
from engine.settings_manager import SettingsManager

logger = logging.getLogger(__name__)

class ProfileMigrator:
    """
    Handles migration of profile data from the old single-user structure to the new multi-user structure.

    This class is responsible for:
    - Creating the users directory structure
    - Moving existing profile data to the new structure
    - Creating a default admin user with the existing profile data
    - Ensuring proper isolation between user data
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize the ProfileMigrator.

        Args:
            base_dir: Base directory for the application. If None, uses the parent directory of the current file.
        """
        self.base_dir = base_dir or Path(__file__).parent.parent
        self.profile_path = self.base_dir / "profile.json"
        self.settings_path = self.base_dir / "settings.json"
        self.conversations_dir = self.base_dir / "conversations"
        self.users_dir = self.base_dir / "users"

        # Initialize managers
        self.settings_manager = SettingsManager(base_dir=self.base_dir)
        self.user_manager = UserManager(base_dir=self.base_dir)

    def migrate_profile(self, admin_username: str, admin_password: str) -> Tuple[bool, str]:
        """
        Migrate the existing profile to the new multi-user structure.

        Args:
            admin_username: Username for the admin user
            admin_password: Password for the admin user

        Returns:
            Tuple of (success, message)
        """
        # Check if migration is needed
        if not self._migration_needed():
            return True, "Migration not needed, already using multi-user structure"

        try:
            # Create the admin user
            success, message = self._create_admin_user(admin_username, admin_password)
            if not success:
                return False, message

            # Migrate conversations
            success, message = self._migrate_conversations(admin_username)
            if not success:
                return False, message

            # Clean up old files
            self._cleanup_old_files()

            return True, "Profile migration completed successfully"
        except Exception as e:
            logger.error(f"Error during profile migration: {e}")
            return False, f"Error during profile migration: {str(e)}"

    def _migration_needed(self) -> bool:
        """
        Check if migration is needed.

        Returns:
            True if migration is needed, False otherwise
        """
        # If profile.json exists at the root level, migration is needed
        return self.profile_path.exists()

    def _create_admin_user(self, admin_username: str, admin_password: str) -> Tuple[bool, str]:
        """
        Create an admin user with the existing profile data.

        Args:
            admin_username: Username for the admin user
            admin_password: Password for the admin user

        Returns:
            Tuple of (success, message)
        """
        # Load existing profile
        if not self.profile_path.exists():
            # No existing profile, create a default admin user
            return self.user_manager.create_user(admin_username, admin_password, "Admin", "admin")

        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                profile_data = json.load(f)

            # Create the admin user
            success, message = self.user_manager.create_user(
                admin_username,
                admin_password,
                profile_data.get("name", "Admin"),
                "admin"
            )

            if not success:
                return False, message

            # Update the admin user's profile with existing data
            admin_profile = self.user_manager.get_profile(admin_username)
            if admin_profile:
                # Copy preferences from existing profile
                if "preferences" in profile_data:
                    admin_profile["preferences"] = profile_data["preferences"]

                # Copy history if present
                if "history" in profile_data:
                    admin_profile["history"] = profile_data["history"]

                # Save the updated profile
                self.user_manager.save_profile(admin_username, admin_profile)

            # Migrate settings
            self._migrate_settings(admin_username)

            return True, f"Admin user '{admin_username}' created successfully"
        except Exception as e:
            logger.error(f"Error creating admin user: {e}")
            return False, f"Error creating admin user: {str(e)}"

    def _migrate_settings(self, admin_username: str) -> None:
        """
        Migrate settings from the old structure to the new structure.

        Args:
            admin_username: Username of the admin user
        """
        if not self.settings_path.exists():
            return

        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                settings_data = json.load(f)

            # Save as global settings
            self.settings_manager.save_settings(settings_data)

            # Also save user-specific settings for the admin
            self.settings_manager.save_settings(settings_data, admin_username)
        except Exception as e:
            logger.error(f"Error migrating settings: {e}")

    def _migrate_conversations(self, admin_username: str) -> Tuple[bool, str]:
        """
        Migrate conversations from the old structure to the new structure.

        Args:
            admin_username: Username of the admin user

        Returns:
            Tuple of (success, message)
        """
        if not self.conversations_dir.exists():
            return True, "No conversations to migrate"

        try:
            # Create admin user's conversations directory
            admin_conversations_dir = self.users_dir / admin_username / "conversations"
            admin_conversations_dir.mkdir(exist_ok=True)

            # Copy all conversation files to the admin user's directory
            conversation_count = 0
            for item in self.conversations_dir.glob("*.json"):
                if item.is_file():
                    # Copy the file
                    shutil.copy2(item, admin_conversations_dir)
                    conversation_count += 1

            return True, f"Migrated {conversation_count} conversations to admin user"
        except Exception as e:
            logger.error(f"Error migrating conversations: {e}")
            return False, f"Error migrating conversations: {str(e)}"

    def _cleanup_old_files(self) -> None:
        """
        Clean up old files after migration.

        This renames the old files with a .bak extension rather than deleting them,
        to ensure data is not lost if something goes wrong.
        """
        try:
            # Rename profile.json to profile.json.bak
            if self.profile_path.exists():
                backup_path = self.profile_path.with_suffix(".json.bak")
                self.profile_path.rename(backup_path)
                logger.info(f"Renamed {self.profile_path} to {backup_path}")

            # Rename settings.json to settings.json.bak
            # Note: We don't do this because settings.json is still used for global settings
            # but we could move it to a different location in the future

            # Rename conversations directory to conversations.bak
            if self.conversations_dir.exists():
                backup_dir = Path(str(self.conversations_dir) + ".bak")
                if backup_dir.exists():
                    shutil.rmtree(backup_dir)
                self.conversations_dir.rename(backup_dir)
                logger.info(f"Renamed {self.conversations_dir} to {backup_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up old files: {e}")
