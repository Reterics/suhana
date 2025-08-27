import json
import types
from datetime import datetime, timedelta
import sys
import pytest

# ---- Fakes / test doubles ----------------------------------------------------

class FakeDB:
    """In-memory DatabaseAdapter-compatible fake."""
    def __init__(self):
        self.users = {}  # id -> user dict
        self._initialized = False

    # API expected by UserManager
    def initialize_schema(self):
        self._initialized = True

    def create_user(self, user_data: dict):
        uid = user_data["id"]
        if uid in self.users:
            return None
        # emulate DB persistence (store shallow copy)
        self.users[uid] = dict(user_data)
        return uid

    def get_user(self, user_id: str):
        u = self.users.get(user_id)
        if not u:
            return None
        # emulate DB row return (dict)
        return dict(u)

    def update_user(self, user_id: str, updates: dict):
        if user_id not in self.users:
            return False
        self.users[user_id].update(updates)
        return True

    def delete_user(self, user_id: str):
        return self.users.pop(user_id, None) is not None

    def list_users(self):
        # emulate DB list of rows
        return [dict(v) for v in self.users.values()]

class FakeSettingsManager:
    def __init__(self):
        self.saved = {}
    def save_settings(self, data, username=None):
        self.saved[username or "_global"] = data
        return True

class FakeACM:
    def __init__(self):
        self.added = []
    def add_user(self, username, role):
        self.added.append((username, role))

# ---- Fixtures / patching -----------------------------------------------------

@pytest.fixture
def patch_access_control(monkeypatch):
    """
    Create a fake module 'engine.security.access_control' with get_access_control_manager()
    so 'from engine.security.access_control import get_access_control_manager' works.
    """
    mod = types.ModuleType("engine.security.access_control")
    acm = FakeACM()
    def get_access_control_manager():
        return acm
    mod.get_access_control_manager = get_access_control_manager

    # ensure package parents exist
    pkg_engine = sys.modules.setdefault("engine", types.ModuleType("engine"))
    pkg_engine_security = sys.modules.setdefault("engine.security", types.ModuleType("engine.security"))
    sys.modules["engine.security.access_control"] = mod
    yield acm
    # (We leave modules in sys.modules; harmless for test run.)

@pytest.fixture
def user_manager(monkeypatch):
    # Import the module under test after patching its dependencies.
    import importlib
    # Patch dependencies visible from engine.user_manager
    from engine import user_manager as umod

    # Patch SettingsManager and get_database_adapter
    monkeypatch.setattr(umod, "SettingsManager", FakeSettingsManager, raising=True)

    fake_db = FakeDB()
    monkeypatch.setattr(umod, "get_database_adapter", lambda: fake_db, raising=True)

    # Recreate instance now that patches applied
    mgr = umod.UserManager()
    # Sanity: schema init happened
    assert fake_db._initialized is True
    mgr._test_db = fake_db  # expose for assertions
    return mgr

# ---- Helpers -----------------------------------------------------------------

def extract_profile(urow):
    prof = urow["profile"]
    return json.loads(prof) if isinstance(prof, str) else prof

# ---- Tests: user creation ----------------------------------------------------

def test_create_user_success(user_manager, patch_access_control):
    ok, msg = user_manager.create_user("alice_1", "secret", name="Alice", role="admin")
    assert ok
    assert "created successfully" in msg

    row = user_manager._test_db.get_user("alice_1")
    assert row is not None
    prof = extract_profile(row)
    assert prof["name"] == "Alice"
    assert prof["role"] == "admin"
    assert "salt" in row and len(row["salt"]) >= 32
    # settings saved
    assert user_manager.settings_manager.saved["alice_1"]["version"] == 1

def test_create_user_invalid_username(user_manager):
    ok, msg = user_manager.create_user("bad name!", "pw")
    assert not ok
    assert "Username must contain only letters" in msg

def test_create_guest_privacy_defaults_hardened(user_manager):
    ok, _ = user_manager.create_user("visitor", "pw", role="guest")
    assert ok
    row = user_manager._test_db.get_user("visitor")
    prof = extract_profile(row)
    assert prof["role"] == "guest"
    assert prof["privacy"]["store_history"] is False
    assert prof["privacy"]["allow_analytics"] is False

# ---- Auth / session ----------------------------------------------------------

def test_authenticate_success_and_session(user_manager):
    user_manager.create_user("bob", "hunter2")
    ok, token = user_manager.authenticate("bob", "hunter2")
    assert ok and token
    # validate session
    assert user_manager.validate_session(token) == "bob"

def test_authenticate_wrong_password(user_manager):
    user_manager.create_user("carol", "goodpw")
    ok, token = user_manager.authenticate("carol", "badpw")
    assert not ok and token is None

def test_authenticate_no_user(user_manager):
    ok, token = user_manager.authenticate("nouser", "x")
    assert not ok and token is None

