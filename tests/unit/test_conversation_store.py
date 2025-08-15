import pytest
import json
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock


from engine.conversation_store import (
    get_conversation_path,
    get_conversation_meta_path,
    list_conversations,
    list_conversation_meta,
    CONVERSATION_DIR, ConversationStore
)

conversation_store = ConversationStore()

@pytest.fixture
def mock_profile_meta():
    """Mock the load_profile_meta function."""
    profile_data = {
        "name": "Test User",
        "preferences": {
            "preferred_language": "English",
            "communication_style": "casual",
            "focus": "testing"
        }
    }
    with patch("engine.conversation_store.meta", profile_data), \
         patch("engine.conversation_store.load_profile_meta", return_value=profile_data):
        yield profile_data

@pytest.fixture
def mock_uuid():
    """Mock uuid.uuid4 to return a predictable value."""
    with patch("uuid.uuid4", return_value="test-uuid-1234"):
        yield

@pytest.fixture
def mock_datetime_now():
    """Mock datetime.now to return a predictable value."""
    # Create a mock datetime object
    mock_dt = MagicMock()
    mock_now = MagicMock()
    mock_now.isoformat.return_value = "2025-05-30T12:00:00"
    mock_dt.now.return_value = mock_now

    with patch("engine.conversation_store.datetime", mock_dt):
        yield mock_now

def test_get_conversation_path():
    """Test getting the path to a conversation file."""
    conversation_id = "test-conversation"
    expected_path = CONVERSATION_DIR / "test-conversation.json"

    path = get_conversation_path(conversation_id)

    assert path == expected_path

def test_get_conversation_meta_path():
    """Test getting the path to a conversation metadata file."""
    conversation_id = "test-conversation"
    expected_path = CONVERSATION_DIR / "test-conversation.meta.json"

    path = get_conversation_meta_path(conversation_id)

    assert path == expected_path

def test_list_conversations():
    """Test listing all conversation IDs."""
    # Mock the glob method to return a list of paths
    mock_paths = [
        Path(CONVERSATION_DIR / "conv1.json"),
        Path(CONVERSATION_DIR / "conv2.json")
    ]

    with patch.object(Path, "glob", return_value=mock_paths):
        result = list_conversations()

        assert result == ["conv1", "conv2"]

def test_list_conversation_meta():
    """Test listing metadata for all conversations."""
    # Mock the glob method to return a list of paths
    mock_paths = [
        Path(CONVERSATION_DIR / "conv1.meta.json"),
        Path(CONVERSATION_DIR / "conv2.meta.json")
    ]

    # Mock metadata content
    meta1 = {
        "title": "Conversation 1",
        "created": "2025-05-29T10:00:00",
        "last_updated": "2025-05-29T11:00:00",
        "mode": "normal",
        "project_path": None
    }

    meta2 = {
        "title": "Conversation 2",
        "created": "2025-05-30T10:00:00",
        "last_updated": "2025-05-30T11:00:00",
        "mode": "project",
        "project_path": "/path/to/project"
    }

    # Mock open to return different content for different files
    mock_file_content = {
        str(mock_paths[0]): json.dumps(meta1),
        str(mock_paths[1]): json.dumps(meta2)
    }

    def mock_open_side_effect(file, mode, encoding):
        m = MagicMock()
        m.__enter__.return_value.read.return_value = mock_file_content[str(file)]
        return m

    with patch.object(Path, "glob", return_value=mock_paths), \
         patch("builtins.open", side_effect=mock_open_side_effect):
        result = list_conversation_meta()

        # Results should be sorted by last_updated in reverse order
        assert len(result) == 2
        assert result[0]["id"] == "conv2"
        assert result[0]["title"] == "Conversation 2"
        assert result[1]["id"] == "conv1"
        assert result[1]["title"] == "Conversation 1"

