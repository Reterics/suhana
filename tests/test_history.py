import pytest
from unittest.mock import patch, MagicMock

from engine.history import trim_message_history

@pytest.fixture
def mock_tiktoken():
    """Mock the tiktoken library."""
    mock_encoder = MagicMock()

    # Configure the encode method to return a list with length equal to the number of words
    # This is a simple approximation for testing purposes
    def mock_encode(text):
        return [0] * len(text.split())

    mock_encoder.encode.side_effect = mock_encode

    with patch("engine.history.tiktoken.encoding_for_model", return_value=mock_encoder):
        yield mock_encoder

def test_trim_message_history_all_fit(mock_tiktoken):
    """Test when all messages fit within the token limit."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
        {"role": "user", "content": "How are you?"},
        {"role": "assistant", "content": "I'm doing well, thank you!"}
    ]

    # With our mock, each message is counted as the number of words
    # Total tokens: 5 (system) + 1 (Hello) + 2 (Hi there) + 3 (How are you?) + 6 (I'm doing well...) = 17
    # This is well below our max_tokens of 100
    result = trim_message_history(messages, max_tokens=100)

    # All messages should be included
    assert len(result) == len(messages)
    assert result[0] == messages[0]  # System message is always first
    assert result[-1] == messages[-1]  # Last message should be included

def test_trim_message_history_some_trimmed(mock_tiktoken):
    """Test when some messages need to be trimmed due to token limit."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "This is a long message that should be trimmed"},
        {"role": "assistant", "content": "Here is a detailed response that should also be trimmed"},
        {"role": "user", "content": "Short message"},
        {"role": "assistant", "content": "Short reply"}
    ]

    # With our mock, the token counts would be:
    # System: 5, User1: 9, Assistant1: 10, User2: 2, Assistant2: 2
    # Total: 28
    # If we set max_tokens to 15, we should only get:
    # System (5) + Assistant2 (2) + User2 (2) = 9 tokens
    result = trim_message_history(messages, max_tokens=15)

    # We should have the system message and the last two messages
    assert len(result) == 3
    assert result[0] == messages[0]  # System message is always first
    assert result[1] == messages[3]  # Second-to-last message
    assert result[2] == messages[4]  # Last message

def test_trim_message_history_only_system(mock_tiktoken):
    """Test when only the system message fits within the token limit."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "This is a very long message that exceeds the token limit"}
    ]

    # System: 5 tokens, User: 12 tokens
    # If max_tokens is 10, only the system message should fit
    result = trim_message_history(messages, max_tokens=10)

    # We should only have the system message
    assert len(result) == 1
    assert result[0] == messages[0]

def test_trim_message_history_empty():
    """Test with an empty message list."""
    with pytest.raises(IndexError):
        # This should raise an IndexError because the function assumes at least one message
        trim_message_history([])

def test_trim_message_history_different_model():
    """Test using a different model parameter."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello"}
    ]

    # Mock tiktoken to verify the model parameter is passed correctly
    mock_encoder = MagicMock()
    mock_encoder.encode.return_value = [0] * 5  # Simulate 5 tokens per message

    with patch("engine.history.tiktoken.encoding_for_model", return_value=mock_encoder) as mock_encoding:
        trim_message_history(messages, model="gpt-4")

        # Verify the correct model was used
        mock_encoding.assert_called_once_with("gpt-4")

def test_trim_message_history_order():
    """Test that messages are added in the correct order."""
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "user1"},
        {"role": "assistant", "content": "assistant1"},
        {"role": "user", "content": "user2"},
        {"role": "assistant", "content": "assistant2"}
    ]

    # Mock tiktoken to return a fixed token count
    mock_encoder = MagicMock()
    mock_encoder.encode.return_value = [0] * 5  # 5 tokens per message

    with patch("engine.history.tiktoken.encoding_for_model", return_value=mock_encoder):
        # Set max_tokens to allow only 3 messages (15 tokens)
        result = trim_message_history(messages, max_tokens=15)

        # We should have the system message and the last two messages in the correct order
        assert len(result) == 3
        assert result[0]["content"] == "system"
        assert result[1]["content"] == "user2"
        assert result[2]["content"] == "assistant2"
