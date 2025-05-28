import pytest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

from engine import agent_core
from engine.agent_core import VectorStoreManager


class FakeMemory:
    def __init__(self, content): self.page_content = content


def test_vectorstore_manager_singleton():
    """Test that VectorStoreManager follows the singleton pattern."""
    # Get two instances
    manager1 = VectorStoreManager()
    manager2 = VectorStoreManager()

    # They should be the same object
    assert manager1 is manager2

    # Modifying one should affect the other
    manager1.current_vector_mode = "test_mode"
    assert manager2.current_vector_mode == "test_mode"


@patch("engine.agent_core.get_embedding_model")
def test_vectorstore_manager_initialization(mock_get_embedding):
    """Test that VectorStoreManager initializes correctly."""
    # Reset the singleton for testing
    VectorStoreManager._instance = None

    # Mock the embedding model
    mock_embedding = MagicMock()
    mock_get_embedding.return_value = mock_embedding

    # Create a new instance
    manager = VectorStoreManager()

    # Check initialization
    assert manager.embedding_model == mock_embedding
    assert manager.current_vector_mode is None
    assert manager.vectorstore is None
    assert mock_get_embedding.called


@patch("engine.agent_core.load_vectorstore")
@patch("engine.agent_core.Path")
@patch("engine.agent_core.get_embedding_model")
def test_vectorstore_manager_get_vectorstore_normal_mode(mock_get_embedding, mock_path, mock_load_vectorstore):
    """Test get_vectorstore method in normal mode."""
    # Reset the singleton for testing
    VectorStoreManager._instance = None

    # Mock the embedding model
    mock_embedding = MagicMock()
    mock_get_embedding.return_value = mock_embedding

    # Mock Path to return a path that exists
    mock_path_instance = MagicMock()
    mock_path.return_value = mock_path_instance
    mock_path_instance.__truediv__.return_value = mock_path_instance
    mock_path_instance.exists.return_value = True

    # Mock load_vectorstore to return a mock vectorstore
    mock_vectorstore = MagicMock()
    mock_load_vectorstore.return_value = mock_vectorstore

    # Create a new instance
    manager = VectorStoreManager()

    # Test get_vectorstore with normal mode
    profile = {"mode": "normal"}
    result = manager.get_vectorstore(profile)

    # Check results
    assert result == mock_vectorstore
    assert manager.current_vector_mode == "normal"
    assert mock_load_vectorstore.called


@patch("engine.agent_core.load_vectorstore")
@patch("engine.agent_core.Path")
@patch("engine.agent_core.get_embedding_model")
def test_vectorstore_manager_get_vectorstore_development_mode(mock_get_embedding, mock_path, mock_load_vectorstore):
    """Test get_vectorstore method in development mode."""
    # Reset the singleton for testing
    VectorStoreManager._instance = None

    # Mock the embedding model
    mock_embedding = MagicMock()
    mock_get_embedding.return_value = mock_embedding

    # Mock Path to return a path that exists
    mock_path_instance = MagicMock()
    mock_path.return_value = mock_path_instance
    mock_path_instance.__truediv__.return_value = mock_path_instance
    mock_path_instance.exists.return_value = True

    # Mock load_vectorstore to return a mock vectorstore
    mock_vectorstore = MagicMock()
    mock_load_vectorstore.return_value = mock_vectorstore

    # Create a new instance
    manager = VectorStoreManager()

    # Test get_vectorstore with development mode
    profile = {"mode": "development", "project_path": "test/path"}
    result = manager.get_vectorstore(profile)

    # Check results
    assert result == mock_vectorstore
    assert manager.current_vector_mode == "development"
    assert mock_load_vectorstore.called


@patch("engine.agent_core.subprocess.run")
@patch("engine.agent_core.load_vectorstore")
@patch("engine.agent_core.Path")
@patch("engine.agent_core.get_embedding_model")
def test_vectorstore_manager_get_vectorstore_missing_index(mock_get_embedding, mock_path, mock_load_vectorstore, mock_subprocess_run):
    """Test get_vectorstore method when index.faiss doesn't exist."""
    # Reset the singleton for testing
    VectorStoreManager._instance = None

    # Mock the embedding model
    mock_embedding = MagicMock()
    mock_get_embedding.return_value = mock_embedding

    # Mock Path to return a path that doesn't exist
    mock_path_instance = MagicMock()
    mock_path.return_value = mock_path_instance
    mock_path_instance.__truediv__.return_value = mock_path_instance
    mock_path_instance.exists.return_value = False

    # Mock load_vectorstore to return a mock vectorstore
    mock_vectorstore = MagicMock()
    mock_load_vectorstore.return_value = mock_vectorstore

    # Create a new instance
    manager = VectorStoreManager()

    # Test get_vectorstore with normal mode (should run ingest.py)
    profile = {"mode": "normal"}
    result = manager.get_vectorstore(profile)

    # Check results
    assert mock_subprocess_run.called
    assert mock_load_vectorstore.called
    assert result == mock_vectorstore


@pytest.mark.parametrize("input_text, mems, expected", [
    ("explain this", [], True),  # keyword match
    ("what is suhana", [], True),  # keyword match
    ("how does this work", [], True),  # keyword match
    ("summarize the article", [], True),  # keyword match
    ("random question", [FakeMemory("short fact")] * 3, True),  # short memory facts
    ("random question", [], True),  # no memory
    ("random question", [FakeMemory("one")], True),  # only one memory
    ("random question", [FakeMemory("this memory content is intentionally made longer than ten words to bypass short fact heuristic")]*5, False),  # valid long mem
])
def test_should_include_documents(input_text, mems, expected):
    assert agent_core.should_include_documents(input_text, mems) == expected


