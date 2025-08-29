import sys
import types
import json
from datetime import datetime
from pathlib import Path

import pytest

# ---- Lightweight stubs for pymongo and vector store/embeddings ----

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


def test_memory_add_search_forget_clear(adapter, tmp_path):
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
    # stats
    stats = adapter.get_api_key_usage_stats()
    assert isinstance(stats, list) and stats[0].get("username") == "alice"
