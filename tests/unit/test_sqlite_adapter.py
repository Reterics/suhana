import json
from pathlib import Path
import uuid
import pytest

# Target under test
from engine.database.sqlite import SQLiteAdapter, Document


class DummyEmbeddings:
    def __init__(self, *args, **kwargs):
        pass

    def embed_documents(self, texts):
        # Return a deterministic vector size based on text length
        return [[float(len(t))] for t in texts]

    def embed_query(self, text):
        return [float(len(text))]


class DummyFAISS:
    def __init__(self, documents):
        self.documents = documents

    @classmethod
    def from_documents(cls, documents, embeddings):
        # Just hold onto the docs; ignore embeddings
        return cls(documents)

    def save_local(self, path):
        # Simulate saving an index by writing a tiny file
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("index")

    @classmethod
    def load_local(cls, path, embeddings):
        # Pretend to load an index; return instance with a placeholder doc
        return cls([Document(page_content="loaded", metadata={"id": "loaded-id"})])

    def similarity_search_with_score(self, query, k=1):
        # Always return a single match with low score (best)
        return [(Document(page_content="match", metadata={}), 0.1)]


@pytest.fixture()
def sqlite_adapter(tmp_path, monkeypatch):
    # Patch heavy deps in the module under test
    import engine.database.sqlite as mod
    import engine.security.access_control as acl
    import engine.security.database_access as dbacc

    # Allow all permissions in tests (patch both access points)
    allow = lambda *args, **kwargs: True
    monkeypatch.setattr(acl, "check_permission", allow)
    monkeypatch.setattr(dbacc, "check_permission", allow)

    # Replace vector store and embeddings with light stubs
    monkeypatch.setattr(mod, "FAISS", DummyFAISS)
    monkeypatch.setattr(mod, "HuggingFaceEmbeddings", DummyEmbeddings)

    db_file = tmp_path / "unit_test.db"
    adapter = SQLiteAdapter(str(db_file))
    assert adapter.connect()
    assert adapter.initialize_schema()

    yield adapter

    adapter.disconnect()


def _create_user(adapter: SQLiteAdapter, user_id: str = None):
    if user_id is None:
        user_id = str(uuid.uuid4())
    data = {
        "id": user_id,
        "username": f"user_{user_id[:8]}",
        "created_at": "2025-01-01T00:00:00",
        "profile": {"name": "Test", "prefs": {"a": 1}},
    }
    created_id = adapter.create_user(data)
    assert created_id == user_id
    return user_id


def test_user_crud_and_settings(sqlite_adapter: SQLiteAdapter):
    user_id = _create_user(sqlite_adapter)

    # get_user returns profile as dict
    u = sqlite_adapter.get_user(user_id)
    assert u is not None
    assert u["id"] == user_id
    assert isinstance(u["profile"], dict)
    assert u["profile"]["name"] == "Test"

    # list_users finds our user
    users = sqlite_adapter.list_users()
    assert any(x["id"] == user_id for x in users)

    # update_user with username and profile string-json
    new_username = "renamed"
    new_profile = {"name": "Renamed"}
    ok = sqlite_adapter.update_user(user_id, {"username": new_username, "profile": json.dumps(new_profile)})
    assert ok
    u2 = sqlite_adapter.get_user(user_id)
    assert u2["username"] == new_username
    assert u2["profile"]["name"] == "Renamed"

    # settings: global and per-user
    assert sqlite_adapter.get_settings() == {}
    assert sqlite_adapter.save_settings({"theme": "dark"})
    assert sqlite_adapter.get_settings() == {"theme": "dark"}

    assert sqlite_adapter.get_settings(user_id) == {}
    assert sqlite_adapter.save_settings({"volume": 7}, user_id)
    assert sqlite_adapter.get_settings(user_id) == {"volume": 7}

    # delete user
    assert sqlite_adapter.delete_user(user_id)


