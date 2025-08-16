from typing import Dict, Any, Optional
import logging
from functools import lru_cache

from engine.database.base import DatabaseAdapter
from engine.engine_config import get_database_adapter

logger = logging.getLogger(__name__)

class SettingsManager:
    """
    DB-backed settings manager. No filesystem support.
    - Global settings are stored with user_id = NULL in the database.
    - Per-user settings are stored with user_id set.
    - No legacy file-based implementation is supported.
    """

    CURRENT_VERSION = 1

    DEFAULT_SETTINGS: Dict[str, Any] = {
        "version": CURRENT_VERSION,
        "llm_backend": "ollama",
        "llm_model": "llama3",
        "openai_model": "gpt-4o-mini",
        "gemini_model": "gemini-1.5-flash",
        "claude_model": "claude-3-5-sonnet-20240620",
        "voice": False,
        "streaming": False,
        "secured_streaming": False,
        "logging": {
            "console_level": "INFO",
            "file_level": "DEBUG",
            "log_file": "suhana.log",
            "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "date_format": "%Y-%m-%d %H:%M:%S",
            "max_file_size": 10 * 1024 * 1024,
            "backup_count": 5,
            "propagate": False,
        },
    }

    def __init__(self, db: Optional[DatabaseAdapter] = None):
        self.db: DatabaseAdapter = db or get_database_adapter()
        # Ensure schema exists
        try:
            self.db.initialize_schema()
        except Exception:
            logger.exception("Failed to initialize DB schema for settings")

    @lru_cache(maxsize=16)
    def get_settings(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            global_settings = self.db.get_settings(None) or {}
            if not global_settings:
                # Initialize with defaults if empty
                self.save_settings(self.DEFAULT_SETTINGS.copy(), None)
                global_settings = self.DEFAULT_SETTINGS.copy()

            if not user_id:
                return self._with_version(global_settings)

            user_settings = self.db.get_settings(user_id) or {}
            return self._merge_dicts(self._with_version(global_settings), user_settings)
        except Exception:
            logger.exception("Failed to load settings from DB")
            return self.DEFAULT_SETTINGS.copy()

    def save_settings(self, settings: Dict[str, Any], user_id: Optional[str] = None) -> bool:
        try:
            data = self._with_version(settings)
            ok = self.db.save_settings(data, user_id)
            # Bust cache: both the global view and per-user merged view may change
            self.get_settings.cache_clear()
            return ok
        except Exception:
            logger.exception("Failed to save settings to DB")
            return False

    # --- helpers ---
    def _with_version(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        s = dict(settings)
        if "version" not in s:
            s["version"] = self.CURRENT_VERSION
        return s

    def _merge_dicts(self, base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(base)
        for k, v in (overrides or {}).items():
            if isinstance(v, dict) and isinstance(result.get(k), dict):
                result[k] = self._merge_dicts(result[k], v)
            else:
                result[k] = v
        return result
