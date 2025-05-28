import pytest
from unittest.mock import patch, MagicMock, call

from engine import agent


@patch("engine.agent.load_settings")
@patch("engine.agent.create_new_conversation")
@patch("engine.agent.load_conversation")
@patch("engine.agent.load_tools")
@patch("engine.agent.input", return_value="exit")
def test_run_agent_exit_command(mock_input, mock_load_tools, mock_load_conversation,
                               mock_create_conversation, mock_load_settings):
    """Test that the run_agent function exits correctly when 'exit' is entered."""
    # Setup mocks
    mock_load_settings.return_value = {"llm_backend": "ollama", "llm_model": "llama3"}
    mock_create_conversation.return_value = "test-conversation-id"
    mock_load_conversation.return_value = {"history": [], "preferences": {}}
    mock_load_tools.return_value = []

    # Run the function
    agent.run_agent()

    # Verify the function called the expected dependencies
    mock_load_settings.assert_called_once()
    mock_create_conversation.assert_called_once()
    mock_load_conversation.assert_called_once_with("test-conversation-id")
    mock_load_tools.assert_called_once()
    mock_input.assert_called_once()


@patch("engine.agent.load_settings")
@patch("engine.agent.create_new_conversation")
@patch("engine.agent.load_conversation")
@patch("engine.agent.load_tools")
@patch("engine.agent.save_conversation")
@patch("engine.agent.input")
@patch("engine.agent.handle_input")
def test_run_agent_normal_input(mock_handle_input, mock_input, mock_save_conversation,
                               mock_load_tools, mock_load_conversation,
                               mock_create_conversation, mock_load_settings):
    """Test that the run_agent function processes normal input correctly."""
    # Setup mocks
    mock_load_settings.return_value = {
        "llm_backend": "ollama",
        "llm_model": "llama3",
        "voice": False,
        "streaming": False
    }
    mock_create_conversation.return_value = "test-conversation-id"
    mock_profile = {"history": [], "preferences": {}}
    mock_load_conversation.return_value = mock_profile
    mock_load_tools.return_value = []

    # Set up input to first provide a normal query, then exit
    mock_input.side_effect = ["hello", "exit"]
    mock_handle_input.return_value = "Hello, I'm Suhana. How can I help you?"

    # Run the function
    agent.run_agent()

    # Verify the function called the expected dependencies
    assert mock_input.call_count == 2
    mock_handle_input.assert_called_once_with("hello", "ollama", mock_profile, mock_load_settings.return_value)
    mock_save_conversation.assert_called_once_with("test-conversation-id", mock_profile)


@patch("engine.agent.load_settings")
@patch("engine.agent.create_new_conversation")
@patch("engine.agent.load_conversation")
@patch("engine.agent.load_tools")
@patch("engine.agent.input")
@patch("engine.agent.match_and_run_tools")
def test_run_agent_tool_match(mock_match_tools, mock_input, mock_load_tools,
                             mock_load_conversation, mock_create_conversation,
                             mock_load_settings):
    """Test that the run_agent function handles tool matches correctly."""
    # Setup mocks
    mock_load_settings.return_value = {"llm_backend": "ollama", "llm_model": "llama3"}
    mock_create_conversation.return_value = "test-conversation-id"
    mock_load_conversation.return_value = {"history": [], "preferences": {}}
    mock_load_tools.return_value = []

    # Set up input to first provide a command that matches a tool, then exit
    mock_input.side_effect = ["what time is it", "exit"]
    mock_match_tools.return_value = "The current time is 12:00 PM"

    # Run the function
    agent.run_agent()

    # Verify the function called the expected dependencies
    assert mock_input.call_count == 2
    mock_match_tools.assert_called_once_with("what time is it", [])


@patch("engine.agent.load_settings")
@patch("engine.agent.create_new_conversation")
@patch("engine.agent.load_conversation")
@patch("engine.agent.load_tools")
@patch("engine.agent.input")
@patch("engine.agent.switch_backend")
def test_run_agent_switch_backend(mock_switch_backend, mock_input, mock_load_tools,
                                 mock_load_conversation, mock_create_conversation,
                                 mock_load_settings):
    """Test that the run_agent function handles backend switching correctly."""
    # Setup mocks
    settings = {"llm_backend": "ollama", "llm_model": "llama3"}
    mock_load_settings.return_value = settings
    mock_create_conversation.return_value = "test-conversation-id"
    mock_load_conversation.return_value = {"history": [], "preferences": {}}
    mock_load_tools.return_value = []

    # Set up input to first provide a switch command, then exit
    mock_input.side_effect = ["switch openai", "exit"]
    mock_switch_backend.return_value = "openai"

    # Run the function
    agent.run_agent()

    # Verify the function called the expected dependencies
    assert mock_input.call_count == 2
    mock_switch_backend.assert_called_once_with("openai", settings)