def test_conversation_save_load_and_meta(sqlite_adapter: SQLiteAdapter):
    user_id = _create_user(sqlite_adapter)
    conv_id = str(uuid.uuid4())

    # Provide placeholder title to trigger derivation from first user message
    data = {
        "title": "New Conversation",
        "category": "General",
        "tags": ["t1", "t2"],
        "history": [
            {"role": "user", "content": "  Hello   world!  ", "meta": {"x": 1}},
            {"role": "assistant", "content": "Hi!"},
            {"role": "user", "content": "Another"},
        ],
    }

    ok = sqlite_adapter.save_conversation(user_id, conv_id, data)
    assert ok

    loaded = sqlite_adapter.load_conversation(user_id, conv_id)
    assert loaded is not None
    # Title should be derived from first user message (normalized whitespace)
    assert loaded["title"] == "Hello world!"
    assert loaded["category"] == "General"
    assert loaded["tags"] == ["t1", "t2"]
    # History order and fields
    assert [m["role"] for m in loaded["history"]] == ["user", "assistant", "user"]
    assert loaded["history"][0]["content"] == "  Hello   world!  "
    assert loaded["history"][0]["meta"] == {"x": 1}

    # list_conversations and meta
    ids = sqlite_adapter.list_conversations(user_id)
    assert conv_id in ids
    meta_list = sqlite_adapter.list_conversation_meta(user_id)
    assert any(m["id"] == conv_id and m["category"] == "General" for m in meta_list)

    # Move to a new category
    assert sqlite_adapter.move_conversation_to_category(user_id, conv_id, "Work")
    meta_list2 = sqlite_adapter.list_conversation_meta(user_id, category="Work")
    assert any(m["id"] == conv_id for m in meta_list2)


def test_create_new_conversation(sqlite_adapter: SQLiteAdapter):
    user_id = _create_user(sqlite_adapter)
    new_id = sqlite_adapter.create_new_conversation(user_id)
    assert isinstance(new_id, str) and new_id
    loaded = sqlite_adapter.load_conversation(user_id, new_id)
    assert loaded is not None
    assert loaded["history"] == []


def test_save_conversation_invalid_history_raises(sqlite_adapter: SQLiteAdapter):
    user_id = _create_user(sqlite_adapter)
    conv_id = str(uuid.uuid4())
    data = {
        "title": "x",
        "history": "not-a-list",
        "messages": "also-not-a-list",
    }
    with pytest.raises(ValueError):
        sqlite_adapter.save_conversation(user_id, conv_id, data)


def test_memory_add_search_forget_clear(sqlite_adapter: SQLiteAdapter, tmp_path):
    user_id = _create_user(sqlite_adapter)

    # Add a private memory fact
    ok = sqlite_adapter.add_memory_fact(user_id, "Buy milk tomorrow", private=True)
    assert ok

    # Vectorstore path should exist under vectorstore/<user_id>
    vec_dir = Path(sqlite_adapter.db_path).parent / "vectorstore" / user_id
    assert vec_dir.exists()
    # There should be exactly one .faiss file
    files = list(vec_dir.glob("*.faiss"))
    assert len(files) == 1

    # Search returns one result with a score
    results = sqlite_adapter.search_memory("milk", user_id=user_id, include_shared=False, k=3)
    assert isinstance(results, list)
    assert len(results) >= 1
    assert results[0]["text"].startswith("Buy milk")
    assert isinstance(results[0]["score"], float)

    # Forget by keyword removes it (and the file)
    n = sqlite_adapter.forget_memory("milk", user_id=user_id, forget_shared=False)
    assert n >= 1
    # Files for that user get deleted (at least the one we created)
    files_after = list(vec_dir.glob("*.faiss"))
    assert len(files_after) == 0

    # Add two public (shared) facts and clear shared
    ok1 = sqlite_adapter.add_memory_fact(None, "Shared tip one", private=False)
    ok2 = sqlite_adapter.add_memory_fact(None, "Shared tip two", private=False)
    assert ok1 and ok2

    shared_dir = Path(sqlite_adapter.db_path).parent / "vectorstore" / "shared"
    assert shared_dir.exists()
    assert len(list(shared_dir.glob("*.faiss"))) == 2

    # Clear shared memory (passing None means system/all)
    cleared = sqlite_adapter.clear_memory(user_id=None, clear_shared=True)
    assert cleared >= 2
    assert len(list(shared_dir.glob("*.faiss"))) == 0

