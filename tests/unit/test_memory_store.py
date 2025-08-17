import sys
import types
import pytest
from unittest.mock import MagicMock

sys.modules['sentence_transformers'] = MagicMock()
sys.modules['sentence_transformers.SentenceTransformer'] = MagicMock()

@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock external dependencies used by memory_store.py."""
    sys.modules['langchain_community'] = MagicMock()
    sys.modules['langchain_community.vectorstores'] = MagicMock()
    sys.modules['langchain_community.embeddings'] = types.ModuleType("langchain_community.embeddings")
    sys.modules['langchain_community.vectorstores.FAISS'] = MagicMock()
    sys.modules['torch'] = MagicMock()
    huggingface_mod = types.ModuleType("langchain_huggingface")
    huggingface_mod.HuggingFaceEmbeddings = MagicMock()
    sys.modules['langchain_huggingface'] = huggingface_mod
    sys.modules['faiss'] = MagicMock()
    yield


def make_store(tmp_path, monkeypatch):
    from engine.memory_store import MemoryStore
    store = MemoryStore(base_dir=tmp_path)
    # Patch embedding model and FAISS
    import engine.memory_store as memory_store
    fake_FAISS = MagicMock()
    monkeypatch.setattr(memory_store, "FAISS", fake_FAISS)
    monkeypatch.setattr(memory_store, "EMBED_MODEL", "EMBED")
    return store, fake_FAISS


def test_load_memory_store_index_exists(monkeypatch, tmp_path):
    from engine.memory_store import MemoryStore
    store, fake_FAISS = make_store(tmp_path, monkeypatch)
    # Simulate index.faiss exists in shared memory
    (tmp_path / "memory" / "index.faiss").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory" / "index.faiss").write_text("abc")
    fake_store = MagicMock()
    fake_FAISS.load_local.return_value = fake_store

    out = store.load_memory_store()
    assert out is fake_store
    fake_FAISS.load_local.assert_called_once()


def test_load_memory_store_no_index(monkeypatch, tmp_path):
    store, fake_FAISS = make_store(tmp_path, monkeypatch)
    fake_store = MagicMock()
    fake_FAISS.from_documents.return_value = fake_store

    out = store.load_memory_store()
    assert out is fake_store
    fake_FAISS.from_documents.assert_called_once()


def test_save_memory_store(monkeypatch, tmp_path):
    store, _ = make_store(tmp_path, monkeypatch)
    fake_store = MagicMock()
    store.save_memory_store(fake_store)
    fake_store.save_local.assert_called_with(str(tmp_path / "memory"))


def test_add_memory_fact_shared(monkeypatch, tmp_path):
    import engine.memory_store as memory_store
    store, fake_FAISS = make_store(tmp_path, monkeypatch)
    fake_store = MagicMock()
    fake_FAISS.from_documents.return_value = fake_store
    monkeypatch.setattr(memory_store, "Document", MagicMock(return_value="DOC"))

    ok = store.add_memory_fact("test fact", user_id=None, private=False)
    assert ok is True
    fake_FAISS.from_documents.assert_called()  # Called when saving new store


def test_search_memory(monkeypatch, tmp_path):
    store, fake_FAISS = make_store(tmp_path, monkeypatch)
    fake_vs = MagicMock()
    doc = MagicMock()
    doc.page_content = "result"
    fake_vs.similarity_search.return_value = [doc]
    # For shared search
    monkeypatch.setattr(store, "load_memory_store", lambda user_id=None: fake_vs)

    result = store.search_memory("query", k=5)
    fake_vs.similarity_search.assert_called_with("query", k=5)
    # Function returns documents; verify page_content aggregation logic by mapping
    assert [d.page_content for d in result] == ["result"]


def test_recall_memory(monkeypatch, tmp_path):
    store, _ = make_store(tmp_path, monkeypatch)
    doc1 = MagicMock(page_content="a")
    doc2 = MagicMock(page_content="b")
    fake_vs = MagicMock()
    fake_vs.similarity_search.return_value = [doc1, doc2]
    monkeypatch.setattr(store, "load_memory_store", lambda user_id=None: fake_vs)

    out = store.recall_memory()
    assert out == ["a", "b"]
    fake_vs.similarity_search.assert_called_with("", k=50)


def test_forget_memory(monkeypatch, tmp_path):
    store, fake_FAISS = make_store(tmp_path, monkeypatch)
    doc1 = MagicMock(page_content="foo is here")
    doc2 = MagicMock(page_content="keep this")
    fake_vs = MagicMock()
    fake_vs.similarity_search.return_value = [doc1, doc2]
    monkeypatch.setattr(store, "load_memory_store", lambda user_id=None: fake_vs)

    user_count, shared_count = store.forget_memory("foo")
    assert shared_count == 1
    fake_FAISS.from_documents.assert_called_once()