@patch("engine.agent.load_settings")
@patch("engine.agent.create_new_conversation")
@patch("engine.agent.load_conversation")
@patch("engine.agent.load_tools")
@patch("engine.agent.input")
@patch("engine.agent.add_memory_fact")
def test_run_agent_remember_command(mock_add_memory, mock_input, mock_load_tools,
                                   mock_load_conversation, mock_create_conversation,
                                   mock_load_settings):
    """Test that the run_agent function handles !remember commands correctly."""
    # Setup mocks
    mock_load_settings.return_value = {"llm_backend": "ollama", "llm_model": "llama3"}
    mock_create_conversation.return_value = "test-conversation-id"
    mock_load_conversation.return_value = {"history": [], "preferences": {}}
    mock_load_tools.return_value = []

    # Set up input to first provide a remember command, then exit
    mock_input.side_effect = ["!remember I like pizza", "exit"]

    # Run the function
    agent.run_agent()

    # Verify the function called the expected dependencies
    assert mock_input.call_count == 2
    mock_add_memory.assert_called_once_with("I like pizza")


@patch("engine.agent.load_settings")
@patch("engine.agent.create_new_conversation")
@patch("engine.agent.load_conversation")
@patch("engine.agent.load_tools")
@patch("engine.agent.input")
@patch("engine.agent.recall_memory")
def test_run_agent_recall_command(mock_recall_memory, mock_input, mock_load_tools,
                                 mock_load_conversation, mock_create_conversation,
                                 mock_load_settings):
    """Test that the run_agent function handles !recall commands correctly."""
    # Setup mocks
    mock_load_settings.return_value = {"llm_backend": "ollama", "llm_model": "llama3"}
    mock_create_conversation.return_value = "test-conversation-id"
    mock_load_conversation.return_value = {"history": [], "preferences": {}}
    mock_load_tools.return_value = []

    # Set up input to first provide a recall command, then exit
    mock_input.side_effect = ["!recall", "exit"]
    mock_recall_memory.return_value = ["I like pizza", "I like ice cream"]

    # Run the function
    agent.run_agent()

    # Verify the function called the expected dependencies
    assert mock_input.call_count == 2
    mock_recall_memory.assert_called_once()


@patch("engine.agent.load_settings")
@patch("engine.agent.create_new_conversation")
@patch("engine.agent.load_conversation")
@patch("engine.agent.load_tools")
@patch("engine.agent.input")
@patch("engine.agent.forget_memory")
def test_run_agent_forget_command(mock_forget_memory, mock_input, mock_load_tools,
                                 mock_load_conversation, mock_create_conversation,
                                 mock_load_settings):
    """Test that the run_agent function handles !forget commands correctly."""
    # Setup mocks
    mock_load_settings.return_value = {"llm_backend": "ollama", "llm_model": "llama3"}
    mock_create_conversation.return_value = "test-conversation-id"
    mock_load_conversation.return_value = {"history": [], "preferences": {}}
    mock_load_tools.return_value = []

    # Set up input to first provide a forget command, then exit
    mock_input.side_effect = ["!forget pizza", "exit"]
    mock_forget_memory.return_value = 1

    # Run the function
    agent.run_agent()

    # Verify the function called the expected dependencies
    assert mock_input.call_count == 2
    mock_forget_memory.assert_called_once_with("pizza")


@patch("engine.agent.load_settings")
@patch("engine.agent.create_new_conversation")
@patch("engine.agent.load_conversation")
@patch("engine.agent.load_tools")
@patch("engine.agent.input")
@patch("engine.agent.list_conversation_meta")
def test_run_agent_load_command_invalid(mock_list_meta, mock_input, mock_load_tools,
                                       mock_load_conversation, mock_create_conversation,
                                       mock_load_settings):
    """Test that the run_agent function handles !load commands with invalid input."""
    # Setup mocks
    mock_load_settings.return_value = {"llm_backend": "ollama", "llm_model": "llama3"}
    mock_create_conversation.return_value = "test-conversation-id"
    mock_load_conversation.return_value = {"history": [], "preferences": {}}
    mock_load_tools.return_value = []

    # Set up input sequence
    mock_input.side_effect = ["!load", "invalid", "exit"]
    mock_list_meta.return_value = [
        {"id": "conv1", "title": "Conversation 1", "last_updated": "2025-05-28"}
    ]

    # Run the function
    agent.run_agent()

    # Verify the function called the expected dependencies
    assert mock_input.call_count == 3
    mock_list_meta.assert_called_once()
    # Load conversation should be called only once for the initial load
    assert mock_load_conversation.call_count == 1