def test_categories_and_delete_conversation(sqlite_adapter: SQLiteAdapter):
    user_id = _create_user(sqlite_adapter)

    # Initially, no categories
    assert sqlite_adapter.list_categories(user_id) == []

    # Create a category explicitly
    assert sqlite_adapter.create_category(user_id, "Ideas")
    assert sqlite_adapter.list_categories(user_id) == ["Ideas"]

    # Creating the same category again is a no-op success
    assert sqlite_adapter.create_category(user_id, "Ideas")
    assert sqlite_adapter.list_categories(user_id) == ["Ideas"]

    # Create conversation and then delete it
    conv_id = sqlite_adapter.create_new_conversation(user_id, title="Tmp", category="Ideas")
    ids = sqlite_adapter.list_conversations(user_id, category="Ideas")
    assert conv_id in ids
    assert sqlite_adapter.delete_conversation(user_id, conv_id)
    ids_after = sqlite_adapter.list_conversations(user_id)
    assert conv_id not in ids_after


def test_api_key_lifecycle(sqlite_adapter: SQLiteAdapter):
    user_id = _create_user(sqlite_adapter)

    key = "k-" + uuid.uuid4().hex
    # Create with custom name, rate limit and permissions
    ok = sqlite_adapter.create_api_key(user_id, key, name="CI", rate_limit=120, permissions=["read", "write"])
    assert ok

    # Read back the key
    info = sqlite_adapter.get_api_key(key)
    assert info is not None
    assert info["user_id"] == user_id
    assert info["name"] == "CI"
    assert info["rate_limit"] == 120
    assert info["permissions"] == ["read", "write"]
    assert info["active"] is True

    # List keys for user
    keys = sqlite_adapter.get_user_api_keys(user_id)
    assert any(k["key"] == key for k in keys)

    # Update usage and then revoke
    assert sqlite_adapter.update_api_key_usage(key)
    # After usage, usage_count should be >= 1 and last_used set
    info2 = sqlite_adapter.get_api_key(key)
    assert isinstance(info2["usage_count"], int) and info2["usage_count"] >= 1
    assert isinstance(info2["last_used"], str) and len(info2["last_used"]) >= 10

    assert sqlite_adapter.revoke_api_key(key)
    info3 = sqlite_adapter.get_api_key(key)
    assert info3["active"] is False

    # Usage stats for all users and for a specific user
    stats_all = sqlite_adapter.get_api_key_usage_stats()
    assert any(s["key"] == key for s in stats_all)
    stats_user = sqlite_adapter.get_api_key_usage_stats(user_id)
    assert any(s["key"] == key for s in stats_user)


def test_migrate_from_files(sqlite_adapter: SQLiteAdapter, tmp_path: Path):
    base = tmp_path / "fs"
    users_dir = base / "users"
    u1 = users_dir / "u1"
    (u1 / "conversations").mkdir(parents=True)

    # Global settings
    (base / "settings.json").write_text(json.dumps({"g": 1}), encoding="utf-8")

    # User profile and settings
    (u1 / "profile.json").write_text(json.dumps({"name": "Alice"}), encoding="utf-8")
    (u1 / "settings.json").write_text(json.dumps({"s": 2}), encoding="utf-8")

    # One conversation
    conv_id = "c-001"
    conversation = {"title": "Hello", "history": [{"role": "user", "content": "hi"}]}
    (u1 / "conversations" / f"{conv_id}.json").write_text(json.dumps(conversation), encoding="utf-8")

    users_m, convs_m, settings_m = sqlite_adapter.migrate_from_files(base)

    # Validate counts
    assert users_m >= 1
    assert convs_m >= 1
    assert settings_m >= 2  # global + user settings

    # Validate data presence
    user = sqlite_adapter.get_user("u1")
    assert user is not None and user["username"] == "Alice"
    loaded = sqlite_adapter.load_conversation("u1", conv_id)
    assert loaded is not None and loaded["title"] == "Hello"
    assert sqlite_adapter.get_settings() == {"g": 1}
    assert sqlite_adapter.get_settings("u1") == {"s": 2}
