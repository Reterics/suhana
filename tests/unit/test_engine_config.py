from unittest.mock import patch
import os
from pathlib import Path

from engine.engine_config import (
    load_settings,
    configure_logging_from_settings,
    save_settings,
    switch_backend,
)


def test_load_settings_uses_settings_manager_and_env():
    base_settings = {
        "llm_backend": "ollama",
        "llm_model": "llama3",
        "openai_api_key": None,
        "logging": {"console_level": "INFO"},
    }
    with patch("engine.settings_manager.SettingsManager") as SM, \
         patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}, clear=False), \
         patch("engine.engine_config.configure_logging_from_settings") as cfg:
        SM.return_value.get_settings.return_value = dict(base_settings)

        settings = load_settings()

        SM.return_value.get_settings.assert_called_once_with(None)
        assert settings["llm_backend"] == "ollama"
        assert settings["llm_model"] == "llama3"
        # env injection occurs when value is falsy
        assert settings["openai_api_key"] == "test-api-key"
        cfg.assert_called_once()


def test_load_settings_no_env_keeps_none():
    base_settings = {
        "llm_backend": "openai",
        "llm_model": "gpt-4o-mini",
        "openai_api_key": None,
        "logging": {},
    }
    with patch("engine.settings_manager.SettingsManager") as SM, \
         patch.dict(os.environ, {}, clear=True), \
         patch("engine.engine_config.configure_logging_from_settings") as cfg:
        SM.return_value.get_settings.return_value = dict(base_settings)

        settings = load_settings()

        assert settings["llm_backend"] == "openai"
        assert settings["llm_model"] == "gpt-4o-mini"
        assert settings["openai_api_key"] is None
        cfg.assert_called_once()


def test_configure_logging_from_settings():
    with patch("engine.engine_config.configure_logging") as mock_configure:
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
                "propagate": True,
            }
        }
        configure_logging_from_settings(test_settings)
        mock_configure.assert_called_once()
        _, kwargs = mock_configure.call_args
        assert kwargs["config"]["console_level"] == "DEBUG"
        assert kwargs["config"]["file_level"] == "INFO"
        assert kwargs["config"]["log_file"] == "custom.log"
        assert kwargs["config"]["log_format"] == "%(message)s"
        assert kwargs["config"]["date_format"] == "%H:%M:%S"
        assert kwargs["config"]["max_file_size"] == 5000000
        assert kwargs["config"]["backup_count"] == 3
        assert kwargs["config"]["propagate"] is True
        assert kwargs["log_dir"] == Path("/custom/log/dir")


def test_configure_logging_from_settings_defaults():
    with patch("engine.engine_config.configure_logging") as mock_configure:
        test_settings = {"logging": {}}
        configure_logging_from_settings(test_settings)
        _, kwargs = mock_configure.call_args
        assert kwargs["config"]["console_level"] == "INFO"
        assert kwargs["config"]["file_level"] == "DEBUG"
        assert kwargs["config"]["log_file"] == "suhana.log"


def test_configure_logging_from_settings_no_logging_section():
    with patch("engine.engine_config.configure_logging") as mock_configure:
        test_settings = {}
        configure_logging_from_settings(test_settings)
        _, kwargs = mock_configure.call_args
        assert kwargs["config"]["console_level"] == "INFO"
        assert kwargs["config"]["file_level"] == "DEBUG"
        assert kwargs["config"]["log_file"] == "suhana.log"


def test_save_settings_uses_settings_manager():
    settings = {"llm_backend": "openai", "openai_model": "gpt-4o-mini"}
    with patch("engine.settings_manager.SettingsManager") as SM:
        save_settings(settings)
        SM.return_value.save_settings.assert_called_once_with(settings, None)


def test_switch_backend_valid():
    test_settings = {"llm_backend": "ollama"}
    with patch("engine.engine_config.save_settings") as mock_save, \
         patch("builtins.print") as mock_print:
        result = switch_backend("openai", test_settings)
        assert test_settings["llm_backend"] == "openai"
        mock_save.assert_called_once_with(test_settings)
        mock_print.assert_called_once()
        args, _ = mock_print.call_args
        assert "Switched to OPENAI" in args[0]
        assert result == "openai"


def test_switch_backend_invalid():
    test_settings = {"llm_backend": "ollama"}
    with patch("engine.engine_config.save_settings") as mock_save, \
         patch("builtins.print") as mock_print:
        result = switch_backend("invalid_backend", test_settings)
        assert test_settings["llm_backend"] == "ollama"
        mock_save.assert_not_called()
        mock_print.assert_called_once()
        args, _ = mock_print.call_args
        assert "Supported engines" in args[0]
        assert result == "invalid_backend"
