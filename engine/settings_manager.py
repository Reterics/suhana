import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

class SettingsManager:
    """
    Manages application settings with support for global and user-specific configurations.

    This class handles loading, saving, and validating settings, with support for:
    - User-specific settings overrides
    - Migration capabilities for settings schema changes
    - Caching for better performance
    """

    # Current settings schema version
    CURRENT_VERSION = 1

    # Default settings
    DEFAULT_SETTINGS = {
        "version": CURRENT_VERSION,
        "llm_backend": "ollama",
        "llm_model": "llama3",
        "openai_model": "gpt-4",
        "gemini_model": "gemini-pro",
        "claude_model": "claude-3-opus-20240229",
        # feature flags
        "voice": False,
        "streaming": False,
        "secured_streaming": False,
        "logging": {
            "console_level": "INFO",
            "file_level": "DEBUG",
            "log_file": "suhana.log",
            "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "date_format": "%Y-%m-%d %H:%M:%S",
            "max_file_size": 10485760,  # 10 MB
            "backup_count": 5,
            "propagate": False
        }
    }

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize the SettingsManager.

        Args:
            base_dir: Base directory for settings files. If None, uses the parent directory of the current file.
        """
        self.base_dir = base_dir or Path(__file__).parent.parent
        self.global_settings_path = self.base_dir / "settings.json"
        self.users_dir = self.base_dir / "users"
        self._settings_cache = {}

    @lru_cache(maxsize=8)
    def get_settings(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get settings for the specified user, or global settings if no user is specified.

        Args:
            user_id: Optional user ID to get user-specific settings

        Returns:
            Dictionary containing the merged settings (global + user-specific if applicable)
        """
        # Load global settings
        global_settings = self._load_global_settings()

        # If no user specified, return global settings
        if not user_id:
            return global_settings

        # Load and merge user-specific settings
        user_settings_path = self.users_dir / user_id / "settings.json"
        if user_settings_path.exists():
            try:
                with open(user_settings_path, "r", encoding="utf-8") as f:
                    user_settings = json.load(f)

                # Merge global and user settings
                merged_settings = self._merge_settings(global_settings, user_settings)
                return merged_settings
            except Exception as e:
                logger.error(f"Error loading user settings for {user_id}: {e}")
                return global_settings

        return global_settings

    def save_settings(self, settings: Dict[str, Any], user_id: Optional[str] = None) -> bool:
        """
        Save settings for the specified user, or global settings if no user is specified.

        Args:
            settings: Dictionary containing the settings to save
            user_id: Optional user ID to save user-specific settings

        Returns:
            True if settings were saved successfully, False otherwise
        """
        try:
            # Ensure settings have a version
            if "version" not in settings:
                settings["version"] = self.CURRENT_VERSION

            # Determine the path to save to
            if user_id:
                # Ensure user directory exists
                user_dir = self.users_dir / user_id
                user_dir.mkdir(parents=True, exist_ok=True)
                settings_path = user_dir / "settings.json"

                # For user settings, we only save the differences from global settings
                global_settings = self._load_global_settings()
                user_settings = self._extract_user_overrides(global_settings, settings)

                with open(settings_path, "w", encoding="utf-8") as f:
                    json.dump(user_settings, f, indent=2)
            else:
                # Save global settings
                with open(self.global_settings_path, "w", encoding="utf-8") as f:
                    json.dump(settings, f, indent=2)

            # Clear cache for this user
            if user_id in self._settings_cache:
                del self._settings_cache[user_id]
            else:
                # Clear the entire cache if global settings changed
                self._settings_cache.clear()

            # Clear the lru_cache
            self.get_settings.cache_clear()

            return True
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return False

    def _load_global_settings(self) -> Dict[str, Any]:
        """
        Load global settings from file, or create default settings if file doesn't exist.

        Returns:
            Dictionary containing the global settings
        """
        if self.global_settings_path.exists():
            try:
                with open(self.global_settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)

                # Check if migration is needed
                if "version" not in settings or settings["version"] < self.CURRENT_VERSION:
                    settings = self._migrate_settings(settings)

                return settings
            except Exception as e:
                logger.error(f"Error loading global settings: {e}")
                return self.DEFAULT_SETTINGS.copy()
        else:
            # Create default settings file
            default_settings = self.DEFAULT_SETTINGS.copy()
            try:
                with open(self.global_settings_path, "w", encoding="utf-8") as f:
                    json.dump(default_settings, f, indent=2)
            except Exception as e:
                logger.error(f"Error creating default settings file: {e}")

            return default_settings

    def _merge_settings(self, global_settings: Dict[str, Any], user_settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge global and user-specific settings.

        Args:
            global_settings: Dictionary containing global settings
            user_settings: Dictionary containing user-specific settings

        Returns:
            Dictionary containing the merged settings
        """
        # Create a deep copy of global settings
        merged = global_settings.copy()

        # Recursively merge user settings
        def merge_dict(target, source):
            for key, value in source.items():
                if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                    merge_dict(target[key], value)
                else:
                    target[key] = value

        merge_dict(merged, user_settings)
        return merged

    def _extract_user_overrides(self, global_settings: Dict[str, Any], user_settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract user-specific overrides from the merged settings.

        Args:
            global_settings: Dictionary containing global settings
            user_settings: Dictionary containing merged settings

        Returns:
            Dictionary containing only the user-specific overrides
        """
        overrides = {}

        def extract_diff(global_dict, user_dict, result_dict):
            for key, value in user_dict.items():
                if key not in global_dict:
                    result_dict[key] = value
                elif isinstance(value, dict) and isinstance(global_dict[key], dict):
                    result_dict[key] = {}
                    extract_diff(global_dict[key], value, result_dict[key])
                    if not result_dict[key]:  # Remove empty dicts
                        del result_dict[key]
                elif value != global_dict[key]:
                    result_dict[key] = value

        extract_diff(global_settings, user_settings, overrides)

        # Always include version in user settings
        overrides["version"] = user_settings.get("version", self.CURRENT_VERSION)

        return overrides

    def _migrate_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migrate settings from an older version to the current version.

        Args:
            settings: Dictionary containing settings to migrate

        Returns:
            Dictionary containing the migrated settings
        """
        current_version = settings.get("version", 0)

        # Apply migrations based on version
        if current_version < 1:
            # Migrate to version 1
            settings = self._migrate_to_v1(settings)

        # Set the current version
        settings["version"] = self.CURRENT_VERSION

        return settings

    def _migrate_to_v1(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migrate settings to version 1.

        Args:
            settings: Dictionary containing settings to migrate

        Returns:
            Dictionary containing the migrated settings
        """
        # Map legacy keys to new schema
        if "ollama_model" in settings and "llm_model" not in settings:
            settings["llm_model"] = settings.get("ollama_model")
        # Clean up legacy keys if present
        if "ollama_model" in settings:
            try:
                del settings["ollama_model"]
            except Exception:
                pass

        # Add any missing default settings
        for key, value in self.DEFAULT_SETTINGS.items():
            if key not in settings:
                settings[key] = value

        return settings