@patch("engine.agent.load_settings")
@patch("engine.agent.create_new_conversation")
@patch("engine.agent.load_conversation")
@patch("engine.agent.load_tools")
@patch("engine.agent.input")
@patch("engine.agent.list_conversation_meta")
def test_run_agent_load_command_valid(mock_list_meta, mock_input, mock_load_tools,
                                     mock_load_conversation, mock_create_conversation,
                                     mock_load_settings):
    """Test that the run_agent function handles !load commands with valid input."""
    # Setup mocks
    mock_load_settings.return_value = {"llm_backend": "ollama", "llm_model": "llama3"}
    mock_create_conversation.return_value = "test-conversation-id"
    mock_load_conversation.return_value = {"history": [], "preferences": {}}
    mock_load_tools.return_value = []

    # Set up input sequence
    mock_input.side_effect = ["!load", "1", "exit"]
    mock_list_meta.return_value = [
        {"id": "conv1", "title": "Conversation 1", "last_updated": "2025-05-28"}
    ]

    # Run the function
    agent.run_agent()

    # Verify the function called the expected dependencies
    assert mock_input.call_count == 3
    mock_list_meta.assert_called_once()
    # Load conversation should be called twice - once for initial load and once for the loaded conversation
    assert mock_load_conversation.call_count == 2
    # Second call should load the selected conversation
    mock_load_conversation.assert_has_calls([
        call("test-conversation-id"),
        call("conv1")
    ])


@patch("engine.agent.load_settings")
@patch("engine.agent.create_new_conversation")
@patch("engine.agent.load_conversation")
@patch("engine.agent.load_tools")
@patch("engine.agent.input")
@patch("engine.agent.subprocess.run")
@patch("engine.agent.vectorstore_manager")
def test_run_agent_reindex_command(mock_vectorstore_manager, mock_subprocess, mock_input,
                                  mock_load_tools, mock_load_conversation,
                                  mock_create_conversation, mock_load_settings):
    """Test that the run_agent function handles !reindex commands correctly."""
    # Setup mocks
    mock_load_settings.return_value = {"llm_backend": "ollama", "llm_model": "llama3"}
    mock_create_conversation.return_value = "test-conversation-id"
    mock_profile = {"history": [], "preferences": {}, "project_path": "test/path"}
    mock_load_conversation.return_value = mock_profile
    mock_load_tools.return_value = []

    # Set up input to first provide a reindex command, then exit
    mock_input.side_effect = ["!reindex", "exit"]

    # Run the function
    agent.run_agent()

    # Verify the function called the expected dependencies
    assert mock_input.call_count == 2
    mock_subprocess.assert_called_once_with(["python", "ingest_project.py", "test/path"])
    assert mock_vectorstore_manager.vectorstore is None
    mock_vectorstore_manager.get_vectorstore.assert_called_with(mock_profile)


@patch("engine.agent.load_settings")
@patch("engine.agent.create_new_conversation")
@patch("engine.agent.load_conversation")
@patch("engine.agent.load_tools")
@patch("engine.agent.input")
def test_run_agent_mode_command(mock_input, mock_load_tools, mock_load_conversation,
                               mock_create_conversation, mock_load_settings):
    """Test that the run_agent function handles !mode commands correctly."""
    # Setup mocks
    mock_load_settings.return_value = {"llm_backend": "ollama", "llm_model": "llama3"}
    mock_create_conversation.return_value = "test-conversation-id"
    mock_profile = {"history": [], "preferences": {}}
    mock_load_conversation.return_value = mock_profile
    mock_load_tools.return_value = []

    # Set up input to first provide a mode command, then exit
    mock_input.side_effect = ["!mode creative", "exit"]

    # Run the function
    agent.run_agent()

    # Verify the function updated the profile correctly
    assert mock_input.call_count == 2
    assert mock_profile["mode"] == "creative"


