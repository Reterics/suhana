import pytest
from unittest.mock import patch, MagicMock


from engine.memory_store import (
    load_memory_store,
    save_memory_store,
    add_memory_fact,
    search_memory,
    recall_memory,
    forget_memory,
    MEMORY_PATH,
    EMBED_MODEL
)

@pytest.fixture
def mock_faiss():
    """Mock the FAISS vector store."""
    with patch("engine.memory_store.FAISS") as mock:
        # Create a mock instance that will be returned by FAISS.load_local or FAISS.from_documents
        mock_instance = MagicMock()
        mock.load_local.return_value = mock_instance
        mock.from_documents.return_value = mock_instance
        yield mock, mock_instance

@pytest.fixture
def mock_path_exists():
    """Mock Path.exists to control whether the memory store exists."""
    with patch("pathlib.Path.exists") as mock:
        yield mock

def test_load_memory_store_existing(mock_faiss, mock_path_exists):
    """Test loading an existing memory store."""
    mock_path_exists.return_value = True
    mock_faiss_class, mock_faiss_instance = mock_faiss

    result = load_memory_store()

    # Verify FAISS.load_local was called with correct parameters
    mock_faiss_class.load_local.assert_called_once_with(
        str(MEMORY_PATH),
        EMBED_MODEL,
        allow_dangerous_deserialization=True
    )

    # Verify the result is the mock instance
    assert result == mock_faiss_instance

def test_load_memory_store_new(mock_faiss, mock_path_exists):
    """Test creating a new memory store when one doesn't exist."""
    mock_path_exists.return_value = False
    mock_faiss_class, mock_faiss_instance = mock_faiss

    result = load_memory_store()

    # Verify FAISS.from_documents was called with empty list
    mock_faiss_class.from_documents.assert_called_once()
    args, _ = mock_faiss_class.from_documents.call_args
    assert args[0] == []  # Empty document list
    assert args[1] == EMBED_MODEL

    # Verify the result is the mock instance
    assert result == mock_faiss_instance

def test_save_memory_store(mock_faiss):
    """Test saving a memory store."""
    mock_faiss_class, mock_faiss_instance = mock_faiss

    save_memory_store(mock_faiss_instance)

    # Verify save_local was called with correct path
    mock_faiss_instance.save_local.assert_called_once_with(str(MEMORY_PATH))

def test_add_memory_fact_existing_store(mock_faiss, mock_path_exists):
    """Test adding a memory fact to an existing store."""
    mock_path_exists.return_value = True
    mock_faiss_class, mock_faiss_instance = mock_faiss

    test_text = "This is a test memory fact"
    add_memory_fact(test_text)

    # Verify load_memory_store was used (via FAISS.load_local)
    mock_faiss_class.load_local.assert_called_once()

    # Verify add_documents was called with a document containing our text
    mock_faiss_instance.add_documents.assert_called_once()
    args, _ = mock_faiss_instance.add_documents.call_args
    assert len(args[0]) == 1
    assert args[0][0].page_content == test_text

    # Verify save_local was called
    mock_faiss_instance.save_local.assert_called_once()

def test_add_memory_fact_new_store(mock_faiss, mock_path_exists):
    """Test adding a memory fact when no store exists."""
    mock_path_exists.return_value = False
    mock_faiss_class, mock_faiss_instance = mock_faiss

    test_text = "This is a test memory fact"
    add_memory_fact(test_text)

    # Verify from_documents was called with a document containing our text
    mock_faiss_class.from_documents.assert_called_once()
    args, _ = mock_faiss_class.from_documents.call_args
    assert len(args[0]) == 1
    assert args[0][0].page_content == test_text

    # Verify save_local was called
    mock_faiss_instance.save_local.assert_called_once()

def test_search_memory(mock_faiss):
    """Test searching memory."""
    mock_faiss_class, mock_faiss_instance = mock_faiss

    # Set up mock return value for similarity_search
    mock_doc1 = MagicMock()
    mock_doc1.page_content = "Result 1"
    mock_doc2 = MagicMock()
    mock_doc2.page_content = "Result 2"
    mock_faiss_instance.similarity_search.return_value = [mock_doc1, mock_doc2]

    results = search_memory("test query", k=2)

    # Verify similarity_search was called with correct parameters
    mock_faiss_instance.similarity_search.assert_called_once_with("test query", k=2)

    # Verify results match what the mock returned
    assert results == [mock_doc1, mock_doc2]

def test_recall_memory(mock_faiss):
    """Test recalling all memory."""
    mock_faiss_class, mock_faiss_instance = mock_faiss

    # Set up mock return value for similarity_search
    mock_doc1 = MagicMock()
    mock_doc1.page_content = "Memory 1"
    mock_doc2 = MagicMock()
    mock_doc2.page_content = "Memory 2"
    mock_faiss_instance.similarity_search.return_value = [mock_doc1, mock_doc2]

    results = recall_memory()

    # Verify similarity_search was called with empty query and k=50
    mock_faiss_instance.similarity_search.assert_called_once_with("", k=50)

    # Verify results are the page_content values
    assert results == ["Memory 1", "Memory 2"]

def test_forget_memory_with_matches(mock_faiss):
    """Test forgetting memory with matching keyword."""
    mock_faiss_class, mock_faiss_instance = mock_faiss

    # Set up mock return value for similarity_search
    mock_doc1 = MagicMock()
    mock_doc1.page_content = "Memory about cats"
    mock_doc2 = MagicMock()
    mock_doc2.page_content = "Memory about dogs"
    mock_doc3 = MagicMock()
    mock_doc3.page_content = "Another cat memory"
    mock_faiss_instance.similarity_search.return_value = [mock_doc1, mock_doc2, mock_doc3]

    # Call forget_memory with "cat" keyword
    result = forget_memory("cat")

    # Verify similarity_search was called
    mock_faiss_instance.similarity_search.assert_called_once_with("", k=50)

    # Verify from_documents was called with only the dog memory
    mock_faiss_class.from_documents.assert_called_once()
    args, _ = mock_faiss_class.from_documents.call_args
    assert len(args[0]) == 1
    assert args[0][0].page_content == "Memory about dogs"

    # Verify save_local was called
    mock_faiss_instance.save_local.assert_called_once()

    # Verify result is 2 (number of items removed)
    assert result == 2

def test_forget_memory_no_matches(mock_faiss):
    """Test forgetting memory with no matching keyword."""
    mock_faiss_class, mock_faiss_instance = mock_faiss

    # Set up mock return value for similarity_search
    mock_doc1 = MagicMock()
    mock_doc1.page_content = "Memory about cats"
    mock_doc2 = MagicMock()
    mock_doc2.page_content = "Memory about dogs"
    mock_faiss_instance.similarity_search.return_value = [mock_doc1, mock_doc2]

    # Call forget_memory with keyword that doesn't match
    result = forget_memory("elephant")

    # Verify similarity_search was called
    mock_faiss_instance.similarity_search.assert_called_once_with("", k=50)

    # Verify from_documents was NOT called (no new store created)
    mock_faiss_class.from_documents.assert_not_called()

    # Verify save_local was NOT called
    mock_faiss_instance.save_local.assert_not_called()

    # Verify result is 0 (no items removed)
    assert result == 0
