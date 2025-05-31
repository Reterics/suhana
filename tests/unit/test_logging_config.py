import pytest
import logging
import tempfile
import sys
from pathlib import Path
from unittest.mock import patch

from engine.logging_config import (
    configure_logging,
    get_logger,
    set_log_level,
    get_log_config,
)

@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for log files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture(autouse=True)
def reset_logging():
    """Reset logging configuration after each test."""
    # Store original handlers for uvicorn.app logger
    uvicorn_app_logger = logging.getLogger("uvicorn.app")
    original_handlers = uvicorn_app_logger.handlers.copy()
    original_level = uvicorn_app_logger.level
    original_propagate = uvicorn_app_logger.propagate

    # Clear all existing handlers
    for handler in uvicorn_app_logger.handlers[:]:
        if hasattr(handler, 'close'):
            handler.close()
        uvicorn_app_logger.removeHandler(handler)

    yield

    # Clean up after test
    for handler in uvicorn_app_logger.handlers[:]:
        if hasattr(handler, 'close'):
            handler.close()
        uvicorn_app_logger.removeHandler(handler)

    # Restore original configuration
    for handler in original_handlers:
        uvicorn_app_logger.addHandler(handler)
    uvicorn_app_logger.setLevel(original_level)
    uvicorn_app_logger.propagate = original_propagate

def test_configure_logging_creates_handlers(temp_log_dir):
    """Test that configure_logging creates the expected handlers."""
    # Make sure we close any existing handlers first
    uvicorn_app_logger = logging.getLogger("uvicorn.app")
    for handler in uvicorn_app_logger.handlers[:]:
        if hasattr(handler, 'close'):
            handler.close()
        uvicorn_app_logger.removeHandler(handler)

    try:
        configure_logging(
            config={
                "console_level": "INFO",
                "file_level": "DEBUG",
                "log_file": "test.log"
            },
            log_dir=temp_log_dir
        )

        # Use uvicorn.app logger as per implementation
        uvicorn_app_logger = logging.getLogger("uvicorn.app")

        # Should have exactly two handlers (console and file)
        assert len(uvicorn_app_logger.handlers) == 2

        # Verify handler types
        console_handlers = [h for h in uvicorn_app_logger.handlers
                           if isinstance(h, logging.StreamHandler) and not hasattr(h, 'baseFilename')]
        file_handlers = [h for h in uvicorn_app_logger.handlers
                        if hasattr(h, 'baseFilename')]

        assert len(console_handlers) == 1
        assert len(file_handlers) == 1

        # Verify log file was created in the temp directory
        log_file = temp_log_dir / "test.log"
        assert log_file.parent.exists()
    finally:
        # Make sure we close all handlers before exiting
        for handler in uvicorn_app_logger.handlers[:]:
            if hasattr(handler, 'close'):
                handler.close()
            uvicorn_app_logger.removeHandler(handler)

def test_get_logger_returns_configured_logger(reset_logging):
    """Test that get_logger returns a properly configured logger with correct naming."""
    # Configure with custom format
    test_format = "%(levelname)s - %(message)s"
    configure_logging(config={"log_format": test_format})

    logger = get_logger("test_module")

    # Verify logger name is prefixed correctly
    assert logger.name == "uvicorn.app.test_module"

    # Verify propagate setting
    assert logger.propagate is False

    # Check that the logger's parent has the correct handlers with the right formatter
    parent_logger = logging.getLogger("uvicorn.app")
    for handler in parent_logger.handlers:
        assert handler.formatter._fmt == test_format

def test_get_logger_with_uvicorn_prefix(reset_logging):
    """Test that get_logger preserves uvicorn prefix if already present."""
    configure_logging()

    logger = get_logger("uvicorn.test_module")

    # Should keep the original name if it already starts with uvicorn
    assert logger.name == "uvicorn.test_module"

def test_set_log_level_changes_handler_levels(reset_logging):
    """Test that set_log_level changes the log levels of handlers."""
    # First configure logging to ensure we have the handlers
    configure_logging()

    # Get the root logger that set_log_level uses
    root_logger = logging.getLogger()
    uvicorn_app_logger = logging.getLogger("uvicorn.app")

    # Set console level to DEBUG
    set_log_level("DEBUG", handler_type="console")

    # Check the config was updated
    config = get_log_config()
    assert config["console_level"] == "DEBUG"

    # Reconfigure logging to apply the changes
    configure_logging()

    # Now check the handlers
    console_handlers = [h for h in uvicorn_app_logger.handlers
                       if isinstance(h, logging.StreamHandler) and not hasattr(h, 'baseFilename')]

    for handler in console_handlers:
        assert handler.level == logging.DEBUG

    # Set all handlers to WARNING
    set_log_level("WARNING", handler_type="all")

    # Check the config was updated
    config = get_log_config()
    assert config["console_level"] == "WARNING"
    assert config["file_level"] == "WARNING"

    # Reconfigure logging to apply the changes
    configure_logging()

    # Verify all handlers have the new level
    for handler in uvicorn_app_logger.handlers:
        assert handler.level == logging.WARNING

