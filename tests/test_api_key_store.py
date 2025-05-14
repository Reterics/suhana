import json
import tempfile
from pathlib import Path

import pytest
from engine import api_key_store


@pytest.fixture
def temp_key_path(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_path = Path(tmpdir) / "api_keys.json"
        monkeypatch.setattr("engine.api_key_store.API_KEY_PATH", fake_path)
        yield fake_path


def test_get_default_key_from_env(monkeypatch):
    monkeypatch.setenv("SUHANA_DEFAULT_API_KEY", "test-env-key")
    key = api_key_store.get_default_key()
    assert key == "test-env-key"


def test_get_default_key_generated(monkeypatch):
    monkeypatch.delenv("SUHANA_DEFAULT_API_KEY", raising=False)
    key = api_key_store.get_default_key()
    assert isinstance(key, str)
    assert len(key) > 10


def test_ensure_api_keys_file_creates_file(temp_key_path):
    assert not temp_key_path.exists()
    api_key_store.ensure_api_keys_file()
    assert temp_key_path.exists()
    content = json.loads(temp_key_path.read_text())
    assert "keys" in content
    assert isinstance(content["keys"], list)
    assert content["keys"][0]["active"] is True


def test_load_valid_api_keys(temp_key_path):
    dummy_key = "abc123"
    test_data = {
        "keys": [
            {"key": dummy_key, "owner": "dev", "active": True},
            {"key": "inactive", "owner": "test", "active": False}
        ]
    }
    temp_key_path.write_text(json.dumps(test_data, indent=2))
    keys = api_key_store.load_valid_api_keys()
    assert dummy_key in keys
    assert "inactive" not in keys
