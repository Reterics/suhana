import sys
import types
import pytest
from unittest.mock import MagicMock

sys.modules['sentence_transformers'] = MagicMock()
sys.modules['sentence_transformers.SentenceTransformer'] = MagicMock()

@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock all external dependencies for agent_core.py before import."""
    sys.modules['langchain_community'] = MagicMock()
    sys.modules['langchain_community.vectorstores'] = MagicMock()
    sys.modules['langchain_community.embeddings'] = types.ModuleType("langchain_community.embeddings")
    sys.modules['langchain_community.vectorstores.FAISS'] = MagicMock()
    sys.modules['torch'] = MagicMock()
    huggingface_mod = types.ModuleType("langchain_huggingface")
    huggingface_mod.HuggingFaceEmbeddings = MagicMock()
    sys.modules['langchain_huggingface'] = huggingface_mod
    sys.modules['faiss'] = MagicMock()
    #sys.modules['numpy'] = MagicMock()

    # AI Libraries
    sys.modules['google'] = MagicMock()
    sys.modules['google.generativeai'] = MagicMock()
    sys.modules['anthropic'] = MagicMock()
    yield


@pytest.fixture(autouse=True)
def fake_memory_path(monkeypatch, tmp_path):
    # Patch MEMORY_PATH to tmp_path / "memory"
    import engine.memory_store as memory_store
    mem_path = tmp_path / "memory"
    mem_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(memory_store, "MEMORY_PATH", mem_path)
    return mem_path

def test_load_memory_store_index_exists(monkeypatch, fake_memory_path):
    import engine.memory_store as memory_store
    # Simulate index.faiss exists
    (fake_memory_path / "index.faiss").write_text("abc")
    fake_FAISS = MagicMock()
    fake_store = MagicMock()
    fake_FAISS.load_local.return_value = fake_store
    monkeypatch.setattr(memory_store, "FAISS", fake_FAISS)
    monkeypatch.setattr(memory_store, "EMBED_MODEL", "EMBED")
    store = memory_store.load_memory_store()
    assert store is fake_store
    fake_FAISS.load_local.assert_called_once()

def test_load_memory_store_no_index(monkeypatch, fake_memory_path):
    import engine.memory_store as memory_store
    fake_FAISS = MagicMock()
    fake_store = MagicMock()
    fake_FAISS.from_documents.return_value = fake_store
    monkeypatch.setattr(memory_store, "FAISS", fake_FAISS)
    monkeypatch.setattr(memory_store, "EMBED_MODEL", "EMBED")
    store = memory_store.load_memory_store()
    assert store is fake_store
    fake_FAISS.from_documents.assert_called_once()

def test_save_memory_store(monkeypatch, fake_memory_path):
    import engine.memory_store as memory_store
    fake_store = MagicMock()
    memory_store.save_memory_store(fake_store)
    fake_store.save_local.assert_called_with(str(fake_memory_path))

def test_add_memory_fact_existing_index(monkeypatch, fake_memory_path):
    import engine.memory_store as memory_store
    # index.faiss exists
    (fake_memory_path / "index.faiss").write_text("abc")
    fake_store = MagicMock()
    fake_FAISS = MagicMock()
    fake_FAISS.from_documents.return_value = fake_store
    monkeypatch.setattr(memory_store, "FAISS", fake_FAISS)
    monkeypatch.setattr(memory_store, "EMBED_MODEL", "EMBED")
    monkeypatch.setattr(memory_store, "load_memory_store", lambda: fake_store)
    monkeypatch.setattr(memory_store, "save_memory_store", MagicMock())
    fake_Document = MagicMock(return_value="DOC")
    monkeypatch.setattr(memory_store, "Document", fake_Document)
    memory_store.add_memory_fact("test fact")
    fake_store.add_documents.assert_called_once_with(["DOC"])

def test_add_memory_fact_new_index(monkeypatch, fake_memory_path):
    import engine.memory_store as memory_store
    fake_store = MagicMock()
    fake_FAISS = MagicMock()
    fake_FAISS.from_documents.return_value = fake_store
    monkeypatch.setattr(memory_store, "FAISS", fake_FAISS)
    monkeypatch.setattr(memory_store, "EMBED_MODEL", "EMBED")
    monkeypatch.setattr(memory_store, "save_memory_store", MagicMock())
    fake_Document = MagicMock(return_value="DOC")
    monkeypatch.setattr(memory_store, "Document", fake_Document)
    memory_store.add_memory_fact("test fact")
    fake_FAISS.from_documents.assert_called_once_with(["DOC"], "EMBED")

def test_search_memory(monkeypatch):
    import engine.memory_store as memory_store
    fake_store = MagicMock()
    fake_store.similarity_search.return_value = ["result"]
    monkeypatch.setattr(memory_store, "load_memory_store", lambda: fake_store)
    result = memory_store.search_memory("query", k=5)
    fake_store.similarity_search.assert_called_with("query", k=5)
    assert result == ["result"]

def test_recall_memory(monkeypatch):
    import engine.memory_store as memory_store
    doc1 = MagicMock(page_content="a")
    doc2 = MagicMock(page_content="b")
    fake_store = MagicMock()
    fake_store.similarity_search.return_value = [doc1, doc2]
    monkeypatch.setattr(memory_store, "load_memory_store", lambda: fake_store)
    out = memory_store.recall_memory()
    assert out == ["a", "b"]
    fake_store.similarity_search.assert_called_with("", k=50)

def test_forget_memory(monkeypatch):
    import engine.memory_store as memory_store
    doc1 = MagicMock(page_content="foo is here")
    doc2 = MagicMock(page_content="keep this")
    fake_store = MagicMock()
    fake_store.similarity_search.return_value = [doc1, doc2]
    monkeypatch.setattr(memory_store, "load_memory_store", lambda: fake_store)
    fake_FAISS = MagicMock()
    monkeypatch.setattr(memory_store, "FAISS", fake_FAISS)
    monkeypatch.setattr(memory_store, "EMBED_MODEL", "EMBED")
    monkeypatch.setattr(memory_store, "save_memory_store", MagicMock())
    # Forget 'foo' -> leaves only doc2
    n = memory_store.forget_memory("foo")
    assert n == 1
    fake_FAISS.from_documents.assert_called_once()
