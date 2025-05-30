import pytest
from unittest.mock import patch, mock_open
import json
import os
from pathlib import Path

from engine.engine_config import (
    load_settings,
    configure_logging_from_settings,
    save_settings,
    switch_backend,
    SETTINGS_PATH
)

@pytest.fixture
def mock_settings_file():
    """Mock the settings.json file."""
    test_settings = {
        "llm_backend": "ollama",
        "ollama_model": "llama3",
        "openai_model": "gpt-4",
        "openai_api_key": None,
        "logging": {
            "console_level": "INFO",
            "file_level": "DEBUG",
            "log_file": "test.log",
            "log_dir": "test_logs"
        }
    }

    with patch("builtins.open", mock_open(read_data=json.dumps(test_settings))) as mock_file:
        yield mock_file, test_settings

@pytest.fixture
def mock_env_vars():
    """Mock environment variables."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
        yield

@pytest.fixture
def mock_configure_logging():
    """Mock the configure_logging function."""
    with patch("engine.engine_config.configure_logging") as mock:
        yield mock

def test_load_settings(mock_settings_file, mock_env_vars, mock_configure_logging):
    """Test loading settings from file."""
    mock_file, test_settings = mock_settings_file

    # Call the function
    settings = load_settings()

    # Verify file was opened correctly
    mock_file.assert_called_with(SETTINGS_PATH, "r", encoding="utf-8")

    # Verify settings were loaded correctly
    assert settings["llm_backend"] == "ollama"
    assert settings["ollama_model"] == "llama3"

    # Verify API key was loaded from environment
    assert settings["openai_api_key"] == "test-api-key"

    # Verify configure_logging_from_settings was called
    assert mock_configure_logging.called

def test_load_settings_no_env_var(mock_settings_file, mock_configure_logging):
    """Test loading settings without environment variables."""
    mock_file, test_settings = mock_settings_file

    # We need to patch os.environ to ensure OPENAI_API_KEY is not set
    with patch.dict('os.environ', {}, clear=True):
        # Call the function
        settings = load_settings()

        # Verify settings were loaded correctly
        assert settings["llm_backend"] == "ollama"
        assert settings["ollama_model"] == "llama3"

        # Verify API key is None (not set in env)
        assert settings["openai_api_key"] is None

def test_configure_logging_from_settings(mock_configure_logging):
    """Test configuring logging from settings."""
    test_settings = {
        "logging": {
            "console_level": "DEBUG",
            "file_level": "INFO",
            "log_file": "custom.log",
            "log_dir": "/custom/log/dir",
            "log_format": "%(message)s",
            "date_format": "%H:%M:%S",
            "max_file_size": 5000000,
            "backup_count": 3,
            "propagate": True
        }
    }

    configure_logging_from_settings(test_settings)

    # Verify configure_logging was called with correct parameters
    mock_configure_logging.assert_called_once()
    args, kwargs = mock_configure_logging.call_args

    # Check config parameter
    assert kwargs["config"]["console_level"] == "DEBUG"
    assert kwargs["config"]["file_level"] == "INFO"
    assert kwargs["config"]["log_file"] == "custom.log"
    assert kwargs["config"]["log_format"] == "%(message)s"
    assert kwargs["config"]["date_format"] == "%H:%M:%S"
    assert kwargs["config"]["max_file_size"] == 5000000
    assert kwargs["config"]["backup_count"] == 3
    assert kwargs["config"]["propagate"] is True

    # Check log_dir parameter
    assert kwargs["log_dir"] == Path("/custom/log/dir")

def test_configure_logging_from_settings_defaults(mock_configure_logging):
    """Test configuring logging with default values."""
    # Settings with minimal logging configuration
    test_settings = {
        "logging": {}
    }

    configure_logging_from_settings(test_settings)

    # Verify configure_logging was called
    mock_configure_logging.assert_called_once()
    args, kwargs = mock_configure_logging.call_args

    # Check default values were used
    assert kwargs["config"]["console_level"] == "INFO"
    assert kwargs["config"]["file_level"] == "DEBUG"
    assert kwargs["config"]["log_file"] == "suhana.log"

def test_configure_logging_from_settings_no_logging_section(mock_configure_logging):
    """Test configuring logging when no logging section exists."""
    # Settings without logging configuration
    test_settings = {}

    configure_logging_from_settings(test_settings)

    # Verify configure_logging was called with defaults
    mock_configure_logging.assert_called_once()
    args, kwargs = mock_configure_logging.call_args

    # Check default values were used
    assert kwargs["config"]["console_level"] == "INFO"
    assert kwargs["config"]["file_level"] == "DEBUG"
    assert kwargs["config"]["log_file"] == "suhana.log"

def test_save_settings():
    """Test saving settings to file."""
    test_settings = {
        "llm_backend": "openai",
        "openai_model": "gpt-4"
    }

    # Mock the open function and json.dump
    mock_open_func = mock_open()
    with patch("builtins.open", mock_open_func), \
         patch("json.dump") as mock_json_dump:

        save_settings(test_settings)

        # Verify file was opened for writing
        mock_open_func.assert_called_with(SETTINGS_PATH, "w", encoding="utf-8")

        # Verify json.dump was called with the settings
        mock_json_dump.assert_called_once()
        args, kwargs = mock_json_dump.call_args

        # First argument should be the settings
        assert args[0] == test_settings
        # Second argument should be the file handle
        assert args[1] == mock_open_func()

def test_switch_backend_valid():
    """Test switching to a valid backend."""
    test_settings = {
        "llm_backend": "ollama"
    }

    with patch("engine.engine_config.save_settings") as mock_save, \
         patch("builtins.print") as mock_print:

        result = switch_backend("openai", test_settings)

        # Verify settings were updated
        assert test_settings["llm_backend"] == "openai"

        # Verify settings were saved
        mock_save.assert_called_once_with(test_settings)

        # Verify success message was printed
        mock_print.assert_called_once()
        args, _ = mock_print.call_args
        assert "Switched to OPENAI" in args[0]

        # Verify correct result
        assert result == "openai"

def test_switch_backend_invalid():
    """Test switching to an invalid backend."""
    test_settings = {
        "llm_backend": "ollama"
    }

    with patch("engine.engine_config.save_settings") as mock_save, \
         patch("builtins.print") as mock_print:

        result = switch_backend("invalid_backend", test_settings)

        # Verify settings were not updated
        assert test_settings["llm_backend"] == "ollama"

        # Verify settings were not saved
        mock_save.assert_not_called()

        # Verify error message was printed
        mock_print.assert_called_once()
        args, _ = mock_print.call_args
        assert "Supported engines" in args[0]

        # Verify correct result
        assert result == "invalid_backend"
