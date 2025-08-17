import os
from unittest.mock import MagicMock

import pytest
from engine import api_key_store
from engine.api_key_store import ApiKeyManager


def test_get_default_key_from_env(monkeypatch):
    # Use a dummy db adapter because ApiKeyManager initializes the DB
    dummy_db = MagicMock()
    dummy_db.initialize_schema.return_value = None
    dummy_db.get_user_api_keys.return_value = []
    dummy_db.get_user.return_value = None
    dummy_db.create_user.return_value = True
    dummy_db.create_api_key.return_value = True

    monkeypatch.setenv("SUHANA_DEFAULT_API_KEY", "test-env-key")
    mgr = ApiKeyManager(db_adapter=dummy_db)
    key = mgr._get_default_key()
    assert key == "test-env-key"


def test_get_default_key_generated(monkeypatch):
    dummy_db = MagicMock()
    dummy_db.initialize_schema.return_value = None
    dummy_db.get_user_api_keys.return_value = []
    dummy_db.get_user.return_value = None
    dummy_db.create_user.return_value = True
    dummy_db.create_api_key.return_value = True

    monkeypatch.delenv("SUHANA_DEFAULT_API_KEY", raising=False)
    mgr = ApiKeyManager(db_adapter=dummy_db)
    key = mgr._get_default_key()
    assert isinstance(key, str)
    assert len(key) > 10


def test_load_valid_api_keys_uses_manager(monkeypatch):
    fake_manager = MagicMock()
    fake_manager.get_valid_api_keys.return_value = {"abc123", "xyz"}
    monkeypatch.setattr(api_key_store, "get_api_key_manager", lambda db_adapter=None: fake_manager)

    keys = api_key_store.load_valid_api_keys()
    assert "abc123" in keys
    assert "xyz" in keys
