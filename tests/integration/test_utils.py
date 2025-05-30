import pytest
from unittest.mock import patch, MagicMock, mock_open

from engine.utils import (
    configure_logging,
    get_embedding_model,
    save_vectorstore,
    load_vectorstore
)

@pytest.fixture
def mock_huggingface_embeddings():
    """Mock HuggingFaceEmbeddings."""
    with patch("engine.utils.HuggingFaceEmbeddings") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock, mock_instance

@pytest.fixture
def mock_faiss():
    """Mock FAISS vector store."""
    with patch("engine.utils.FAISS") as mock:
        mock_instance = MagicMock()
        mock.from_documents.return_value = mock_instance
        mock.load_local.return_value = mock_instance
        yield mock, mock_instance

@pytest.fixture
def mock_path():
    """Mock Path operations."""
    with patch("engine.utils.Path") as mock_path_class:
        mock_path_instance = MagicMock()
        mock_path_class.return_value = mock_path_instance
        mock_path_instance.__truediv__.return_value = mock_path_instance  # For path / "file" operations
        yield mock_path_class, mock_path_instance

@pytest.mark.expensive
def test_configure_logging():
    """Test that configure_logging calls get_logger."""
    with patch("engine.logging_config.get_logger") as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Call the function
        result = configure_logging("test_module")

        # Verify get_logger was called with the correct name
        mock_get_logger.assert_called_once_with("test_module")

        # Verify the result is the logger from get_logger
        assert result == mock_logger

@pytest.mark.expensive
def test_get_embedding_model(mock_huggingface_embeddings):
    """Test get_embedding_model creates a HuggingFaceEmbeddings instance."""
    mock_class, mock_instance = mock_huggingface_embeddings

    # Call with default model name
    result = get_embedding_model()

    # Verify HuggingFaceEmbeddings was called with the default model name
    mock_class.assert_called_once_with(model_name="all-MiniLM-L6-v2")

    # Verify the result is the mock instance
    assert result == mock_instance

    # Reset the mock and call with a custom model name
    mock_class.reset_mock()
    result = get_embedding_model("custom-model")

    # Verify HuggingFaceEmbeddings was called with the custom model name
    mock_class.assert_called_once_with(model_name="custom-model")

@pytest.mark.expensive
def test_save_vectorstore(mock_faiss, mock_path):
    """Test save_vectorstore creates and saves a FAISS vector store."""
    mock_faiss_class, mock_faiss_instance = mock_faiss
    mock_path_class, mock_path_instance = mock_path

    # Create test documents and embedding model
    documents = [MagicMock(), MagicMock()]
    embedding_model = MagicMock()
    target_dir = "test_dir"
    metadata = {"test": "metadata"}

    # Call the function
    result = save_vectorstore(documents, embedding_model, target_dir, metadata)

    # Verify Path was called with the target directory
    mock_path_class.assert_called_once_with(target_dir)

    # Verify directory was created
    mock_path_instance.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    # Verify FAISS.from_documents was called with the documents and embedding model
    mock_faiss_class.from_documents.assert_called_once_with(documents, embedding_model)

    # Verify save_local was called with the target directory
    mock_faiss_instance.save_local.assert_called_once_with(str(mock_path_instance))

    # Verify metadata was saved
    with patch("builtins.open", mock_open()) as mock_file:
        # Call the function again to test metadata saving
        save_vectorstore(documents, embedding_model, target_dir, metadata)

        # Verify open was called with the metadata file path
        mock_file.assert_called_with(mock_path_instance / 'metadata.json', 'w')

        # Verify json.dump was called with the metadata
        mock_file().write.assert_called()

    # Verify the result is the FAISS instance
    assert result == mock_faiss_instance

@pytest.mark.expensive
def test_save_vectorstore_no_metadata(mock_faiss, mock_path):
    """Test save_vectorstore without metadata."""
    mock_faiss_class, mock_faiss_instance = mock_faiss
    mock_path_class, mock_path_instance = mock_path

    # Create test documents and embedding model
    documents = [MagicMock(), MagicMock()]
    embedding_model = MagicMock()
    target_dir = "test_dir"

    # Call the function without metadata
    result = save_vectorstore(documents, embedding_model, target_dir)

    # Verify Path was called with the target directory
    mock_path_class.assert_called_once_with(target_dir)

    # Verify directory was created
    mock_path_instance.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    # Verify FAISS.from_documents was called with the documents and embedding model
    mock_faiss_class.from_documents.assert_called_once_with(documents, embedding_model)

    # Verify save_local was called with the target directory
    mock_faiss_instance.save_local.assert_called_once_with(str(mock_path_instance))

    # Verify the result is the FAISS instance
    assert result == mock_faiss_instance

@pytest.mark.expensive
def test_load_vectorstore_existing(mock_faiss, mock_huggingface_embeddings):
    """Test loading an existing vector store."""
    mock_faiss_class, mock_faiss_instance = mock_faiss
    mock_hf_class, mock_hf_instance = mock_huggingface_embeddings

    # Mock Path.exists to return True
    with patch("pathlib.Path.exists", return_value=True):
        # Call the function with a path
        result = load_vectorstore("test_path")

        # Verify HuggingFaceEmbeddings was created (default embedding model)
        mock_hf_class.assert_called_once_with(model_name="all-MiniLM-L6-v2")

        # Verify FAISS.load_local was called with the path and embedding model
        mock_faiss_class.load_local.assert_called_once_with(
            "test_path",
            mock_hf_instance,
            allow_dangerous_deserialization=True
        )

        # Verify the result is the FAISS instance
        assert result == mock_faiss_instance

        # Reset mocks and call with a custom embedding model
        mock_faiss_class.reset_mock()
        mock_hf_class.reset_mock()

        custom_embedding = MagicMock()
        result = load_vectorstore("test_path", custom_embedding)

        # Verify HuggingFaceEmbeddings was not created (custom model provided)
        mock_hf_class.assert_not_called()

        # Verify FAISS.load_local was called with the path and custom embedding model
        mock_faiss_class.load_local.assert_called_once_with(
            "test_path",
            custom_embedding,
            allow_dangerous_deserialization=True
        )

@pytest.mark.expensive
def test_load_vectorstore_not_found():
    """Test loading a vector store that doesn't exist."""
    # Mock Path.exists to return False
    with patch("pathlib.Path.exists", return_value=False), \
         patch("engine.utils.logger") as mock_logger:

        # Call the function
        result = load_vectorstore("test_path")

        # Verify logger.error was called
        mock_logger.error.assert_called_once()
        args, _ = mock_logger.error.call_args
        assert "Vector store not found" in args[0]

        # Verify the result is None
        assert result is None

@pytest.mark.expensive
def test_load_vectorstore_error():
    """Test error handling when loading a vector store."""
    # Mock Path.exists to return True
    with patch("pathlib.Path.exists", return_value=True), \
         patch("engine.utils.FAISS.load_local", side_effect=Exception("Test error")), \
         patch("engine.utils.logger") as mock_logger:

        # Call the function
        result = load_vectorstore("test_path")

        # Verify logger.error was called
        mock_logger.error.assert_called_once()
        args, _ = mock_logger.error.call_args
        assert "Failed to load vector store" in args[0]

        # Verify the result is None
        assert result is None
