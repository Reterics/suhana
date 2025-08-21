import sys
import types
import json
import builtins
from datetime import datetime

import pytest

# --- Psycopg2 stubs ---

class PGError(Exception):
    pass

class FakeCursor:
    def __init__(self, fetchone_returns=None, fetchall_returns=None):
        self.fetchone_returns = list(fetchone_returns or [])
        self.fetchall_returns = list(fetchall_returns or [])
        self.executed = []  # record (query, params)

    def execute(self, query, params=None):
        # Record queries for assertions
        self.executed.append((" ".join(query.split()), params))

    def fetchone(self):
        if self.fetchone_returns:
            return self.fetchone_returns.pop(0)
        return None

    def fetchall(self):
        if self.fetchall_returns:
            return self.fetchall_returns.pop(0)
        return []

class FakePGConnection:
    def __init__(self, cursors):
        # cursors: list[FakeCursor] returned in order
        self._cursors = list(cursors)
        self.closed = False

    def cursor(self, cursor_factory=None):
        if not self._cursors:
            # If tests didn't preload enough cursors, provide a dummy
            return FakeCursor()
        return self._cursors.pop(0)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        self.closed = True

class FakePGExtras(types.ModuleType):
    RealDictCursor = object  # not used by our stubs beyond being passed

class FakePsycopg2(types.ModuleType):
    def __init__(self):
        super().__init__("psycopg2")
        self.Error = PGError
        self._next_connection = None
        # submodule extras
        extras = FakePGExtras("psycopg2.extras")
        sys.modules["psycopg2.extras"] = extras

    def connect(self, dsn):
        # Return the preconfigured connection (set by test)
        if self._next_connection is None:
            return FakePGConnection([])
        conn = self._next_connection
        self._next_connection = None
        return conn

# --- Pymongo stubs ---

ASCENDING = 1

class FakeCollection:
    def __init__(self):
        self.docs = []
        self.indexes = []

    # schema helpers
    def create_index(self, *args, **kwargs):
        self.indexes.append((args, kwargs))
        return "idx"

    # CRUD used in adapter
    def find_one(self, query, projection=None):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                if projection:
                    result = {k: doc.get(k) for k in projection.keys()}
                    return result
                return doc.copy()
        return None

    def update_one(self, query, update):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                if "$set" in update:
                    doc.update(update["$set"])
                return types.SimpleNamespace(matched_count=1, modified_count=1)
        return types.SimpleNamespace(matched_count=0, modified_count=0)

    def insert_one(self, doc):
        self.docs.append(doc.copy())
        return types.SimpleNamespace(inserted_id=doc.get("id"))

    def delete_many(self, query):
        before = len(self.docs)
        self.docs = [d for d in self.docs if not all(d.get(k) == v for k, v in query.items())]
        return types.SimpleNamespace(deleted_count=before - len(self.docs))

    def insert_many(self, docs):
        for d in docs:
            self.docs.append(d.copy())
        return types.SimpleNamespace(inserted_ids=[d.get("id") for d in docs])

    # find with simple sort used by adapter
    def find(self, query, projection=None):
        results = [d.copy() for d in self.docs if all(d.get(k) == v for k, v in query.items())]
        class _Cursor(list):
            def sort(self, key, direction):
                super().sort(key=lambda x: x.get(key), reverse=(direction == -1))
                return self
        if projection:
            results = [{k: d.get(k) for k in projection.keys()} for d in results]
        return _Cursor(results)

    # aggregation used in list_conversation_meta (not used by our tests, but keep minimal)
    def aggregate(self, pipeline):
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
        if item in self._collections:
            return self._collections[item]
        # Auto-create collections on first access for convenience
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

# --- Helpers to install stubs ---

def install_psycopg2_stub(cursors):
    fake = FakePsycopg2()
    fake._next_connection = FakePGConnection(cursors)
    sys.modules["psycopg2"] = fake
    # extras already registered in FakePsycopg2.__init__
    return fake

def install_pymongo_stub():
    fake = FakePymongo()
    sys.modules["pymongo"] = fake
    return fake

# --- Tests for PostgresAdapter using stubbed psycopg2 ---

