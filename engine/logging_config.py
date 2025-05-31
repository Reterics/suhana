import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Union


# Default configuration
DEFAULT_CONFIG = {
    "console_level": "INFO",
    "file_level": "DEBUG",
    "log_file": "suhana.log",
    "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "date_format": "%Y-%m-%d %H:%M:%S",
    "max_file_size": 10 * 1024 * 1024,
    "backup_count": 5,
    "propagate": False
}

_config: Dict[str, Any] = DEFAULT_CONFIG.copy()

def configure_logging(config: Optional[Dict[str, Any]] = None, log_dir: Optional[Union[str, Path]] = None) -> None:
    global _config
    if config:
        _config.update(config)

    log_file_path = Path(log_dir) / _config["log_file"] if log_dir else Path(_config["log_file"])
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger("uvicorn.app")
    root_logger.handlers.clear()
    root_logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(fmt=_config["log_format"], datefmt=_config["date_format"])

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging._nameToLevel[_config["console_level"]])
    ch.setFormatter(formatter)
    root_logger.addHandler(ch)

    # File handler (Rotating)
    try:
        from logging.handlers import RotatingFileHandler
        fh = RotatingFileHandler(log_file_path, maxBytes=_config["max_file_size"], backupCount=_config["backup_count"], encoding='utf-8')
        fh.setLevel(logging._nameToLevel[_config["file_level"]])
        fh.setFormatter(formatter)
        root_logger.addHandler(fh)
    except Exception as e:
        root_logger.error(f"Failed to set up file logging: {e}")

def get_logger(name: str) -> logging.Logger:
    if not name.startswith("uvicorn."):
        name = f"uvicorn.app.{name}"
    logger = logging.getLogger(name)
    logger.propagate = _config["propagate"]
    return logger

def set_log_level(level: str, handler_type: str = "all") -> None:
    levelno = logging._nameToLevel.get(level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if handler_type == "all":
            handler.setLevel(levelno)
        elif handler_type == "console" and isinstance(handler, logging.StreamHandler) and not hasattr(handler, "baseFilename"):
            handler.setLevel(levelno)
        elif handler_type == "file" and hasattr(handler, "baseFilename"):
            handler.setLevel(levelno)
    if handler_type in ("all", "console"):
        _config["console_level"] = logging.getLevelName(levelno)
    if handler_type in ("all", "file"):
        _config["file_level"] = logging.getLevelName(levelno)

def get_log_config() -> Dict[str, Any]:
    return _config.copy()

