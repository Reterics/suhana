import sys
import types
import pytest
from unittest.mock import MagicMock, patch

@pytest.fixture(autouse=True)
def mock_dependencies(monkeypatch):
    # Patch langchain_community and langchain_huggingface
    fake_FAISS = MagicMock()
    fake_HuggingFaceEmbeddings = MagicMock()
    sys.modules['langchain_community'] = MagicMock()
    sys.modules['langchain_community.vectorstores'] = MagicMock(FAISS=fake_FAISS)
    sys.modules['langchain_community.embeddings'] = MagicMock(HuggingFaceEmbeddings=fake_HuggingFaceEmbeddings)
    sys.modules['langchain_huggingface'] = MagicMock(HuggingFaceEmbeddings=fake_HuggingFaceEmbeddings)
    sys.modules['langchain_core.documents'] = MagicMock(Document=MagicMock())
    sys.modules['engine.logging_config'] = MagicMock(get_logger=MagicMock(return_value=MagicMock()))
    sys.modules['engine.error_handling'] = MagicMock(VectorStoreError=Exception)
    yield

def test_configure_logging(monkeypatch):
    import sys
    import types

    # Prepare a module in sys.modules
    fake_logger = MagicMock()
    fake_logging_config = types.ModuleType("engine.logging_config")
    fake_logging_config.get_logger = lambda name=None: fake_logger
    sys.modules["engine.logging_config"] = fake_logging_config

    import engine.utils as utils
    logger = utils.configure_logging("abc")
    assert logger is fake_logger

def test_get_embedding_model(monkeypatch):
    import engine.utils as utils
    fake_Embed = MagicMock()
    monkeypatch.setattr(utils, "HuggingFaceEmbeddings", lambda model_name: fake_Embed)
    result = utils.get_embedding_model("foobar")
    assert result is fake_Embed

def test_save_vectorstore(monkeypatch, tmp_path):
    import engine.utils as utils

    fake_FAISS = MagicMock()
    fake_vectorstore = MagicMock()
    fake_FAISS.from_documents.return_value = fake_vectorstore
    monkeypatch.setattr(utils, "FAISS", fake_FAISS)
    fake_embed = MagicMock()
    fake_doc = MagicMock()

    # No metadata
    out = utils.save_vectorstore([fake_doc], fake_embed, tmp_path)
    assert out is fake_vectorstore
    fake_FAISS.from_documents.assert_called_once_with([fake_doc], fake_embed)
    fake_vectorstore.save_local.assert_called_once()

    # With metadata
    meta = {"project_info": {"foo": "bar"}}
    out2 = utils.save_vectorstore([fake_doc], fake_embed, tmp_path, meta)
    assert out2 is fake_vectorstore
    # Check metadata file written
    with open(tmp_path / 'metadata.json') as f:
        import json
        data = json.load(f)
        assert data == meta

def test_load_metadata(monkeypatch, tmp_path):
    import engine.utils as utils
    # Write valid metadata file
    metadata = {"project_info": {"foo": 42}}
    with open(tmp_path / "metadata.json", "w") as f:
        import json; json.dump(metadata, f)
    loaded = utils.load_metadata(tmp_path)
    assert loaded == {"foo": 42}

    # Missing file
    missing = utils.load_metadata(tmp_path / "not_here")
    assert missing is None

    # Invalid JSON/file
    (tmp_path / "metadata.json").write_text("invalid!")
    # Should log a warning and return None
    result = utils.load_metadata(tmp_path)
    assert result is None

def test_load_vectorstore(monkeypatch, tmp_path):
    import engine.utils as utils

    # No index.faiss
    assert utils.load_vectorstore(tmp_path) is None

    # Create index.faiss to enable load
    (tmp_path / "index.faiss").write_text("abc")
    fake_FAISS = MagicMock()
    fake_FAISS.load_local.return_value = "VECTORSTORE"
    monkeypatch.setattr(utils, "FAISS", fake_FAISS)
    monkeypatch.setattr(utils, "get_embedding_model", lambda: "EMBED")
    # Should succeed
    result = utils.load_vectorstore(tmp_path)
    assert result == "VECTORSTORE"
    # Simulate exception
    fake_FAISS.load_local.side_effect = Exception("fail")
    assert utils.load_vectorstore(tmp_path) is None

def test_refresh_vectorstore(monkeypatch, tmp_path):
    import engine.utils as utils
    monkeypatch.setattr(utils, "load_vectorstore", lambda *a, **k: "VECTORSTORE")
    fake_run = MagicMock()
    monkeypatch.setattr(utils.subprocess, "run", fake_run)
    # Success case
    (tmp_path / "index.faiss").write_text("abc")
    out = utils.refresh_vectorstore(tmp_path)
    assert out == "VECTORSTORE"
    # Simulate failure
    class FakeVSErr(Exception):
        def __init__(self, *a, **k): super().__init__(*a)
    monkeypatch.setattr(utils, "VectorStoreError", FakeVSErr)
    import subprocess
    fake_run.side_effect = subprocess.CalledProcessError(1, "ingest_project.py")
    with pytest.raises(FakeVSErr):
        utils.refresh_vectorstore(tmp_path)
