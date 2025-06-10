import json
from pathlib import Path
from dotenv import load_dotenv
import os
from typing import Dict, Any, Optional

from engine.database.base import DatabaseAdapter
from engine.logging_config import configure_logging, get_log_config, set_log_level

load_dotenv()

SETTINGS_PATH = Path(__file__).parent.parent / "settings.json"
DEFAULT_LOG_DIR = Path(__file__).parent.parent / "logs"

def load_settings() -> Dict[str, Any]:
    """
    Load settings from the settings.json file and configure the application.

    Returns:
        Dictionary containing the application settings
    """
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        settings = json.load(f)

    # Fallback to env if not in settings
    if not settings.get("openai_api_key"):
        settings["openai_api_key"] = os.getenv("OPENAI_API_KEY")

    # Configure logging based on settings
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

def save_settings(settings):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

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
    Get a database adapter based on the current settings.

    Returns:
        DatabaseAdapter: An initialized database adapter
    """
    settings = load_settings()
    db_type = settings.get("database", {}).get("type", "sqlite")

    if db_type.lower() == "postgres":
        from engine.database.postgres import PostgresAdapter

        # Get connection parameters from settings
        db_config = settings.get("database", {}).get("postgres", {})
        connection_string = db_config.get("connection_string", "")

        # If no connection string is provided, build one from individual parameters
        if not connection_string:
            host = db_config.get("host", "localhost")
            port = db_config.get("port", 5432)
            database = db_config.get("database", "suhana")
            user = db_config.get("user", "postgres")
            password = db_config.get("password", "")

            connection_string = f"host={host} port={port} dbname={database} user={user} password={password}"

        return PostgresAdapter(connection_string)
    else:
        # Default to SQLite
        from engine.database.sqlite import SQLiteAdapter

        # Get database file path from settings or use default
        db_path = settings.get("database", {}).get("sqlite", {}).get("path", "suhana.db")

        # Ensure path is absolute
        if not os.path.isabs(db_path):
            db_path = os.path.join(os.path.dirname(SETTINGS_PATH), db_path)

        return SQLiteAdapter(db_path)