def test_validate_session_expired(user_manager):
    user_manager.create_user("dave", "pw")
    ok, token = user_manager.authenticate("dave", "pw")
    assert ok and token
    # force expire
    user_manager._sessions[token]["expires"] = (datetime.now() - timedelta(seconds=1)).isoformat()
    assert user_manager.validate_session(token) is None
    # token removed
    assert token not in user_manager._sessions

def test_logout(user_manager):
    user_manager.create_user("eva", "pw")
    ok, token = user_manager.authenticate("eva", "pw")
    assert ok
    assert user_manager.logout(token) is True
    assert user_manager.validate_session(token) is None
    # logging out again -> False
    assert user_manager.logout(token) is False

# ---- Profile CRUD ------------------------------------------------------------

def test_get_profile_roundtrip(user_manager):
    user_manager.create_user("frank", "pw", name="Frank")
    prof = user_manager.get_profile("frank")
    assert prof["name"] == "Frank"
    # stored as json string in DB
    row = user_manager._test_db.get_user("frank")
    assert isinstance(row["profile"], str)

def test_save_profile_injects_missing_sections(user_manager):
    user_manager.create_user("gina", "pw")
    # save a minimal profile
    profile = {"name": "Gina"}  # missing preferences/personalization/privacy
    assert user_manager.save_profile("gina", profile) is True
    prof = user_manager.get_profile("gina")
    for section in ["preferences", "personalization", "privacy"]:
        assert section in prof

# ---- List / delete users -----------------------------------------------------

def test_list_users_formats_fields(user_manager):
    user_manager.create_user("u1", "pw", name="U1", role="user")
    user_manager.create_user("u2", "pw", name="U2", role="admin")
    users = user_manager.list_users()
    names = {u["name"] for u in users}
    roles = {u["role"] for u in users}
    assert {"U1", "U2"} <= names
    assert {"user", "admin"} <= roles
    # has created_at
    assert all("created_at" in u for u in users)

def test_delete_user_removes_sessions(user_manager):
    user_manager.create_user("hank", "pw")
    ok, token = user_manager.authenticate("hank", "pw")
    assert ok and token in user_manager._sessions
    assert user_manager.delete_user("hank") is True
    assert token not in user_manager._sessions
    assert user_manager._test_db.get_user("hank") is None

# ---- Password change ---------------------------------------------------------

def test_change_password_success(user_manager):
    user_manager.create_user("ivy", "oldpw")
    ok, msg = user_manager.change_password("ivy", "oldpw", "newpw")
    assert ok and "successfully" in msg
    # old no longer works; new works
    assert user_manager.authenticate("ivy", "oldpw")[0] is False
    assert user_manager.authenticate("ivy", "newpw")[0] is True

def test_change_password_wrong_current(user_manager):
    user_manager.create_user("jack", "pw")
    ok, msg = user_manager.change_password("jack", "WRONG", "npw")
    assert not ok and "Current password is incorrect" in msg

def test_change_password_user_not_found(user_manager):
    ok, msg = user_manager.change_password("missing", "x", "y")
    assert not ok and "User not found" in msg

# ---- Avatar & typed section helpers -----------------------------------------

def test_set_and_get_avatar(user_manager):
    user_manager.create_user("kate", "pw")
    assert user_manager.set_avatar("kate", "/path/to/avatar.png") is True
    assert user_manager.get_avatar("kate") == "/path/to/avatar.png"

def test_preferences_personalization_privacy_helpers(user_manager):
    user_manager.create_user("leo", "pw")
    assert user_manager.update_preferences("leo", {"theme": "dark"}) is True
    assert user_manager.get_preferences("leo")["theme"] == "dark"

    assert user_manager.update_personalization("leo", {"favorite_tools": ["x"]}) is True
    assert "x" in user_manager.get_personalization("leo")["favorite_tools"]

    assert user_manager.update_privacy_settings("leo", {"store_history": False}) is True
    assert user_manager.get_privacy_settings("leo")["store_history"] is False

# ---- Interests list ops ------------------------------------------------------

def test_add_interest_creates_sections_and_is_idempotent(user_manager):
    user_manager.create_user("mia", "pw")
    assert user_manager.add_interest("mia", "python") is True
    # add again -> still True and not duplicated
    assert user_manager.add_interest("mia", "python") is True
    prof = user_manager.get_profile("mia")
    assert prof["personalization"]["interests"] == ["python"]

def test_remove_interest_missing_sections_is_noop(user_manager):
    user_manager.create_user("nick", "pw")
    # set profile without personalization to simulate missing sections
    row = user_manager._test_db.get_user("nick")
    prof = extract_profile(row)
    prof.pop("personalization", None)
    user_manager.save_profile("nick", prof)
    # removing non-existing interest should be True (noop)
    assert user_manager.remove_interest("nick", "ml") is True

def test_remove_interest_existing(user_manager):
    user_manager.create_user("olga", "pw")
    user_manager.add_interest("olga", "ai")
    assert user_manager.remove_interest("olga", "ai") is True
    prof = user_manager.get_profile("olga")
    assert "ai" not in prof["personalization"]["interests"]
