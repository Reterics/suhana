import importlib
import types
import pytest

# Import module under test (assumes path engine/security/access_control.py)
acmod = importlib.import_module("engine.security.access_control")
AccessControlManager = acmod.AccessControlManager
Permission = acmod.Permission
Role = acmod.Role
DEFAULT_ROLE_PERMISSIONS = acmod.DEFAULT_ROLE_PERMISSIONS
get_access_control_manager = acmod.get_access_control_manager
permission_required = acmod.permission_required
resource_permission_required = acmod.resource_permission_required


@pytest.fixture(autouse=True)
def fresh_singleton():
    """
    Ensure each test starts with a fresh singleton to avoid cross-test contamination.
    """
    # reset singleton before & after test
    acmod._access_control_manager = None
    yield
    acmod._access_control_manager = None


@pytest.fixture
def acm():
    return AccessControlManager()


# ------------------------- Basic roles & auto-register ------------------------

def test_add_user_with_enum_role(acm):
    acm.add_user("alice", Role.ADMIN)
    assert acm.get_user_role("alice") == Role.ADMIN
    assert DEFAULT_ROLE_PERMISSIONS[Role.ADMIN] <= acm.get_user_permissions("alice")

def test_add_user_with_string_role_known(acm):
    acm.add_user("bob", "user")
    assert acm.get_user_role("bob") == Role.USER
    assert DEFAULT_ROLE_PERMISSIONS[Role.USER] <= acm.get_user_permissions("bob")

def test_add_user_with_string_role_invalid_falls_back_to_user(acm, caplog):
    acm.add_user("carol", "superhero")  # invalid -> USER
    assert acm.get_user_role("carol") == Role.USER
    assert DEFAULT_ROLE_PERMISSIONS[Role.USER] <= acm.get_user_permissions("carol")
    assert any("Invalid role" in r.message for r in caplog.records)

def test_get_user_permissions_auto_registers(acm):
    # unknown user -> auto-assign USER perms
    perms = acm.get_user_permissions("ghost")
    assert DEFAULT_ROLE_PERMISSIONS[Role.USER] <= perms
    assert acm.get_user_role("ghost") == Role.USER

def test_remove_user_clears_role_and_perms(acm):
    acm.add_user("dave", Role.USER)
    acm.remove_user("dave")
    assert acm.get_user_role("dave") is None
    # next fetch auto-registers again
    assert DEFAULT_ROLE_PERMISSIONS[Role.USER] <= acm.get_user_permissions("dave")


# ------------------------------ Owner vs All ---------------------------------

def test_check_permission_owner_mapping(acm):
    """
    If user is the resource owner and we're checking an 'ALL' permission,
    having the corresponding 'OWN' permission should also allow access.
    """
    acm.add_user("erin", Role.USER)
    # USER has VIEW_OWN_CONVERSATIONS but not VIEW_ALL_CONVERSATIONS
    assert Permission.VIEW_OWN_CONVERSATIONS in acm.get_user_permissions("erin")
    assert Permission.VIEW_ALL_CONVERSATIONS not in acm.get_user_permissions("erin")

    # As owner, checking ALL should pass due to mapping to OWN
    assert acm.check_permission("erin", Permission.VIEW_ALL_CONVERSATIONS, resource_owner_id="erin") is True
    # For a non-owner resource, it should fail
    assert acm.check_permission("erin", Permission.VIEW_ALL_CONVERSATIONS, resource_owner_id="someone") is False

def test_has_permission_exact_check(acm):
    acm.add_user("frank", Role.ADMIN)
    assert acm.has_permission("frank", Permission.MANAGE_PERMISSIONS) is True
    assert acm.has_permission("frank", Permission.CREATE_MEMORY) is True


# ------------------------------ Custom roles ---------------------------------

def test_create_and_assign_custom_role(acm):
    custom = {"power_user",}
    # give custom only VIEW_ALL_CONVERSATIONS
    acm.create_custom_role("power_user", {Permission.VIEW_ALL_CONVERSATIONS})

    # Assign via string (custom)
    acm.add_user("gina", "power_user")
    assert acm.get_user_role("gina") == "power_user"
    assert Permission.VIEW_ALL_CONVERSATIONS in acm.get_user_permissions("gina")
    assert Permission.MANAGE_USERS not in acm.get_user_permissions("gina")

def test_set_user_role_to_custom_then_delete_role_resets_to_user(acm):
    acm.create_custom_role("auditor", {Permission.VIEW_USERS, Permission.VIEW_ALL_CONVERSATIONS})
    acm.add_user("henry", "auditor")
    assert acm.get_user_role("henry") == "auditor"

    # Deleting the custom role should push affected users back to USER role
    acm.delete_custom_role("auditor")
    assert acm.get_user_role("henry") == Role.USER
    assert DEFAULT_ROLE_PERMISSIONS[Role.USER] <= acm.get_user_permissions("henry")


