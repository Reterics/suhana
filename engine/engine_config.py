from pathlib import Path
from dotenv import load_dotenv
import os
from typing import Dict, Any

from engine.database.base import DatabaseAdapter
from engine.logging_config import configure_logging

load_dotenv()

DEFAULT_LOG_DIR = Path(__file__).parent.parent / "logs"
DEFAULT_DB_PATH = Path(__file__).parent.parent / "suhana.db"

def load_settings() -> Dict[str, Any]:
    """
    Load settings from the database and configure the application.
    """
    # Lazy import to avoid circular dependency during module import
    from engine.settings_manager import SettingsManager
    settings = SettingsManager().get_settings(None)
    if not settings.get("openai_api_key"):
        settings["openai_api_key"] = os.getenv("OPENAI_API_KEY")
    configure_logging_from_settings(settings)
    return settings

def configure_logging_from_settings(settings: Dict[str, Any]) -> None:
    """
    Configure the logging system based on the application settings.

    Args:
        settings: Dictionary containing the application settings
    """
    # Get logging settings with defaults
    logging_config = settings.get("logging", {})

    # Set up log directory
    log_dir = logging_config.get("log_dir")
    if log_dir:
        log_dir = Path(log_dir)
    else:
        log_dir = DEFAULT_LOG_DIR

    # Configure logging
    configure_logging(
        config={
            "console_level": logging_config.get("console_level", "INFO"),
            "file_level": logging_config.get("file_level", "DEBUG"),
            "log_file": logging_config.get("log_file", "suhana.log"),
            "log_format": logging_config.get("log_format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
            "date_format": logging_config.get("date_format", "%Y-%m-%d %H:%M:%S"),
            "max_file_size": logging_config.get("max_file_size", 10 * 1024 * 1024),  # 10 MB
            "backup_count": logging_config.get("backup_count", 5),
            "propagate": logging_config.get("propagate", False)
        },
        log_dir=log_dir
    )

def save_settings(settings: Dict[str, Any]):
    # Lazy import to avoid circular dependency
    from engine.settings_manager import SettingsManager
    SettingsManager().save_settings(settings, None)

def switch_backend(new_backend, settings):
    if new_backend in ["ollama", "openai", "gemini", "claude"]:
        settings["llm_backend"] = new_backend
        save_settings(settings)
        print(f"🔁 Switched to {new_backend.upper()}")
    else:
        print("❌ Supported engines: ollama, openai, gemini, claude")
    return new_backend

def get_database_adapter() -> DatabaseAdapter:
    """
    Return a database adapter. No file-based settings are used.
    Environment overrides (optional):
    - SUHANA_DB_TYPE = sqlite | postgres (default: sqlite)
    - SUHANA_DB_PATH (for sqlite)
    - POSTGRES_CONN (full connection string for postgres)
    """
    db_type = os.getenv("SUHANA_DB_TYPE", "sqlite").lower()

    if db_type == "postgres":
        from engine.database.postgres import PostgresAdapter
        conn = os.getenv("POSTGRES_CONN")
        if not conn:
            # Build from individual env vars if provided
            host = os.getenv("POSTGRES_HOST", "localhost")
            port = os.getenv("POSTGRES_PORT", "5432")
            database = os.getenv("POSTGRES_DB", "suhana")
            user = os.getenv("POSTGRES_USER", "postgres")
            password = os.getenv("POSTGRES_PASSWORD", "")
            conn = f"host={host} port={port} dbname={database} user={user} password={password}"
        return PostgresAdapter(conn)
    else:
        from engine.database.sqlite import SQLiteAdapter
        db_path = os.getenv("SUHANA_DB_PATH", str(DEFAULT_DB_PATH))
        return SQLiteAdapter(db_path)
