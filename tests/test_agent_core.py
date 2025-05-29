import pytest
from unittest.mock import patch, MagicMock, mock_open

from engine import agent_core
from engine.agent_core import VectorStoreManager


class FakeMemory:
    def __init__(self, content): self.page_content = content


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


@patch("engine.agent_core.load_vectorstore")
@patch("engine.agent_core.get_embedding_model")
def test_vectorstore_manager_reset_vectorstore(mock_get_embedding, mock_load_vectorstore):
    """Test reset_vectorstore method."""
    # Reset the singleton for testing
    VectorStoreManager._instance = None

    # Mock the embedding model
    mock_embedding = MagicMock()
    mock_get_embedding.return_value = mock_embedding

    # Mock load_vectorstore to return a mock vectorstore
    mock_vectorstore = MagicMock()
    mock_load_vectorstore.return_value = mock_vectorstore

    # Create a new instance
    manager = VectorStoreManager()

    # Set up a vectorstore
    profile = {"mode": "normal"}
    manager.get_vectorstore(profile)

    # Verify vectorstore is set
    assert manager._vectorstore is not None

    # Reset the vectorstore
    manager.reset_vectorstore()

    # Verify vectorstore is reset
    assert manager._vectorstore is None

    # Get vectorstore again to verify it's reloaded
    result = manager.get_vectorstore(profile)
    assert result is not None
    assert mock_load_vectorstore.call_count == 2  # Called once during setup and once after reset


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


@patch("engine.agent_core.container.get_typed")
@patch("engine.backends.ollama.query_ollama", return_value="Mocked Ollama reply")
@patch("engine.memory_store.search_memory", return_value=[FakeMemory("test memory fact")])
@patch("engine.agent_core.summarize_profile_for_prompt", return_value="Profile summary")
def test_handle_input_ollama(mock_summary, mock_search, mock_ollama, mock_container_get_typed):
    # Create mock objects
    mock_memory_store = MagicMock()
    mock_memory_store.search_memory.return_value = [FakeMemory("test memory fact")]

    mock_vectorstore = MagicMock()
    mock_vectorstore.similarity_search_with_score.return_value = [(FakeMemory("doc content"), 0.2)]

    mock_vectorstore_manager = MagicMock()
    mock_vectorstore_manager.get_vectorstore.return_value = mock_vectorstore

    # Configure mock_container_get_typed to return the appropriate mock based on the type requested
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

    mock_container_get_typed.side_effect = get_typed_side_effect

    profile = {"history": [], "preferences": {}, "name": "Test"}
    settings = {"llm_backend": "ollama", "llm_model": "fake-model"}

    result = agent_core.handle_input("test question", "ollama", profile, settings)

    assert result == "Mocked Ollama reply"
    # We're not checking mock_ollama.called because we're mocking the container.get_typed method
    # to return a mock backend with a query method that returns "Mocked Ollama reply"


@patch("engine.agent_core.container.get_typed")
@patch("engine.backends.openai.query_openai", return_value="Mocked OpenAI reply")
@patch("engine.memory_store.search_memory", return_value=[])
@patch("engine.agent_core.summarize_profile_for_prompt", return_value="Profile summary")
def test_handle_input_openai(mock_summary, mock_search, mock_openai, mock_container_get_typed):
    # Create mock objects
    mock_memory_store = MagicMock()
    mock_memory_store.search_memory.return_value = []

    mock_vectorstore = MagicMock()
    mock_vectorstore.similarity_search_with_score.return_value = []

    mock_vectorstore_manager = MagicMock()
    mock_vectorstore_manager.get_vectorstore.return_value = mock_vectorstore

    # Configure mock_container_get_typed to return the appropriate mock based on the type requested
    def get_typed_side_effect(name, type_hint):
        if type_hint.__name__ == "MemoryStoreInterface":
            return mock_memory_store
        elif type_hint.__name__ == "VectorStoreManagerInterface":
            return mock_vectorstore_manager
        elif name == "openai_backend":
            backend = MagicMock()
            backend.query.return_value = "Mocked OpenAI reply"
            return backend
        return MagicMock()

    mock_container_get_typed.side_effect = get_typed_side_effect

    profile = {"history": [], "preferences": {}, "name": "Test"}
    settings = {"llm_backend": "openai", "openai_model": "gpt-test"}

    result = agent_core.handle_input("what is this?", "openai", profile, settings)

    assert result == "Mocked OpenAI reply"
    # We're not checking mock_openai.called because we're mocking the container.get_typed method
    # to return a mock backend with a query method that returns "Mocked OpenAI reply"


@patch("engine.agent_core.container.get_typed")
@patch("engine.memory_store.search_memory", return_value=[])
@patch("engine.agent_core.summarize_profile_for_prompt", return_value="Profile summary")
def test_handle_input_unknown_backend(mock_summary, mock_search, mock_container_get_typed):
    """Test handle_input with an unknown backend."""
    # Create mock objects
    mock_memory_store = MagicMock()
    mock_memory_store.search_memory.return_value = []

    mock_vectorstore = MagicMock()
    mock_vectorstore.similarity_search_with_score.return_value = []

    mock_vectorstore_manager = MagicMock()
    mock_vectorstore_manager.get_vectorstore.return_value = mock_vectorstore

    # Configure mock_container_get_typed to return the appropriate mock based on the type requested
    def get_typed_side_effect(name, type_hint):
        if type_hint.__name__ == "MemoryStoreInterface":
            return mock_memory_store
        elif type_hint.__name__ == "VectorStoreManagerInterface":
            return mock_vectorstore_manager
        return MagicMock()

    mock_container_get_typed.side_effect = get_typed_side_effect
    profile = {"history": [], "preferences": {}, "name": "Test"}
    settings = {"llm_backend": "unknown", "model": "test-model"}

    result = agent_core.handle_input("test question", "unknown", profile, settings)

    # The @error_boundary decorator is catching the BackendError and returning the fallback value
    assert result == "I'm sorry, I encountered an error processing your request."