# ----------------------------- Add/remove perms ------------------------------

def test_add_and_remove_user_permission(acm):
    acm.add_user("ivy", Role.USER)
    # USER doesn't have MANAGE_USERS by default
    assert acm.has_permission("ivy", Permission.MANAGE_USERS) is False

    acm.add_user_permission("ivy", Permission.MANAGE_USERS)
    assert acm.has_permission("ivy", Permission.MANAGE_USERS) is True

    acm.remove_user_permission("ivy", Permission.MANAGE_USERS)
    assert acm.has_permission("ivy", Permission.MANAGE_USERS) is False


# ------------------------------- Decorators ----------------------------------

def test_permission_required_decorator_allows_when_has_perm(acm, monkeypatch):
    acmod._access_control_manager = acm
    acm.add_user("jack", Role.ADMIN)

    @permission_required(Permission.MANAGE_PERMISSIONS)
    def do_sensitive(user_id):
        return "ok"

    assert do_sensitive("jack") == "ok"

def test_permission_required_decorator_blocks_when_missing(acm, monkeypatch):
    acmod._access_control_manager = acm
    acm.add_user("kate", Role.USER)

    @permission_required(Permission.MANAGE_PERMISSIONS)
    def do_sensitive(user_id):
        return "ok"

    with pytest.raises(PermissionError):
        do_sensitive("kate")

def test_resource_permission_required_decorator_uses_owner_mapping(acm, monkeypatch):
    acmod._access_control_manager = acm
    acm.add_user("liam", Role.USER)  # has VIEW_OWN_CONVERSATIONS

    @resource_permission_required(Permission.VIEW_ALL_CONVERSATIONS, resource_owner_id_arg="owner")
    def view_conv(user_id, *, owner):
        return "ok"

    # As owner -> allowed (OWN maps to ALL for owner)
    assert view_conv("liam", owner="liam") == "ok"

    # Not owner -> blocked
    with pytest.raises(PermissionError):
        view_conv("liam", owner="other")


# ----------------------------- Save / Load DB --------------------------------

class FakeDB:
    def __init__(self):
        self.saved = None
        self.raise_on_save = False
        self.raise_on_load = False

    def save_access_control(self, data):
        if self.raise_on_save:
            raise RuntimeError("save failed")
        # emulate persistence (copy)
        self.saved = {
            "user_roles": dict(data["user_roles"]),
            "user_permissions": {k: list(v) for k, v in data["user_permissions"].items()},
            "custom_roles": {k: list(v) for k, v in data["custom_roles"].items()},
        }
        return True

    def load_access_control(self):
        if self.raise_on_load:
            raise RuntimeError("load failed")
        return self.saved


def test_save_and_load_roundtrip(acm):
    db = FakeDB()

    # setup: one admin, one user with added perm, one custom role
    acm.add_user("admin1", Role.ADMIN)
    acm.add_user("user1", Role.USER)
    acm.add_user_permission("user1", Permission.MANAGE_USERS)
    acm.create_custom_role("auditor", {Permission.VIEW_USERS})
    acm.add_user("aud1", "auditor")

    assert acm.save_to_database(db) is True

    # New manager loads from DB
    acm2 = AccessControlManager()
    assert acm2.load_from_database(db) is True

    assert acm2.get_user_role("admin1") == Role.ADMIN
    assert Role.USER == acm2.get_user_role("user1")
    assert acm2.has_permission("user1", Permission.MANAGE_USERS) is True
    assert acm2.get_user_role("aud1") == "auditor"
    assert acm2.has_permission("aud1", Permission.VIEW_USERS) is True

def test_save_to_database_handles_exception(acm):
    db = FakeDB()
    db.raise_on_save = True
    assert acm.save_to_database(db) is False  # graceful failure

def test_load_from_database_handles_missing_and_exception(acm):
    db = FakeDB()
    # No data saved yet -> returns False
    assert acm.load_from_database(db) is False

    db.raise_on_load = True
    assert acm.load_from_database(db) is False  # graceful failure


# ------------------------------- Singleton -----------------------------------

def test_singleton_returns_same_instance():
    m1 = get_access_control_manager()
    m2 = get_access_control_manager()
    assert m1 is m2

def test_singleton_is_isolated_by_fixture():
    # fixture resets singleton; ensure new instance here differs from previous test
    m1 = get_access_control_manager()
    acmod._access_control_manager = None
    m2 = get_access_control_manager()
    assert m1 is not m2
