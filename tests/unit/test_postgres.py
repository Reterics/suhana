import json
from datetime import datetime
from pathlib import Path

import importlib
import pytest

# Minimal local stubs for psycopg2 and FAISS used in these tests
import types
import sys

class PGError(Exception):
    pass

class FakeCursor:
    def __init__(self, fetchone_returns=None, fetchall_returns=None, rowcount=1):
        self.fetchone_returns = list(fetchone_returns or [])
        self.fetchall_returns = list(fetchall_returns or [])
        self.executed = []
        self.rowcount = rowcount
    def execute(self, query, params=None):
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
        self._cursors = list(cursors)
    def cursor(self, cursor_factory=None):
        if not self._cursors:
            return FakeCursor()
        return self._cursors.pop(0)
    def commit(self):
        pass
    def rollback(self):
        pass
    def close(self):
        pass

class FakePGExtras(types.ModuleType):
    RealDictCursor = object

class FakePsycopg2(types.ModuleType):
    def __init__(self):
        super().__init__("psycopg2")
        self.Error = PGError
        self._next_connection = None
        extras = FakePGExtras("psycopg2.extras")
        sys.modules["psycopg2.extras"] = extras
    def connect(self, dsn):
        if self._next_connection is None:
            return FakePGConnection([])
        conn = self._next_connection
        self._next_connection = None
        return conn

def install_psycopg2_stub(cursors):
    fake = FakePsycopg2()
    fake._next_connection = FakePGConnection(cursors)
    sys.modules["psycopg2"] = fake
    return fake

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


def test_postgres_user_crud_and_categories(monkeypatch):
    # Prepare cursors for: get_user -> dict; list_users -> list; update_user -> existing row then update; list_categories -> names
    c_get_user = FakeCursor(fetchone_returns=[{"id": "u1", "username": "alice"}])
    c_list_users = FakeCursor(fetchall_returns=[[{"id": "u1"}, {"id": "u2"}]])
    # update_user first SELECT returns some row to indicate exists
    c_update_user = FakeCursor(fetchone_returns=[("u1",)], rowcount=1)
    # delete_user uses rowcount
    c_delete_user = FakeCursor(rowcount=1)
    # list_categories returns tuples
    c_list_cat = FakeCursor(fetchall_returns=[[("General",), ("Work",)]])
    # create_user simple cursor
    c_create_user = FakeCursor()

    install_psycopg2_stub([c_get_user, c_list_users, c_create_user, c_update_user, c_delete_user, c_list_cat])

    import engine.database.postgres as pg
    importlib.reload(pg)
    from engine.database.postgres import PostgresAdapter

    adapter = PostgresAdapter(connection_string="postgres://stub")
    # Bypass access controls for test
    import engine.security.database_access as da
    monkeypatch.setattr(da, "check_permission", lambda user_id, perm, resource_owner_id=None: True)

    # get_user
    user = adapter.get_user("u1")
    assert user and user["username"] == "alice"

    # list_users
    users = adapter.list_users()
    assert len(users) == 2

    # create_user
    uid = adapter.create_user({"id": "u3", "username": "bob", "profile": {"k": 1}})
    assert uid == "u3"

    # update_user
    ok_upd = adapter.update_user("u1", {"username": "alice2"})
    assert ok_upd is True

    # delete_user
    ok_del = adapter.delete_user("u2")
    assert ok_del is True

    # list_categories
    cats = adapter.list_categories("u1")
    assert cats == ["General", "Work"]


def test_postgres_create_delete_conversation_and_move_category(monkeypatch):
    # move_conversation_to_category path with existing category id and successful update
    c_move = FakeCursor(fetchone_returns=[("cat1",)], rowcount=1)
    # delete_conversation rowcount true
    c_delete = FakeCursor(rowcount=1)

    install_psycopg2_stub([c_move, c_delete])

    import engine.database.postgres as pg
    importlib.reload(pg)
    from engine.database.postgres import PostgresAdapter

    adapter = PostgresAdapter(connection_string="postgres://stub")
    # Bypass access controls for test
    import engine.security.database_access as da
    monkeypatch.setattr(da, "check_permission", lambda user_id, perm, resource_owner_id=None: True)

    # create_new_conversation by monkeypatching save_conversation to bypass SQL internals
    def _fake_save(user_id, cid, data):
        return True
    adapter.save_conversation = _fake_save
    conv_id = adapter.create_new_conversation("u1", title="Hello", category="General")
    assert isinstance(conv_id, str) and len(conv_id) > 0

    # move conversation
    ok_move = adapter.move_conversation_to_category("u1", "c1", "General")
    assert ok_move is True

    # delete conversation
    ok_del = adapter.delete_conversation("u1", "c1")
    assert ok_del is True


