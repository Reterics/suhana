import logging
import sys
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, Union

# Define log levels as an enum for easier configuration
class LogLevel(Enum):
    """Enum representing log levels with their corresponding logging module values."""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

    @classmethod
    def from_string(cls, level_name: str) -> 'LogLevel':
        """Convert a string level name to a LogLevel enum value."""
        try:
            return cls[level_name.upper()]
        except KeyError:
            # Default to INFO if the level name is not recognized
            return cls.INFO

# Default configuration
DEFAULT_CONFIG = {
    "console_level": "INFO",
    "file_level": "DEBUG",
    "log_file": "suhana.log",
    "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "date_format": "%Y-%m-%d %H:%M:%S",
    "max_file_size": 10 * 1024 * 1024,  # 10 MB
    "backup_count": 5,
    "propagate": False
}

# Global configuration dictionary
_config: Dict[str, Any] = DEFAULT_CONFIG.copy()

def configure_logging(
    config: Optional[Dict[str, Any]] = None,
    log_dir: Optional[Union[str, Path]] = None
) -> None:
    """
    Configure the logging system with the given configuration.

    Args:
        config: Dictionary with logging configuration parameters
        log_dir: Directory where log files will be stored
    """
    global _config

    # Update configuration with provided values
    if config:
        _config.update(config)

    # Set up log directory
    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file_path = log_dir / _config["log_file"]
    else:
        log_file_path = Path(_config["log_file"])

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Set to lowest level to capture everything

    # Remove existing handlers to avoid duplicates when reconfiguring
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create formatters
    formatter = logging.Formatter(
        fmt=_config["log_format"],
        datefmt=_config["date_format"]
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(LogLevel.from_string(_config["console_level"]).value)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (using RotatingFileHandler for size management)
    try:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=_config["max_file_size"],
            backupCount=_config["backup_count"]
        )
        file_handler.setLevel(LogLevel.from_string(_config["file_level"]).value)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        # If file handler setup fails, log to console and continue
        console_handler.setLevel(logging.DEBUG)  # Ensure we capture everything
        root_logger.error(f"Failed to set up file logging: {e}")

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name, configured according to the current settings.

    Args:
        name: Name of the logger, typically __name__ of the module

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.propagate = _config["propagate"]
    return logger

def set_log_level(level: Union[str, LogLevel], handler_type: str = "all") -> None:
    """
    Set the log level for the specified handler type.

    Args:
        level: Log level to set (can be string or LogLevel enum)
        handler_type: Type of handler to set level for ('console', 'file', or 'all')
    """
    if isinstance(level, str):
        level = LogLevel.from_string(level).value
    elif isinstance(level, LogLevel):
        level = level.value

    root_logger = logging.getLogger()

    for handler in root_logger.handlers:
        if handler_type == "all" or (
            handler_type == "console" and isinstance(handler, logging.StreamHandler) and not hasattr(handler, "baseFilename")
        ) or (
            handler_type == "file" and hasattr(handler, "baseFilename")
        ):
            handler.setLevel(level)

    # Update configuration
    if handler_type in ("all", "console"):
        _config["console_level"] = logging.getLevelName(level)
    if handler_type in ("all", "file"):
        _config["file_level"] = logging.getLevelName(level)

def get_log_config() -> Dict[str, Any]:
    """
    Get the current logging configuration.

    Returns:
        Dictionary with current logging configuration
    """
    return _config.copy()

# Initialize logging with default configuration
configure_logging()