def test_postgres_save_conversation_normalizes_and_derives_title(monkeypatch):
    # Prepare cursor sequence for save_conversation workflow:
    # 1) SELECT category id -> return ("cat1",)
    # 2) SELECT conversation exists -> return None -> triggers INSERT path
    c1 = FakeCursor(fetchone_returns=[("cat1",), None])
    install_psycopg2_stub([c1])

    from engine.database.postgres import PostgresAdapter

    adapter = PostgresAdapter(connection_string="postgres://stub")
    user_id = "u1"
    conv_id = "c1"
    data = {
        "title": "",  # placeholder forces derivation
        "category": "General",
        "starred": False,
        "archived": False,
        "tags": ["x"],
        "history": [
            {"role": "user", "content": "Summarize this long text", "created_at": datetime.now().isoformat()},
            {"role": "assistant", "content": "Sure!"},
        ],
    }

    ok = adapter.save_conversation(user_id, conv_id, data)
    assert ok is True

    # Ensure DELETE then INSERTs into conversation_messages occurred
    flat_sql = [q for (q, _p) in c1.executed]
    has_delete = any("DELETE FROM conversation_messages WHERE conversation_id = %s" in q for q in flat_sql)
    has_insert = any(("INSERT INTO " in q) and ("conversation_messages" in q) for q in flat_sql)
    assert has_delete and has_insert


def test_postgres_load_conversation_merges_meta_and_messages(monkeypatch):
    # Cursor 1: meta row via RealDictCursor fetchone
    meta = {
        "title": "T",
        "tags": ["a"],
        "starred": False,
        "archived": False,
        "updated_at": datetime.now(),
        "created_at": datetime.now(),
        "category": "General",
        "data": {"history": []},
    }
    c_meta = FakeCursor(fetchone_returns=[meta])
    # Cursor 2: normalized messages via fetchall
    msgs = [
        {"idx": 0, "role": "user", "content": "Hi", "created_at": datetime.now(), "meta": {"t": 1}},
        {"idx": 1, "role": "assistant", "content": "Hello", "created_at": datetime.now(), "meta": None},
    ]
    c_msgs = FakeCursor(fetchall_returns=[msgs])

    install_psycopg2_stub([c_meta, c_msgs])

    import importlib
    import engine.database.postgres as pg
    importlib.reload(pg)
    from engine.database.postgres import PostgresAdapter

    adapter = PostgresAdapter(connection_string="postgres://stub")
    # Ensure we bind our stubbed connection with pre-loaded cursors
    adapter.connect()
    res = adapter.load_conversation("u1", "c1")
    assert res is not None
    assert isinstance(res.get("history"), list)
    assert [m["role"] for m in res["history"]] == ["user", "assistant"]
    assert res.get("title") == "T"
    assert res.get("category") == "General"
    assert res.get("tags") == ["a"]


# --- Tests for MongoDBAdapter using stubbed pymongo ---

def test_mongodb_save_conversation_normalizes_and_derives_title(monkeypatch):
    install_pymongo_stub()
    from engine.database.mongodb import MongoDBAdapter
    # Provide concrete implementations for abstract API key methods
    class DummyMongoAdapter(MongoDBAdapter):
        def create_api_key(self, user_id: str, name: str, rate_limit: int = 60, permissions=None) -> str:
            return "k"
        def get_api_key(self, key: str):
            return {}
        def revoke_api_key(self, key: str) -> bool:
            return True
        def get_user_api_keys(self, user_id: str):
            return []
        def update_api_key_usage(self, key: str) -> bool:
            return True
        def get_api_key_usage_stats(self, key: str):
            return {}

    adapter = DummyMongoAdapter(connection_string="mongodb://stub", database_name="db")
    # Pre-create schema and a category
    assert adapter.initialize_schema() is True
    adapter.db.categories.insert_one({"id": "cat1", "user_id": "u1", "name": "General"})

    user_id = "u1"
    conv_id = "c1"
    data = {
        "title": "New Conversation",  # placeholder should derive
        "category": "General",
        "starred": True,
        "archived": False,
        "tags": ["tag"],
        "messages": [
            {"role": "user", "content": "Plan a trip", "created_at": datetime.now().isoformat()},
            {"role": "assistant", "content": "Okay"},
        ],
    }

    ok = adapter.save_conversation(user_id, conv_id, data)
    assert ok is True

    # Verify conversation_messages inserted
    cm = adapter.db.conversation_messages.docs
    assert len(cm) == 2
    assert cm[0]["idx"] == 0 and cm[0]["role"] == "user"