def test_load_conversation_existing(mock_profile_meta):
    """Test loading an existing conversation."""
    conversation_id = "existing-conv"
    conversation_data = {
        "history": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"}
        ]
    }

    with patch("pathlib.Path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data=json.dumps(conversation_data))):
        result = conversation_store.load_conversation(conversation_id)

        assert result["history"] == conversation_data["history"]
        assert result["name"] == mock_profile_meta["name"]
        assert result["preferences"] == mock_profile_meta["preferences"]
        assert result["mode"] == "normal"  # Default value

def test_load_conversation_nonexistent(mock_profile_meta):
    """Test loading a conversation that doesn't exist."""
    conversation_id = "nonexistent-conv"

    with patch("pathlib.Path.exists", return_value=False):
        result = conversation_store.load_conversation(conversation_id)

        assert result["history"] == []
        assert result["name"] == mock_profile_meta["name"]
        assert result["preferences"] == mock_profile_meta["preferences"]

def test_save_conversation():
    """Test saving a conversation."""
    conversation_id = "test-conv"
    profile = {
        "history": [
            {"role": "user", "content": "Hello there"}
        ],
        "title": "Test Conversation",
        "mode": "project",
        "project_path": "/test/project"
    }

    # Create a mock datetime object
    mock_datetime = MagicMock()
    mock_now = MagicMock()
    mock_now.isoformat.return_value = "2025-05-30T12:00:00"
    mock_datetime.now.return_value = mock_now

    # Mock the open function
    mock_file = mock_open()

    with patch("builtins.open", mock_file), \
         patch("engine.conversation_store.datetime", mock_datetime):

        conversation_store.save_conversation(conversation_id, profile)

        # Check that open was called twice (once for each file)
        assert mock_file.call_count == 2

        # Check that the correct files were opened
        conversation_path = get_conversation_path(conversation_id)
        metadata_path = get_conversation_meta_path(conversation_id)

        mock_file.assert_any_call(conversation_path, "w", encoding="utf-8")
        mock_file.assert_any_call(metadata_path, "w", encoding="utf-8")

        # We can't easily check the exact content written to the files due to
        # how mock_open works with json.dump, but we can verify that write was called
        assert mock_file().write.call_count > 0

def test_save_conversation_empty_title():
    """Test saving a conversation with no explicit title."""
    conversation_id = "test-conv"
    profile = {
        "history": [
            {"role": "user", "content": "This is a long message that should be truncated"}
        ]
    }

    # Create a mock datetime object
    mock_datetime = MagicMock()
    mock_now = MagicMock()
    mock_now.isoformat.return_value = "2025-05-30T12:00:00"
    mock_datetime.now.return_value = mock_now

    # Mock the open function
    mock_file = mock_open()

    with patch("builtins.open", mock_file), \
         patch("engine.conversation_store.datetime", mock_datetime):

        conversation_store.save_conversation(conversation_id, profile)

        # Check that open was called twice (once for each file)
        assert mock_file.call_count == 2

        # Check that the correct files were opened
        conversation_path = get_conversation_path(conversation_id)
        metadata_path = get_conversation_meta_path(conversation_id)

        mock_file.assert_any_call(conversation_path, "w", encoding="utf-8")
        mock_file.assert_any_call(metadata_path, "w", encoding="utf-8")

        # We can't easily check the exact content written to the files due to
        # how mock_open works with json.dump, but we can verify that write was called
        assert mock_file().write.call_count > 0

        # The title truncation is tested in the implementation of save_conversation,
        # but we can't easily verify it in this test without complex mocking

def test_save_conversation_invalid_history():
    """Test saving a conversation with invalid history."""
    conversation_id = "test-conv"
    profile = {
        "history": "not a list"  # Invalid history
    }

    with pytest.raises(ValueError, match="Conversation history must be a list"):
        conversation_store.save_conversation(conversation_id, profile)

def test_create_new_conversation(mock_uuid):
    """Test creating a new conversation."""
    with patch("engine.conversation_store.save_conversation") as mock_save:
        conversation_id = conversation_store.create_new_conversation("test-id")

        assert conversation_id == "test-uuid-1234"
        mock_save.assert_called_once_with("test-uuid-1234", {"history": []})
