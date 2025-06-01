import importlib
import sys
import types

import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock all external dependencies for agent_core.py before import."""
    sys.modules['langchain_community'] = MagicMock()
    sys.modules['langchain_community.vectorstores'] = MagicMock()
    sys.modules['langchain_community.embeddings'] = types.ModuleType("langchain_community.embeddings")
    sys.modules['langchain_community.vectorstores.FAISS'] = MagicMock()
    sys.modules['torch'] = MagicMock()
    sys.modules['sentence_transformers'] = MagicMock()
    sys.modules['sentence_transformers.SentenceTransformer'] = MagicMock()
    huggingface_mod = types.ModuleType("langchain_huggingface")
    huggingface_mod.HuggingFaceEmbeddings = MagicMock()
    sys.modules['langchain_huggingface'] = huggingface_mod
    sys.modules['faiss'] = MagicMock()
    #sys.modules['numpy'] = MagicMock()
    yield

# Helper class used in tests
class FakeMemory:
    def __init__(self, content):
        self.page_content = content

# ---- VectorStoreManager tests ----

def test_vectorstore_manager_initialization():
    with patch("engine.agent_core.get_embedding_model") as mock_get_embedding:
        from engine.agent_core import VectorStoreManager
        mock_embedding = MagicMock()
        mock_get_embedding.return_value = mock_embedding
        manager = VectorStoreManager()
        assert manager.embedding_model == mock_embedding
        assert manager.current_vector_mode is None
        assert manager.vectorstore is None
        assert mock_get_embedding.called


def test_vectorstore_manager_reset_vectorstore():
    with patch("engine.agent_core.get_embedding_model"):
        from engine.agent_core import VectorStoreManager
        manager = VectorStoreManager()
        manager._vectorstore = MagicMock()
        manager.reset_vectorstore()
        assert manager._vectorstore is None

# ---- FAISVectorStoreAdapter tests ----

def test_fais_vectorstore_adapter_similarity_search_with_score():
    from engine.agent_core import FAISVectorStoreAdapter
    mock_faiss = MagicMock()
    mock_faiss.similarity_search_with_score.return_value = [
        (FakeMemory("doc1"), 0.1),
        (FakeMemory("doc2"), 0.2)
    ]
    adapter = FAISVectorStoreAdapter(mock_faiss)
    result = adapter.similarity_search_with_score("test query", k=2)
    assert len(result) == 2
    assert result[0][0].page_content == "doc1"
    assert result[0][1] == 0.1
    assert result[1][0].page_content == "doc2"
    assert result[1][1] == 0.2
    mock_faiss.similarity_search_with_score.assert_called_once_with("test query", 2)

# ---- MemoryStoreAdapter tests ----

def test_memory_store_adapter_search_memory():
    from engine.agent_core import MemoryStoreAdapter
    mock_search_func = MagicMock()
    mock_search_func.return_value = [
        FakeMemory("memory1"),
        FakeMemory("memory2")
    ]
    adapter = MemoryStoreAdapter(mock_search_func)
    result = adapter.search_memory("test query", k=2)
    assert len(result) == 2
    assert result[0].page_content == "memory1"
    assert result[1].page_content == "memory2"
    mock_search_func.assert_called_once_with("test query", 2)

# ---- LLMBackendAdapter tests ----

def test_llm_backend_adapter_query():
    from engine.agent_core import LLMBackendAdapter
    mock_query_func = MagicMock()
    mock_query_func.return_value = "Test response"
    adapter = LLMBackendAdapter(mock_query_func)
    profile = {"name": "Test"}
    settings = {"model": "test-model"}
    result = adapter.query("test input", "system prompt", profile, settings)
    assert result == "Test response"
    mock_query_func.assert_called_once_with(
        "test input", "system prompt", profile, settings, False
    )

# ---- should_include_documents tests ----

import pytest

@pytest.mark.parametrize("input_text, mems, expected", [
    ("explain this", [], True),
    ("what is suhana", [], True),
    ("how does this work", [], True),
    ("summarize the article", [], True),
    ("random question", [FakeMemory("short fact")] * 3, True),
    ("random question", [], True),
    ("random question", [FakeMemory("one")], True),
    ("random question", [FakeMemory("this memory content is intentionally made longer than ten words to bypass short fact heuristic")] * 5, False),
])
def test_should_include_documents(input_text, mems, expected):
    from engine.agent_core import should_include_documents
    assert should_include_documents(input_text, mems) == expected

# ---- handle_input tests ----

def test_handle_input_ollama():
    with patch("engine.agent_core.container.get_typed") as mock_get_typed, \
         patch("engine.agent_core.summarize_profile_for_prompt", return_value="Profile summary"):
        from engine.agent_core import handle_input, LLMBackendInterface

        mock_memory_store = MagicMock()
        mock_memory_store.search_memory.return_value = [FakeMemory("test memory fact")]
        mock_vectorstore = MagicMock()
        mock_vectorstore.similarity_search_with_score.return_value = [(FakeMemory("doc content"), 0.2)]
        mock_vectorstore_manager = MagicMock()
        mock_vectorstore_manager.get_vectorstore.return_value = mock_vectorstore

        def get_typed_side_effect(name, type_hint):
            if type_hint.__name__ == "MemoryStoreInterface":
                return mock_memory_store
            elif type_hint.__name__ == "VectorStoreManagerInterface":
                return mock_vectorstore_manager
            elif name == "ollama_backend":
                backend = MagicMock()
                backend.query.return_value = "Mocked Ollama reply"
                return backend
            return MagicMock()
        mock_get_typed.side_effect = get_typed_side_effect

        profile = {"history": [], "preferences": {}, "name": "Test"}
        settings = {"llm_backend": "ollama", "llm_model": "fake-model"}
        result = handle_input("test question", "ollama", profile, settings)
        assert result == "Mocked Ollama reply"

def test_handle_input_unknown_backend():
    with patch("engine.agent_core.container.get_typed") as mock_get_typed, \
         patch("engine.agent_core.summarize_profile_for_prompt", return_value="Profile summary"):
        from engine.agent_core import handle_input, LLMBackendInterface

        mock_memory_store = MagicMock()
        mock_memory_store.search_memory.return_value = []
        mock_vectorstore = MagicMock()
        mock_vectorstore.similarity_search_with_score.return_value = []
        mock_vectorstore_manager = MagicMock()
        mock_vectorstore_manager.get_vectorstore.return_value = mock_vectorstore

        def get_typed_side_effect(name, type_hint):
            if type_hint.__name__ == "MemoryStoreInterface":
                return mock_memory_store
            elif type_hint.__name__ == "VectorStoreManagerInterface":
                return mock_vectorstore_manager
            return None
        mock_get_typed.side_effect = get_typed_side_effect

        profile = {"history": [], "preferences": {}, "name": "Test"}
        settings = {"llm_backend": "unknown", "model": "test-model"}
        result = handle_input("test question", "unknown", profile, settings)
        assert result == "I'm sorry, I encountered an error processing your request."

# ---- register_backends tests ----

def test_register_backends():
    with patch("engine.agent_core.container.register") as mock_register, \
         patch("engine.backends.ollama.query_ollama"), \
         patch("engine.backends.openai.query_openai"), \
         patch("engine.memory_store.search_memory"):
        from engine.agent_core import register_backends, MemoryStoreAdapter, LLMBackendAdapter
        register_backends()
        assert mock_register.call_count == 3
        # At least one of each type is registered
        types = [type(call[0][1]) for call in mock_register.call_args_list]
        assert MemoryStoreAdapter in types
        assert LLMBackendAdapter in types