def test_mongodb_load_conversation_merges_meta_and_messages(monkeypatch):
    install_pymongo_stub()
    from engine.database.mongodb import MongoDBAdapter
    class DummyMongoAdapter(MongoDBAdapter):
        def create_api_key(self, user_id: str, name: str, rate_limit: int = 60, permissions=None) -> str:
            return "k"
        def get_api_key(self, key: str):
            return {}
        def revoke_api_key(self, key: str) -> bool:
            return True
        def get_user_api_keys(self, user_id: str):
            return []
        def update_api_key_usage(self, key: str) -> bool:
            return True
        def get_api_key_usage_stats(self, key: str):
            return {}

    adapter = DummyMongoAdapter(connection_string="mongodb://stub", database_name="db")
    assert adapter.initialize_schema() is True

    # Seed category and conversation + normalized messages
    adapter.db.categories.insert_one({"id": "cat1", "user_id": "u1", "name": "General"})
    adapter.db.conversations.insert_one({
        "id": "c1",
        "user_id": "u1",
        "category_id": "cat1",
        "title": "Topic",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "starred": False,
        "archived": False,
        "tags": ["a"],
        "data": {"history": []},
    })
    adapter.db.conversation_messages.insert_many([
        {"id": "m1", "conversation_id": "c1", "idx": 0, "role": "user", "content": "Hi", "created_at": datetime.now().isoformat()},
        {"id": "m2", "conversation_id": "c1", "idx": 1, "role": "assistant", "content": "Hello", "created_at": datetime.now().isoformat()},
    ])

    res = adapter.load_conversation("u1", "c1")
    assert res is not None
    assert [m["role"] for m in res["history"]] == ["user", "assistant"]
    assert res.get("title") == "Topic"
    assert res.get("category") == "General"
    assert res.get("tags") == ["a"]

# Additional Postgres coverage tests

def test_postgres_initialize_schema_executes_ddls(monkeypatch):
    # Single cursor that just records executions
    c = FakeCursor()
    install_psycopg2_stub([c])

    import importlib
    import engine.database.postgres as pg
    importlib.reload(pg)
    from engine.database.postgres import PostgresAdapter

    adapter = PostgresAdapter(connection_string="postgres://stub")
    ok = adapter.initialize_schema()
    assert ok is True
    executed_sql = "\n".join(q for q, _ in c.executed)
    assert "CREATE TABLE IF NOT EXISTS users" in executed_sql
    assert "CREATE TABLE IF NOT EXISTS conversations" in executed_sql
    assert "CREATE TABLE IF NOT EXISTS conversation_messages" in executed_sql
    assert "CREATE INDEX IF NOT EXISTS idx_conv_msgs_idx" in executed_sql


def test_postgres_list_conversations_without_and_with_category(monkeypatch):
    # First call without category -> fetchall returns tuples of ids
    rows_without = [("id2",), ("id1",)]
    c1 = FakeCursor(fetchall_returns=[rows_without])
    install_psycopg2_stub([c1])

    import importlib
    import engine.database.postgres as pg
    importlib.reload(pg)
    from engine.database.postgres import PostgresAdapter

    adapter = PostgresAdapter(connection_string="postgres://stub")
    adapter.connect()
    ids = adapter.list_conversations("u1")
    assert ids == ["id2", "id1"]

    # Now with category -> new stub
    rows_with = [("id9",), ("id3",)]
    c2 = FakeCursor(fetchall_returns=[rows_with])
    install_psycopg2_stub([c2])
    importlib.reload(pg)
    from engine.database.postgres import PostgresAdapter as PA2
    adapter2 = PA2(connection_string="postgres://stub")
    adapter2.connect()
    ids2 = adapter2.list_conversations("u1", category="General")
    assert ids2 == ["id9", "id3"]


def test_postgres_list_conversation_meta(monkeypatch):
    # RealDictCursor-like rows -> list of dicts
    rows = [[{
        "id": "c1",
        "title": "T",
        "created_at": "2025-01-01",
        "updated_at": "2025-01-02",
        "starred": False,
        "archived": False,
        "tags": ["x"],
        "category": "General",
    }]]
    c = FakeCursor(fetchall_returns=rows)
    install_psycopg2_stub([c])

    import importlib
    import engine.database.postgres as pg
    importlib.reload(pg)
    from engine.database.postgres import PostgresAdapter

    adapter = PostgresAdapter(connection_string="postgres://stub")
    res = adapter.list_conversation_meta("u1")
    assert isinstance(res, list) and res
    assert res[0]["id"] == "c1"
    assert res[0]["category"] == "General"