@patch("engine.agent.load_settings")
@patch("engine.agent.create_new_conversation")
@patch("engine.agent.load_conversation")
@patch("engine.agent.load_tools")
@patch("engine.agent.input")
def test_run_agent_project_command(mock_input, mock_load_tools, mock_load_conversation,
                                  mock_create_conversation, mock_load_settings):
    """Test that the run_agent function handles !project commands correctly."""
    # Setup mocks
    mock_load_settings.return_value = {"llm_backend": "ollama", "llm_model": "llama3"}
    mock_create_conversation.return_value = "test-conversation-id"
    mock_profile = {"history": [], "preferences": {}}
    mock_load_conversation.return_value = mock_profile
    mock_load_tools.return_value = []

    # Set up input to first provide a project command, then exit
    mock_input.side_effect = ["!project /path/to/project", "exit"]

    # Run the function
    agent.run_agent()

    # Verify the function updated the profile correctly
    assert mock_input.call_count == 2
    assert mock_profile["project_path"] == "/path/to/project"
    assert mock_profile["mode"] == "development"


@patch("engine.agent.load_settings")
@patch("engine.agent.create_new_conversation")
@patch("engine.agent.load_conversation")
@patch("engine.agent.load_tools")
@patch("engine.agent.input")
@patch("engine.agent.transcribe_audio")
@patch("engine.agent.speak_text")
@patch("engine.agent.handle_input")
@patch("engine.agent.save_conversation")
def test_run_agent_voice_mode(mock_save_conversation, mock_handle_input, mock_speak_text,
                             mock_transcribe, mock_input, mock_load_tools,
                             mock_load_conversation, mock_create_conversation,
                             mock_load_settings):
    """Test that the run_agent function handles voice mode correctly."""
    # Setup mocks
    mock_load_settings.return_value = {
        "llm_backend": "ollama",
        "llm_model": "llama3",
        "voice": True,
        "streaming": False
    }
    mock_create_conversation.return_value = "test-conversation-id"
    mock_profile = {"history": [], "preferences": {}}
    mock_load_conversation.return_value = mock_profile
    mock_load_tools.return_value = []

    # Set up transcribe to first provide a normal query, then exit
    mock_transcribe.side_effect = ["hello", "exit"]
    mock_handle_input.return_value = "Hello, I'm Suhana. How can I help you?"

    # Run the function
    agent.run_agent()

    # Verify the function called the expected dependencies
    assert mock_transcribe.call_count == 2
    mock_handle_input.assert_called_once_with("hello", "ollama", mock_profile, mock_load_settings.return_value)
    mock_speak_text.assert_called_once_with("Hello, I'm Suhana. How can I help you?")
    mock_save_conversation.assert_called_once_with("test-conversation-id", mock_profile)


@patch("engine.agent.load_settings")
@patch("engine.agent.create_new_conversation")
@patch("engine.agent.load_conversation")
@patch("engine.agent.load_tools")
@patch("engine.agent.input")
@patch("engine.agent.handle_input")
def test_run_agent_streaming_mode(mock_handle_input, mock_input, mock_load_tools,
                                 mock_load_conversation, mock_create_conversation,
                                 mock_load_settings):
    """Test that the run_agent function handles streaming mode correctly."""
    # Setup mocks
    mock_load_settings.return_value = {
        "llm_backend": "ollama",
        "llm_model": "llama3",
        "voice": False,
        "streaming": True
    }
    mock_create_conversation.return_value = "test-conversation-id"
    mock_profile = {"history": [], "preferences": {}}
    mock_load_conversation.return_value = mock_profile
    mock_load_tools.return_value = []

    # Set up input to first provide a normal query, then exit
    mock_input.side_effect = ["hello", "exit"]
    # For streaming, return an iterator of tokens
    mock_handle_input.return_value = iter(["Hello", ", ", "I'm ", "Suhana", "."])

    # Run the function
    agent.run_agent()

    # Verify the function called the expected dependencies
    assert mock_input.call_count == 2
    mock_handle_input.assert_called_once_with("hello", "ollama", mock_profile, mock_load_settings.return_value)


@patch("engine.agent.load_settings")
@patch("engine.agent.create_new_conversation")
@patch("engine.agent.load_conversation")
@patch("engine.agent.load_tools")
@patch("engine.agent.input")
def test_run_agent_keyboard_interrupt(mock_input, mock_load_tools, mock_load_conversation,
                                     mock_create_conversation, mock_load_settings):
    """Test that the run_agent function handles KeyboardInterrupt correctly."""
    # Setup mocks
    mock_load_settings.return_value = {"llm_backend": "ollama", "llm_model": "llama3"}
    mock_create_conversation.return_value = "test-conversation-id"
    mock_load_conversation.return_value = {"history": [], "preferences": {}}
    mock_load_tools.return_value = []

    # Set up input to raise KeyboardInterrupt
    mock_input.side_effect = KeyboardInterrupt()

    # Run the function - should exit gracefully
    agent.run_agent()

    # Verify the function called the expected dependencies
    mock_input.assert_called_once()