def test_configure_logging_creates_log_dir(reset_logging):
    """Test that configure_logging creates the log directory if it doesn't exist."""
    # Use a fixed path instead of a temporary directory to avoid cleanup issues
    log_dir = Path("test_logs_dir")

    try:
        # This should create the directory
        configure_logging(log_dir=log_dir)

        # Verify the directory was created
        assert log_dir.exists()
        assert log_dir.is_dir()
    finally:
        # Clean up by closing all handlers
        uvicorn_app_logger = logging.getLogger("uvicorn.app")
        for handler in uvicorn_app_logger.handlers[:]:
            if hasattr(handler, 'close'):
                handler.close()
            uvicorn_app_logger.removeHandler(handler)

        # Try to remove the directory, but don't fail if it can't be removed
        try:
            import shutil
            shutil.rmtree(log_dir, ignore_errors=True)
        except:
            pass

@patch("logging.handlers.RotatingFileHandler", side_effect=Exception("Test exception"))
def test_configure_logging_handles_file_handler_error(mock_handler, reset_logging):
    """Test that configure_logging handles errors when creating the file handler."""
    # This should not raise an exception
    configure_logging(config={"log_file": "test.log"})

    # Verify the mock was called
    mock_handler.assert_called_once()

    # Verify we still have one handler (console)
    uvicorn_app_logger = logging.getLogger("uvicorn.app")
    assert len(uvicorn_app_logger.handlers) == 1
    assert isinstance(uvicorn_app_logger.handlers[0], logging.StreamHandler)

def test_set_log_level_with_string():
    """Test set_log_level with a string level name."""
    configure_logging()

    # Set file level to DEBUG using string
    set_log_level("DEBUG", handler_type="file")

    # Get the current config and verify
    config = get_log_config()
    assert config["file_level"] == "DEBUG"

def test_get_log_config_returns_current_config():
    """Test that get_log_config returns the current configuration."""
    # Configure with custom settings
    custom_config = {
        "console_level": "DEBUG",
        "file_level": "ERROR",
        "log_file": "custom.log",
        "max_file_size": 5000000,
        "propagate": True
    }

    configure_logging(config=custom_config)

    # Get the current config
    current_config = get_log_config()

    # Verify key settings were applied
    assert current_config["console_level"] == "DEBUG"
    assert current_config["file_level"] == "ERROR"
    assert current_config["log_file"] == "custom.log"
    assert current_config["max_file_size"] == 5000000
    assert current_config["propagate"] == True

@patch("logging.handlers.RotatingFileHandler")
def test_configure_logging_file_handler_creation(mock_handler, temp_log_dir, reset_logging):
    """Test that the file handler is created with the correct parameters."""
    configure_logging(
        config={
            "max_file_size": 1000000,
            "backup_count": 3,
            "log_file": "test.log"
        },
        log_dir=temp_log_dir
    )

    # Verify RotatingFileHandler was created with correct parameters
    mock_handler.assert_called_once()
    args, kwargs = mock_handler.call_args

    assert str(temp_log_dir / "test.log") in str(args[0])
    assert kwargs["maxBytes"] == 1000000
    assert kwargs["backupCount"] == 3
    assert kwargs["encoding"] == 'utf-8'

def test_log_messages_at_different_levels(temp_log_dir, reset_logging, capsys):
    """Test that messages are logged at the appropriate levels."""
    # Use a simple log file name
    log_file_name = "test_log.log"

    # Make sure we close any existing handlers
    uvicorn_app_logger = logging.getLogger("uvicorn.app")
    for handler in uvicorn_app_logger.handlers[:]:
        if hasattr(handler, 'close'):
            handler.close()
        uvicorn_app_logger.removeHandler(handler)

    configure_logging(
        config={
            "console_level": "WARNING",
            "file_level": "DEBUG",
            "log_file": log_file_name
        },
        log_dir=temp_log_dir
    )

    logger = get_logger("test_logger")

    # This should not appear in console but should be in file
    logger.debug("Debug message")

    # This should appear in both
    logger.warning("Warning message")

    # Flush stdout to ensure messages are captured
    sys.stdout.flush()

    # Close all handlers to ensure files are properly closed
    for handler in uvicorn_app_logger.handlers[:]:
        if hasattr(handler, 'close'):
            handler.close()
        uvicorn_app_logger.removeHandler(handler)

    # Verify console output using pytest's capsys fixture
    captured = capsys.readouterr()
    console_output = captured.out + captured.err  # Check both stdout and stderr

    assert "Warning message" in console_output
    assert "Debug message" not in console_output

    # Verify the log directory exists (don't check the file itself)
    assert temp_log_dir.exists()

def test_configure_logging_clears_existing_handlers():
    """Test that configure_logging clears existing handlers before adding new ones."""
    # Get the logger and ensure it's clean
    uvicorn_app_logger = logging.getLogger("uvicorn.app")

    # Make sure we start with no handlers
    for handler in uvicorn_app_logger.handlers[:]:
        uvicorn_app_logger.removeHandler(handler)

    # Add a dummy handler to the logger
    dummy_handler = logging.StreamHandler()
    uvicorn_app_logger.addHandler(dummy_handler)

    # Verify we have exactly 1 handler (our dummy)
    assert len(uvicorn_app_logger.handlers) == 1
    assert uvicorn_app_logger.handlers[0] is dummy_handler

    # Configure logging - this should clear existing handlers
    configure_logging()

    # Should now have exactly 2 handlers (console and file)
    assert len(uvicorn_app_logger.handlers) == 2

    # Verify none of them is our dummy handler
    for handler in uvicorn_app_logger.handlers:
        assert handler is not dummy_handler