def test_postgres_get_and_save_settings_insert_and_update(monkeypatch):
    # Sequence for insert (no existing row) and then get (global)
    c_insert = FakeCursor(fetchone_returns=[None])  # for SELECT existing -> None triggers INSERT
    install_psycopg2_stub([c_insert])

    import importlib
    import engine.database.postgres as pg
    importlib.reload(pg)
    from engine.database.postgres import PostgresAdapter

    adapter = PostgresAdapter(connection_string="postgres://stub")
    ok = adapter.save_settings({"a": 1})
    assert ok is True

    # Now test update branch for a specific user and get_settings
    # fetchone_returns: first call -> some id present triggers UPDATE; second call -> get_settings returns dict
    c_update_get = FakeCursor(fetchone_returns=[("sid",), {"settings": {"b": 2}}])
    install_psycopg2_stub([c_update_get])
    importlib.reload(pg)
    from engine.database.postgres import PostgresAdapter as PA3

    adapter2 = PA3(connection_string="postgres://stub")
    ok2 = adapter2.save_settings({"b": 2}, user_id="u1")
    assert ok2 is True

    # New connection for get_settings so the stubbed cursor returns our dict
    c_get = FakeCursor(fetchone_returns=[{"settings": {"b": 2}}])
    install_psycopg2_stub([c_get])
    importlib.reload(pg)
    from engine.database.postgres import PostgresAdapter as PA4
    adapter3 = PA4(connection_string="postgres://stub")
    got = adapter3.get_settings(user_id="u1")
    assert got == {"b": 2}


def test_postgres_save_conversation_update_and_normalize(monkeypatch):
    # For save_conversation update path:
    # 1) SELECT category id -> found
    # 2) SELECT conversation exists -> found -> UPDATE path
    c = FakeCursor(fetchone_returns=[("cat1",), ("c1",)])
    install_psycopg2_stub([c])

    import importlib
    import engine.database.postgres as pg
    importlib.reload(pg)
    from engine.database.postgres import PostgresAdapter

    adapter = PostgresAdapter(connection_string="postgres://stub")
    data = {
        "title": "Untitled Conversation",  # placeholder -> derive from messages
        "category": "General",
        "starred": True,
        "archived": False,
        "tags": ["t"],
        "messages": [
            {"role": "user", "content": "Make a plan", "created_at": datetime.now().isoformat(), "meta": {"k": 1}},
            {"role": "assistant", "content": "Okay"},
        ],
    }
    ok = adapter.save_conversation("u1", "c1", data)
    assert ok is True
    sqls = [q for q, _ in c.executed]
    assert any("UPDATE conversations" in q for q in sqls)
    assert any("DELETE FROM conversation_messages" in q for q in sqls)
    assert any(("INSERT INTO" in q) and ("conversation_messages" in q) for q in sqls)


def test_postgres_load_conversation_legacy_blob_fallback(monkeypatch):
    # meta_row with legacy blob string, and no normalized messages
    meta = {
        "title": "Legacy",
        "tags": [],
        "starred": False,
        "archived": False,
        "updated_at": datetime.now(),
        "created_at": datetime.now(),
        "category": "General",
        "data": json.dumps({"history": [{"role": "user", "content": "legacy"}]})
    }
    c_meta = FakeCursor(fetchone_returns=[meta])
    c_msgs = FakeCursor(fetchall_returns=[[]])
    install_psycopg2_stub([c_meta, c_msgs])

    import importlib
    import engine.database.postgres as pg
    importlib.reload(pg)
    from engine.database.postgres import PostgresAdapter

    adapter = PostgresAdapter(connection_string="postgres://stub")
    adapter.connect()
    res = adapter.load_conversation("u1", "c1")
    assert res is not None
    assert res["history"] and res["history"][0]["content"] == "legacy"


def test_postgres_disconnect(monkeypatch):
    c = FakeCursor()
    install_psycopg2_stub([c])

    import importlib
    import engine.database.postgres as pg
    importlib.reload(pg)
    from engine.database.postgres import PostgresAdapter

    adapter = PostgresAdapter(connection_string="postgres://stub")
    adapter.connect()
    assert adapter.connection is not None
    ok = adapter.disconnect()
    assert ok is True
