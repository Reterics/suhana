import sys
import types
import json
from datetime import datetime
from pathlib import Path

import pytest

ASCENDING = 1

class FakeCollection:
    def __init__(self):
        self.docs = []
        self.indexes = []
    def create_index(self, *args, **kwargs):
        self.indexes.append((args, kwargs))
        return "idx"
    def find_one(self, query, projection=None):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                if projection:
                    return {k: doc.get(k) for k in projection.keys()}
                return doc.copy()
        return None
    def find(self, query=None, projection=None):
        query = query or {}
        results = [d.copy() for d in self.docs if all(d.get(k) == v for k, v in query.items())]
        class _Cursor(list):
            def sort(self, key, direction):
                super().sort(key=lambda x: (x.get(key) is None, (x.get(key) if x.get(key) is not None else "")), reverse=(direction == -1))
                return self
        if projection:
            results = [{k: d.get(k) for k in projection.keys()} for d in results]
        return _Cursor(results)
    def insert_one(self, doc):
        self.docs.append(doc.copy())
        return types.SimpleNamespace(inserted_id=doc.get("id") or doc.get("key") or True)
    def insert_many(self, docs):
        for d in docs:
            self.docs.append(d.copy())
        return types.SimpleNamespace(inserted_ids=[d.get("id") for d in docs])
    def update_one(self, query, update):
        matched = 0
        modified = 0
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                matched += 1
                if "$set" in update:
                    doc.update(update["$set"])
                if "$inc" in update:
                    for k, v in update["$inc"].items():
                        doc[k] = doc.get(k, 0) + v
                modified += 1
        return types.SimpleNamespace(matched_count=matched, modified_count=modified)
    def delete_one(self, query):
        before = len(self.docs)
        self.docs = [d for d in self.docs if not all(d.get(k) == v for k, v in query.items())]
        return types.SimpleNamespace(deleted_count=before - len(self.docs))
    def delete_many(self, query):
        before = len(self.docs)
        self.docs = [d for d in self.docs if not all(d.get(k) == v for k, v in query.items())]
        return types.SimpleNamespace(deleted_count=before - len(self.docs))
    def aggregate(self, pipeline):
        # minimal: emulate pipeline used in list_conversation_meta
        # We'll just join category name where possible and project fields
        data = []
        # Build a quick index of categories by id if present in db wrapper
        return []

class FakeDB:
    def __init__(self):
        self._collections = {}
    def list_collection_names(self):
        return list(self._collections.keys())
    def create_collection(self, name):
        self._collections[name] = FakeCollection()
        return self._collections[name]
    def __getattr__(self, item):
        if item not in self._collections:
            self._collections[item] = FakeCollection()
        return self._collections[item]
    def __getitem__(self, name):
        return getattr(self, name)

class FakeAdmin:
    def command(self, name):
        return {"ok": 1}

class FakeMongoClient:
    def __init__(self, *args, **kwargs):
        self._dbs = {}
        self.admin = FakeAdmin()
    def __getitem__(self, name):
        if name not in self._dbs:
            self._dbs[name] = FakeDB()
        return self._dbs[name]
    def close(self):
        pass

class FakePymongo(types.ModuleType):
    def __init__(self):
        super().__init__("pymongo")
        self.MongoClient = FakeMongoClient
        self.ASCENDING = ASCENDING
        self.DESCENDING = -1

def install_pymongo_stub():
    fake = FakePymongo()
    sys.modules["pymongo"] = fake
    # Also stub bson.objectid for adapter import safety
    mod = types.ModuleType("bson")
    class _OID(str):
        pass
    sub = types.ModuleType("bson.objectid")
    sub.ObjectId = _OID
    mod.objectid = sub
    sys.modules["bson"] = mod
    sys.modules["bson.objectid"] = sub
    return fake

# Vector store/embeddings stubs
class DummyEmbeddings:
    pass