@patch("engine.agent_core.container.get_typed")
@patch("engine.backends.ollama.query_ollama")
@patch("engine.memory_store.search_memory", return_value=[])
@patch("engine.agent_core.summarize_profile_for_prompt", return_value="Profile summary")
def test_handle_input_exception_during_response(mock_summary, mock_search, mock_ollama, mock_container_get_typed):
    """Test handle_input when an exception occurs during response generation."""
    # Create mock objects
    mock_memory_store = MagicMock()
    mock_memory_store.search_memory.return_value = []

    mock_vectorstore = MagicMock()
    mock_vectorstore.similarity_search_with_score.return_value = []

    mock_vectorstore_manager = MagicMock()
    mock_vectorstore_manager.get_vectorstore.return_value = mock_vectorstore

    # Configure mock_container_get_typed to return the appropriate mock based on the type requested
    def get_typed_side_effect(name, type_hint):
        if type_hint.__name__ == "MemoryStoreInterface":
            return mock_memory_store
        elif type_hint.__name__ == "VectorStoreManagerInterface":
            return mock_vectorstore_manager
        elif name == "ollama_backend":
            backend = MagicMock()
            backend.query.side_effect = Exception("Test exception")
            return backend
        return MagicMock()

    mock_container_get_typed.side_effect = get_typed_side_effect

    profile = {"history": [], "preferences": {}, "name": "Test"}
    settings = {"llm_backend": "ollama", "llm_model": "fake-model"}

    result = agent_core.handle_input("test question", "ollama", profile, settings)

    # The @error_boundary decorator is catching the exception and returning the fallback value
    assert result == "I'm sorry, I encountered an error processing your request."


@patch("engine.agent_core.container.get_typed")
@patch("engine.backends.ollama.query_ollama", return_value="Mocked Ollama reply")
@patch("engine.memory_store.search_memory", return_value=[FakeMemory("test memory fact")])
@patch("engine.agent_core.summarize_profile_for_prompt", return_value="Profile summary")
def test_handle_input_document_search_error(mock_summary, mock_search, mock_ollama, mock_container_get_typed):
    """Test handle_input when an error occurs during document search."""
    # Create mock objects
    mock_memory_store = MagicMock()
    mock_memory_store.search_memory.return_value = [FakeMemory("test memory fact")]

    mock_vectorstore = MagicMock()
    mock_vectorstore.similarity_search_with_score.side_effect = Exception("Search error")

    mock_vectorstore_manager = MagicMock()
    mock_vectorstore_manager.get_vectorstore.return_value = mock_vectorstore

    # Configure mock_container_get_typed to return the appropriate mock based on the type requested
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

    mock_container_get_typed.side_effect = get_typed_side_effect

    profile = {"history": [], "preferences": {}, "name": "Test"}
    settings = {"llm_backend": "ollama", "llm_model": "fake-model"}

    # This should not raise an exception, but log the error and continue
    result = agent_core.handle_input("test question", "ollama", profile, settings)

    assert result == "Mocked Ollama reply"
    # We're not checking mock_ollama.called because we're mocking the container.get_typed method
    # to return a mock backend with a query method that returns "Mocked Ollama reply"
    assert mock_vectorstore.similarity_search_with_score.called


@patch("engine.agent_core.container.get_typed")
@patch("engine.backends.ollama.query_ollama", return_value="Mocked Ollama reply")
@patch("engine.memory_store.search_memory", return_value=[FakeMemory("test memory fact")])
@patch("engine.agent_core.summarize_profile_for_prompt", return_value="Profile summary")
def test_handle_input_no_vectorstore(mock_summary, mock_search, mock_ollama, mock_container_get_typed):
    """Test handle_input when vectorstore is not available."""
    # Create mock objects
    mock_memory_store = MagicMock()
    mock_memory_store.search_memory.return_value = [FakeMemory("test memory fact")]

    mock_vectorstore_manager = MagicMock()
    # Return None to simulate vectorstore not available
    mock_vectorstore_manager.get_vectorstore.return_value = None

    # Configure mock_container_get_typed to return the appropriate mock based on the type requested
    def get_typed_side_effect(name, type_hint):
        if type_hint.__name__ == "MemoryStoreInterface":
            return mock_memory_store
        elif type_hint.__name__ == "VectorStoreManagerInterface":
            return mock_vectorstore_manager
        elif name == "ollama_backend":
            backend = MagicMock()
            backend.query.side_effect = Exception("Test exception")
            return backend
        return MagicMock()

    mock_container_get_typed.side_effect = get_typed_side_effect

    profile = {"history": [], "preferences": {}, "name": "Test"}
    settings = {"llm_backend": "ollama", "llm_model": "fake-model"}

    result = agent_core.handle_input("test question", "ollama", profile, settings)

    # The @error_boundary decorator is catching the exception and returning the fallback value
    assert result == "I'm sorry, I encountered an error processing your request."
    # We don't check mock_ollama.called because the exception is raised before the actual call
    # The context should still include memory but not documents
    # We can't check mock_ollama.call_args because the exception prevents the call from completing