def test_postgres_migrate_from_files(tmp_path):
    base = tmp_path
    # global settings
    (base / "settings.json").write_text(json.dumps({"a": 1}), encoding="utf-8")
    # user structure
    udir = base / "users" / "u1"
    udir.mkdir(parents=True)
    (udir / "profile.json").write_text(json.dumps({"name": "Alice"}), encoding="utf-8")
    (udir / "settings.json").write_text(json.dumps({"b": 2}), encoding="utf-8")
    cdir = udir / "conversations"
    cdir.mkdir()
    (cdir / "c1.json").write_text(json.dumps({"title": "Hi", "messages": []}), encoding="utf-8")

    # stub DB with minimal cursor
    c = FakeCursor()
    install_psycopg2_stub([c])

    import engine.database.postgres as pg
    importlib.reload(pg)
    from engine.database.postgres import PostgresAdapter

    adapter = PostgresAdapter(connection_string="postgres://stub")
    # monkeypatch DB-affecting methods to avoid SQL complexity
    calls = {"save_settings": 0, "create_user": 0, "create_category": 0, "save_conversation": 0}
    def _ss(x, user_id=None):
        calls["save_settings"] += 1
        return True
    def _cu(data):
        calls["create_user"] += 1
        return data.get("id", "")
    def _cc(uid, cat):
        calls["create_category"] += 1
        return True
    def _sc(uid, cid, data):
        calls["save_conversation"] += 1
        return True
    adapter.save_settings = _ss
    adapter.create_user = _cu
    adapter.create_category = _cc
    adapter.save_conversation = _sc

    users_m, conv_m, settings_m = adapter.migrate_from_files(base)
    # 1 global + 1 user settings = 2
    assert settings_m == 2
    assert users_m == 1
    assert conv_m == 1
    # ensure our patched methods were invoked
    assert calls["save_settings"] == 2 and calls["create_user"] == 1 and calls["save_conversation"] == 1


def test_postgres_memory_and_api_keys(tmp_path, monkeypatch):
    # Install DB stub cursors for sequences used:
    # add_memory_fact uses one cursor; search_memory uses one cursor returning rows; forget/clear use one cursor each
    fact_row = {"id": "m1", "user_id": "u1", "text": "alpha", "private": True, "created_at": datetime.now(), "embedding_file": str(tmp_path / "vec.faiss")}
    c_add = FakeCursor()
    c_search = FakeCursor(fetchall_returns=[[fact_row]])
    c_forget = FakeCursor(fetchall_returns=[[fact_row]], rowcount=1)
    c_clear = FakeCursor(fetchall_returns=[[fact_row]], rowcount=1)

    # API key cursors
    c_get_key = FakeCursor(fetchone_returns=[{"key": "k", "user_id": "u1", "permissions": "[\"admin\"]"}])
    c_get_user_keys = FakeCursor(fetchall_returns=[[{"key": "k1", "user_id": "u1", "permissions": "[\"user\"]"}, {"key": "k2", "user_id": "u1", "permissions": None}]])
    c_create_key = FakeCursor()
    c_update_usage = FakeCursor()
    c_revoke = FakeCursor()
    c_stats = FakeCursor(fetchall_returns=[[{"key": "k1", "user_id": "u1", "permissions": "[\"user\"]", "usage_count": 3}]])

    install_psycopg2_stub([c_add, c_search, c_forget, c_clear, c_get_key, c_get_user_keys, c_create_key, c_update_usage, c_revoke, c_stats])

    import engine.database.postgres as pg
    importlib.reload(pg)
    from engine.database.postgres import PostgresAdapter

    adapter = PostgresAdapter(connection_string="postgres://stub")
    # Bypass access controls for test
    import engine.security.database_access as da
    monkeypatch.setattr(da, "check_permission", lambda user_id, perm, resource_owner_id=None: True)

    # Patch embeddings and FAISS with lightweight stubs
    adapter.embeddings = DummyEmbeddings()
    # Monkeypatch FAISS in module namespace
    pg.FAISS = DummyFAISS

    # Prepare a fake embedding file for search/forget/clear
    emb_path = Path(fact_row["embedding_file"])
    emb_path.parent.mkdir(parents=True, exist_ok=True)
    emb_path.write_text("stub", encoding="utf-8")

    # add_memory_fact
    ok_add = adapter.add_memory_fact("u1", "remember alpha", private=True)
    assert ok_add is True

    # search_memory should return one result with score
    results = adapter.search_memory("alpha", user_id="u1", include_shared=False, k=1)
    assert isinstance(results, list) and results and "score" in results[0]

    # forget_memory should delete 1 and remove file
    count_forget = adapter.forget_memory("alpha", user_id="u1")
    assert count_forget == 1
    assert not emb_path.exists()

    # Recreate file for clear
    emb_path.write_text("stub", encoding="utf-8")
    count_clear = adapter.clear_memory(user_id="u1")
    assert count_clear == 1

    # API: get_api_key
    info = adapter.get_api_key("k")
    assert info and info["permissions"] == ["admin"]

    # API: get_user_api_keys
    keys = adapter.get_user_api_keys("u1")
    assert isinstance(keys, list) and keys[0]["permissions"] == ["user"] and keys[1]["permissions"] is None

    # API: create/update/revoke
    assert adapter.create_api_key("u1", key="k3", name="n", rate_limit=10, permissions=["user"]) is True
    assert adapter.update_api_key_usage("k3") is True
    assert adapter.revoke_api_key("k3") is True

    # API: usage stats
    stats = adapter.get_api_key_usage_stats("u1")
    assert stats and stats[0]["usage_count"] == 3