class DummyVectorStore:
    def __init__(self, docs=None):
        self.docs = docs or []
    def save_local(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text("stub")
    def similarity_search_with_score(self, query, k=1):
        from langchain_core.documents import Document as _Doc
        return [(_Doc(page_content="stub", metadata={}), 0.1)]

class DummyFAISS:
    @staticmethod
    def from_documents(documents, embeddings):
        return DummyVectorStore(documents)
    @staticmethod
    def load_local(path, embeddings):
        return DummyVectorStore()

@pytest.fixture(autouse=True)
def stub_env(monkeypatch, tmp_path):
    install_pymongo_stub()
    # Patch FAISS and HF embeddings used inside adapter
    import importlib
    import engine.database.mongodb as m
    importlib.reload(m)
    monkeypatch.setattr(m, 'FAISS', DummyFAISS)
    class _Emb:
        def __init__(self, *a, **k):
            pass
    monkeypatch.setattr(m, 'HuggingFaceEmbeddings', _Emb)
    # Ensure vectorstore path is inside tmp
    monkeypatch.chdir(tmp_path)
    yield

@pytest.fixture
def adapter():
    from engine.database.mongodb import MongoDBAdapter
    a = MongoDBAdapter(connection_string="mongodb://stub", database_name="db")
    assert a.connect() is True
    assert a.initialize_schema() is True
    return a

# ---- Tests covering MongoDBAdapter ----

def test_connect_and_disconnect(adapter):
    assert adapter.db is not None
    assert adapter.disconnect() is True


def test_initialize_schema_creates_collections_and_indexes(adapter):
    db = adapter.db
    for name in ["users", "settings", "categories", "conversations", "conversation_messages", "memory_facts", "api_keys"]:
        assert name in db.list_collection_names()
    # sanity check some indexes
    assert any(idx for idx in db.users.indexes)
    assert any(idx for idx in db.api_keys.indexes)


def test_user_crud(adapter):
    uid = adapter.create_user({"id": "u1", "username": "alice", "profile": {"p": 1}})
    assert uid == "u1"
    u = adapter.get_user("u1")
    assert u and u["username"] == "alice"
    ok = adapter.update_user("u1", {"last_login": "now", "profile": {"p": 2}})
    assert ok is True
    users = adapter.list_users()
    assert any(x["id"] == "u1" for x in users)
    ok2 = adapter.delete_user("u1")
    assert ok2 is True


def test_settings_get_and_save(adapter):
    assert adapter.get_settings() == {}
    assert adapter.save_settings({"a": 1}) is True
    assert adapter.get_settings() == {"a": 1}
    # user specific
    assert adapter.save_settings({"b": 2}, user_id="u1") is True
    assert adapter.get_settings("u1") == {"b": 2}


def test_category_list_create_and_move(adapter):
    # create categories and list
    assert adapter.create_category("u1", "General") is True
    assert adapter.create_category("u1", "Work") is True
    cats = adapter.list_categories("u1")
    assert cats == sorted(cats)
    # create conversation in General then move to Work
    cid = "c1"
    data = {
        "title": "Untitled Conversation",
        "category": "General",
        "messages": [
            {"role": "user", "content": "Plan a trip"},
            {"role": "assistant", "content": "Okay"},
        ],
    }
    assert adapter.save_conversation("u1", cid, data) is True
    assert adapter.move_conversation_to_category("u1", cid, "Work") is True


def test_list_conversations_and_meta(adapter):
    adapter.create_category("u1", "General")
    adapter.save_conversation("u1", "c2", {"title": "New Conversation", "category": "General", "messages": []})
    adapter.save_conversation("u1", "c3", {"title": "", "category": "General", "history": [{"role": "user", "content": "Hello world"}]})
    ids = adapter.list_conversations("u1")
    assert set(ids) >= {"c2", "c3"}
    meta = adapter.list_conversation_meta("u1")
    assert isinstance(meta, list)
    # With non-existent category, list_conversations returns empty list
    none_ids = adapter.list_conversations("u1", category="DoesNotExist")
    assert none_ids == []


def test_migrate_from_files(adapter, tmp_path: Path):
    base = tmp_path / "fs"
    users_dir = base / "users" / "u1"
    (users_dir / "conversations").mkdir(parents=True)
    # Global settings
    (base / "settings.json").write_text(json.dumps({"g": 1}), encoding="utf-8")
    # User profile and settings
    (users_dir / "profile.json").write_text(json.dumps({"name": "Alice"}), encoding="utf-8")
    (users_dir / "settings.json").write_text(json.dumps({"s": 2}), encoding="utf-8")
    # One conversation
    conv_id = "c-001"
    conversation = {"title": "Hello", "history": [{"role": "user", "content": "hi"}]}
    (users_dir / "conversations" / f"{conv_id}.json").write_text(json.dumps(conversation), encoding="utf-8")

    users_m, convs_m, settings_m = adapter.migrate_from_files(base)
    assert users_m >= 1 and convs_m >= 1 and settings_m >= 2
    # Validate data presence
    user = adapter.get_user("u1")
    assert user is not None and user["username"] == "Alice"
    loaded = adapter.load_conversation("u1", conv_id)
    assert loaded is not None and loaded["title"] == "Hello"
    assert adapter.get_settings() == {"g": 1}
    assert adapter.get_settings("u1") == {"s": 2}


def test_save_and_load_conversation_including_legacy(adapter):
    adapter.create_category("u1", "General")
    cid = "c100"
    data = {
        "title": "Untitled Conversation",
        "category": "General",
        "tags": ["x"],
        "starred": True,
        "archived": False,
        "messages": [
            {"role": "user", "content": "Make a plan", "meta": {"k": 1}},
            {"role": "assistant", "content": "Sure"},
        ],
    }
    assert adapter.save_conversation("u1", cid, data) is True
    res = adapter.load_conversation("u1", cid)
    assert res and res["title"] and res["history"][0]["role"] == "user"
    # Legacy blob fallback: write a conversation with only data blob and no normalized messages
    adapter.db.conversations.insert_one({
        "id": "legacy1",
        "user_id": "u1",
        "category_id": adapter.db.categories.find_one({"user_id": "u1", "name": "General"})["id"],
        "title": "Legacy",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "starred": False,
        "archived": False,
        "tags": [],
        "data": json.dumps({"history": [{"role": "user", "content": "legacy"}]})
    })
    legacy = adapter.load_conversation("u1", "legacy1")
    assert legacy and legacy["history"] and legacy["history"][0]["content"] == "legacy"


def test_create_new_and_delete_conversation(adapter):
    adapter.create_category("u2", "General")
    cid = adapter.create_new_conversation("u2")
    assert isinstance(cid, str) and cid
    assert adapter.delete_conversation("u2", cid) is True


def test_save_conversation_invalid_messages_returns_false(adapter):
    # history/messages is not a list -> ValueError inside adapter, should return False
    adapter.create_category("u3", "General")
    bad = {"title": "T", "category": "General", "history": {"x": 1}, "messages": "still-bad"}
    ok = adapter.save_conversation("u3", "bad1", bad)
    assert ok is False


def test_update_user_noop_returns_true(adapter):
    # If no updatable fields are provided, method returns True (no-op)
    assert adapter.update_user("does-not-matter", {}) is True


def test_memory_add_search_forget_clear(adapter, tmp_path):
    # Initially, searching with no facts returns empty list
    assert adapter.search_memory("anything", user_id="u1") == []
    # Add shared (non-private) memory for global search
    ok = adapter.add_memory_fact(None, "The sky is blue", private=False)
    assert ok is True
    # Add private memory for user
    ok2 = adapter.add_memory_fact("u1", "Alice likes tea", private=True)
    assert ok2 is True
    # Search: user should see both private and shared by default
    results = adapter.search_memory("tea", user_id="u1", include_shared=True, k=3)
    assert isinstance(results, list)
    # Forget: remove entries with keyword
    n = adapter.forget_memory("tea", user_id="u1")
    assert isinstance(n, int)
    # Clear shared
    n2 = adapter.clear_memory(user_id=None, clear_shared=True)
    assert isinstance(n2, int)


def test_api_keys_full_flow(adapter):
    # Need a user for usage stats username join
    adapter.create_user({"id": "u1", "username": "alice"})
    # create
    ok = adapter.create_api_key("u1", key="K1", name="dev", rate_limit=120, permissions=["user", "admin"])
    assert ok is True
    # get
    kdoc = adapter.get_api_key("K1")
    assert kdoc and kdoc["active"] is True and "permissions" in kdoc
    # list for user
    keys = adapter.get_user_api_keys("u1")
    assert len(keys) == 1
    # usage update
    ok2 = adapter.update_api_key_usage("K1")
    assert ok2 is True
    kdoc2 = adapter.get_api_key("K1")
    assert kdoc2.get("usage_count", 0) >= 1 and kdoc2.get("last_used")
    # revoke
    assert adapter.revoke_api_key("K1") is True
    kdoc3 = adapter.get_api_key("K1")
    assert kdoc3["active"] is False
    # stats (all)
    stats = adapter.get_api_key_usage_stats()
    assert isinstance(stats, list) and any(s.get("username") == "alice" for s in stats)
    # stats (filtered by user)
    adapter.create_user({"id": "u2", "username": "bob"})
    adapter.create_api_key("u2", key="K2", name="ci", rate_limit=60, permissions=["user"])
    stats_u1 = adapter.get_api_key_usage_stats("u1")
    assert all(s.get("user_id") == "u1" for s in stats_u1) and all(s.get("username") == "alice" for s in stats_u1)


def test_delete_conversation_returns_false_when_missing(adapter):
    # Attempt to delete non-existent conversation
    assert adapter.delete_conversation("u9", "nope") is False


def test_title_derivation_truncation(adapter):
    adapter.create_category("u4", "General")
    long_text = "A" * 80
    data = {"title": "New Conversation", "category": "General", "messages": [{"role": "user", "content": long_text}]}
    adapter.save_conversation("u4", "c-long", data)
    res = adapter.load_conversation("u4", "c-long")
    assert res is not None
    # Should have ellipsis
    assert res["title"].endswith("...")
    assert len(res["title"]) <= 63


def test_api_key_normalization_defaults(adapter):
    # Insert an API key doc with permissions=None and no active field
    adapter.create_user({"id": "ua", "username": "norm"})
    adapter.db.api_keys.insert_one({
        "key": "KZ",
        "user_id": "ua",
        "name": None,
        "created_at": datetime.now().isoformat(),
        "last_used": None,
        "usage_count": 0,
        "rate_limit": 60,
        "permissions": None,
        # 'active' omitted intentionally
    })
    got = adapter.get_api_key("KZ")
    assert got is not None
    assert got["permissions"] == []
    assert got["active"] is True
    # And listing for user normalizes too
    lst = adapter.get_user_api_keys("ua")
    assert lst and lst[0]["permissions"] == [] and lst[0]["active"] is True


def test_load_conversation_legacy_messages_key(adapter):
    adapter.create_category("u5", "General")
    cat_id = adapter.db.categories.find_one({"user_id": "u5", "name": "General"})["id"]
    adapter.db.conversations.insert_one({
        "id": "legacy2",
        "user_id": "u5",
        "category_id": cat_id,
        "title": "Legacy2",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "starred": False,
        "archived": False,
        "tags": [],
        "data": {"messages": [{"role": "user", "content": "legacy-messages"}]}
    })
    res = adapter.load_conversation("u5", "legacy2")
    assert res is not None and res["history"] and res["history"][0]["content"] == "legacy-messages"


def test_create_category_idempotent(adapter):
    assert adapter.create_category("u6", "General") is True
    # Creating again should be True and not duplicate
    assert adapter.create_category("u6", "General") is True
    cats = adapter.list_categories("u6")
    assert cats == ["General"]


def test_memory_search_shared_only_and_clear_none(adapter):
    # No facts yet
    assert adapter.clear_memory(user_id="ux") == 0
    # Add shared fact
    ok = adapter.add_memory_fact(None, "shared fact", private=False)
    assert ok is True
    results = adapter.search_memory("shared", user_id=None, include_shared=True, k=2)
    assert isinstance(results, list)


def test_connect_error_handling(monkeypatch):
    # Force MongoClient to raise to hit connect error path
    import importlib
    import engine.database.mongodb as m
    importlib.reload(m)
    class Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("boom")
    monkeypatch.setattr(m.pymongo, "MongoClient", Boom)
    from engine.database.mongodb import MongoDBAdapter
    a = MongoDBAdapter(connection_string="mongodb://stub", database_name="db")
    ok = a.connect()
    assert ok is False

def test_save_conversation_creates_missing_category_and_skips_bad_messages(adapter):
    # Category does not exist; adapter should create it
    data = {
        "title": "",
        "category": "BrandNew",
        "history": [
            "not-a-dict",  # skipped
            {"role": "user"},  # missing content -> skipped
            {"content": "no role"},  # missing role -> skipped
            {"role": "user", "content": "first valid"},  # included
            {"role": "assistant", "content": "ok"},
        ],
    }
    ok = adapter.save_conversation("u7", "c-skip", data)
    assert ok is True
    # Category should now exist
    assert "BrandNew" in adapter.list_categories("u7")
    # Only two valid messages saved
    msgs = [m for m in adapter.db.conversation_messages.docs if m.get("conversation_id") == "c-skip"]
    assert len(msgs) == 2 and msgs[0]["idx"] == 0 and msgs[0]["role"] == "user"


def test_load_conversation_defaults_category_when_missing(adapter):
    # Insert conversation with category_id that doesn't exist
    adapter.db.conversations.insert_one({
        "id": "c-missing-cat",
        "user_id": "u8",
        "category_id": "does-not-exist",
        "title": "T",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "starred": False,
        "archived": False,
        "tags": [],
        "data": {"history": [{"role": "user", "content": "hi"}]}
    })
    res = adapter.load_conversation("u8", "c-missing-cat")
    assert res is not None and res["category"] == "General"


def test_load_conversation_malformed_blob_results_empty_history(adapter):
    # Malformed JSON blob and no normalized messages
    adapter.create_category("u9", "General")
    cat = adapter.db.categories.find_one({"user_id": "u9", "name": "General"})["id"]
    adapter.db.conversations.insert_one({
        "id": "c-bad-blob",
        "user_id": "u9",
        "category_id": cat,
        "title": "T",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "starred": False,
        "archived": False,
        "tags": [],
        "data": "{bad json]"
    })
    res = adapter.load_conversation("u9", "c-bad-blob")
    assert res is not None and res["history"] == []


def test_memory_forget_with_shared_toggle(adapter):
    # Add private and shared facts, then forget with forget_shared=True
    adapter.add_memory_fact("ua1", "private apples", private=True)
    adapter.add_memory_fact(None, "shared apples", private=False)
    # Forget only user's facts (no shared)
    n1 = adapter.forget_memory("apples", user_id="ua1", forget_shared=False)
    assert isinstance(n1, int)
    # Forget shared too (for remaining, if any)
    n2 = adapter.forget_memory("apples", user_id="ua1", forget_shared=True)
    assert isinstance(n2, int)


def test_clear_memory_user_and_shared(adapter):
    # Seed both user and shared
    adapter.add_memory_fact("uc1", "keep1", private=True)
    adapter.add_memory_fact(None, "keep2", private=False)
    # Clear combined set
    n = adapter.clear_memory(user_id="uc1", clear_shared=True)
    assert isinstance(n, int)


def test_update_api_key_usage_failure_returns_false(adapter):
    assert adapter.update_api_key_usage("no-such-key") is False


def test_create_new_conversation_with_title_and_new_category(adapter):
    # Provide explicit title and category which doesn't exist yet
    conv_id = adapter.create_new_conversation("unew", title="Hello", category="Ideas")
    assert conv_id
    # Ensure category created and set on saved conversation
    cats = adapter.list_categories("unew")
    assert "Ideas" in cats
