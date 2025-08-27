import types
import sys
import pytest

# ------------------------------ Test doubles ---------------------------------

class FakeDB:
    """
    Minimal in-memory DB that matches the interface used by SettingsManager.
    Tracks call counts so we can assert lru_cache behavior.
    """
    def __init__(self):
        self._initialized = False
        self._store = {}  # key: user_id (None for global) -> dict
        self.get_calls = 0
        self.raise_on_get = False
        self.raise_on_save = False

    def initialize_schema(self):
        self._initialized = True

    def get_settings(self, user_id):
        self.get_calls += 1
        if self.raise_on_get:
            raise RuntimeError("DB get failure")
        # emulate DB returning a plain dict or None if missing
        return self._store.get(user_id)

    def save_settings(self, data, user_id):
        if self.raise_on_save:
            raise RuntimeError("DB save failure")
        # emulate persistence (copy)
        self._store[user_id] = dict(data)
        return True


# ------------------------------- Fixtures ------------------------------------

@pytest.fixture
def settings_manager(monkeypatch):
    """
    Instantiate SettingsManager with a FakeDB by monkeypatching
    engine.settings_manager.get_database_adapter. Also ensure lru_cache is
    cleared between tests.
    """
    from engine import settings_manager as smod

    fake_db = FakeDB()
    monkeypatch.setattr(smod, "get_database_adapter", lambda: fake_db, raising=True)

    mgr = smod.SettingsManager()  # this will call initialize_schema()
    assert fake_db._initialized is True

    yield mgr, fake_db

    # clear the lru_cache on the bound function to avoid cross-test pollution
    try:
        mgr.get_settings.cache_clear()
    except Exception:
        pass


# --------------------------------- Tests -------------------------------------

def test_bootstrap_defaults_when_global_missing(settings_manager):
    mgr, db = settings_manager

    # Initially DB has no global settings
    assert db.get_settings(None) is None

    # First call bootstraps defaults and returns them
    s = mgr.get_settings()
    assert s["version"] == mgr.CURRENT_VERSION
    assert s["llm_backend"] == "ollama"
    assert s["logging"]["file_level"] == "DEBUG"

    # DB should now hold global defaults
    persisted = db._store[None]
    assert persisted["llm_model"] == "llama3"

def test_lru_cache_hits_and_bust_on_save(settings_manager):
    mgr, db = settings_manager

    # Warm up (bootstraps)
    mgr.get_settings()
    first_calls = db.get_calls

    # Cached: repeated calls should NOT increment DB gets
    mgr.get_settings()
    mgr.get_settings()
    assert db.get_calls == first_calls  # cache hit

    # Saving should clear the cache; next get should hit DB again
    ok = mgr.save_settings({"llm_model": "llama3:instruct"})
    assert ok is True

    mgr.get_settings()
    assert db.get_calls == first_calls + 1  # cache miss after save -> DB hit

def test_user_overrides_merge_deep(settings_manager):
    mgr, db = settings_manager

    # Set global
    mgr.save_settings({
        "streaming": False,
        "logging": {"console_level": "INFO", "file_level": "DEBUG"}
    }, None)

    # Set user-specific overrides
    user_id = "alice"
    mgr.save_settings({
        "streaming": True,
        "logging": {"console_level": "WARNING"}  # deep-merge into logging
    }, user_id)

    # Get merged
    s_user = mgr.get_settings(user_id)
    assert s_user["streaming"] is True
    assert s_user["logging"]["console_level"] == "WARNING"
    # Deep-merge preserved global "file_level"
    assert s_user["logging"]["file_level"] == "DEBUG"

def test_version_is_injected_if_missing(settings_manager):
    mgr, db = settings_manager

    # Save globals without version explicitly
    mgr.save_settings({"llm_model": "llama3"}, None)

    # Save user settings without version
    uid = "bob"
    mgr.save_settings({"voice": True}, uid)

    g = mgr.get_settings(None)
    u = mgr.get_settings(uid)
    assert g["version"] == mgr.CURRENT_VERSION
    assert u["version"] == mgr.CURRENT_VERSION

def test_override_replaces_non_dict(settings_manager):
    mgr, db = settings_manager

    # Global has dict for 'logging'
    mgr.save_settings({"logging": {"console_level": "INFO"}}, None)
    # User overrides with non-dict should REPLACE
    uid = "carol"
    mgr.save_settings({"logging": "OFF"}, uid)

    combined = mgr.get_settings(uid)
    assert combined["logging"] == "OFF"  # dict replaced by string

def test_get_settings_db_error_returns_defaults(settings_manager, monkeypatch):
    mgr, db = settings_manager

    # Ensure defaults exist in DB first
    mgr.get_settings()
    # Now simulate DB get failure
    db.raise_on_get = True

    s = mgr.get_settings()  # should catch and return DEFAULT_SETTINGS copy
    assert s["llm_backend"] == mgr.DEFAULT_SETTINGS["llm_backend"]
    assert s is not mgr.DEFAULT_SETTINGS  # copy, not the same object

def test_save_settings_db_error_returns_false(settings_manager):
    mgr, db = settings_manager

    db.raise_on_save = True
    ok = mgr.save_settings({"llm_model": "anything"})
    assert ok is False