@patch("engine.agent_core.vectorstore_manager")
@patch("engine.agent_core.query_ollama", return_value="Mocked Ollama reply")
@patch("engine.agent_core.search_memory", return_value=[FakeMemory("test memory fact")])
@patch("engine.agent_core.summarize_profile_for_prompt", return_value="Profile summary")
def test_handle_input_ollama(mock_summary, mock_search, mock_ollama, mock_vectorstore_manager):
    mock_vectorstore = MagicMock()
    mock_vectorstore.similarity_search_with_score.return_value = [(FakeMemory("doc content"), 0.2)]
    mock_vectorstore_manager.get_vectorstore.return_value = mock_vectorstore

    profile = {"history": [], "preferences": {}, "name": "Test"}
    settings = {"llm_backend": "ollama", "llm_model": "fake-model"}

    result = agent_core.handle_input("test question", "ollama", profile, settings)

    assert result == "Mocked Ollama reply"
    assert mock_ollama.called
    assert "test question" in mock_ollama.call_args[0]
    assert "Profile summary" in mock_ollama.call_args[0][1]
    assert "doc content" in mock_ollama.call_args[0][1]


@patch("engine.agent_core.vectorstore_manager")
@patch("engine.agent_core.query_openai", return_value="Mocked OpenAI reply")
@patch("engine.agent_core.search_memory", return_value=[])
@patch("engine.agent_core.summarize_profile_for_prompt", return_value="Profile summary")
def test_handle_input_openai(mock_summary, mock_search, mock_openai, mock_vectorstore_manager):
    mock_vectorstore = MagicMock()
    mock_vectorstore.similarity_search_with_score.return_value = []
    mock_vectorstore_manager.get_vectorstore.return_value = mock_vectorstore

    profile = {"history": [], "preferences": {}, "name": "Test"}
    settings = {"llm_backend": "openai", "openai_model": "gpt-test"}

    result = agent_core.handle_input("what is this?", "openai", profile, settings)

    assert result == "Mocked OpenAI reply"
    assert mock_openai.called
    assert "what is this?" in mock_openai.call_args[0]


@patch("engine.agent_core.vectorstore_manager")
@patch("engine.agent_core.search_memory", return_value=[])
@patch("engine.agent_core.summarize_profile_for_prompt", return_value="Profile summary")
def test_handle_input_unknown_backend(mock_summary, mock_search, mock_vectorstore_manager):
    """Test handle_input with an unknown backend."""
    profile = {"history": [], "preferences": {}, "name": "Test"}
    settings = {"llm_backend": "unknown", "model": "test-model"}

    result = agent_core.handle_input("test question", "unknown", profile, settings)

    assert "❌ Unknown backend" in result


@patch("engine.agent_core.vectorstore_manager")
@patch("engine.agent_core.query_ollama")
@patch("engine.agent_core.search_memory", return_value=[])
@patch("engine.agent_core.summarize_profile_for_prompt", return_value="Profile summary")
def test_handle_input_exception_during_response(mock_summary, mock_search, mock_ollama, mock_vectorstore_manager):
    """Test handle_input when an exception occurs during response generation."""
    # Set up the mock to raise an exception
    mock_ollama.side_effect = Exception("Test exception")

    profile = {"history": [], "preferences": {}, "name": "Test"}
    settings = {"llm_backend": "ollama", "llm_model": "fake-model"}

    result = agent_core.handle_input("test question", "ollama", profile, settings)

    assert "❌ Error:" in result
    assert "Test exception" in result


@patch("engine.agent_core.vectorstore_manager")
@patch("engine.agent_core.query_ollama", return_value="Mocked Ollama reply")
@patch("engine.agent_core.search_memory", return_value=[FakeMemory("test memory fact")])
@patch("engine.agent_core.summarize_profile_for_prompt", return_value="Profile summary")
def test_handle_input_document_search_error(mock_summary, mock_search, mock_ollama, mock_vectorstore_manager):
    """Test handle_input when an error occurs during document search."""
    mock_vectorstore = MagicMock()
    mock_vectorstore.similarity_search_with_score.side_effect = Exception("Search error")
    mock_vectorstore_manager.get_vectorstore.return_value = mock_vectorstore

    profile = {"history": [], "preferences": {}, "name": "Test"}
    settings = {"llm_backend": "ollama", "llm_model": "fake-model"}

    # This should not raise an exception, but log the error and continue
    result = agent_core.handle_input("test question", "ollama", profile, settings)

    assert result == "Mocked Ollama reply"
    assert mock_ollama.called
    # The context should still include memory but not documents
    assert "test memory fact" in mock_ollama.call_args[0][1]
    assert mock_vectorstore.similarity_search_with_score.called


@patch("engine.agent_core.vectorstore_manager")
@patch("engine.agent_core.query_ollama", return_value="Mocked Ollama reply")
@patch("engine.agent_core.search_memory", return_value=[FakeMemory("test memory fact")])
@patch("engine.agent_core.summarize_profile_for_prompt", return_value="Profile summary")
def test_handle_input_no_vectorstore(mock_summary, mock_search, mock_ollama, mock_vectorstore_manager):
    """Test handle_input when vectorstore is not available."""
    # Return None to simulate vectorstore not available
    mock_vectorstore_manager.get_vectorstore.return_value = None

    profile = {"history": [], "preferences": {}, "name": "Test"}
    settings = {"llm_backend": "ollama", "llm_model": "fake-model"}

    result = agent_core.handle_input("test question", "ollama", profile, settings)

    assert result == "Mocked Ollama reply"
    assert mock_ollama.called
    # The context should still include memory but not documents
    assert "test memory fact" in mock_ollama.call_args[0][1]
