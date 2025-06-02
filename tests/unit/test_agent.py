import sys
import types

import pytest
from unittest.mock import patch, MagicMock, mock_open

# Mock the external dependencies
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

    # Mock voice module dependencies
    sys.modules['sounddevice'] = MagicMock()
    sys.modules['whisper'] = MagicMock()
    sys.modules['TTS'] = MagicMock()
    sys.modules['TTS.api'] = MagicMock()
    sys.modules['soundfile'] = MagicMock()

    # AI Libraries
    sys.modules['google.generativeai'] = MagicMock()
    sys.modules['anthropic'] = MagicMock()
    yield



class TestRunAgent:
    """Tests for the run_agent function"""

    @patch("engine.agent.load_settings")
    @patch("engine.agent.create_new_conversation")
    @patch("engine.agent.load_conversation")
    @patch("engine.agent.load_tools")
    @patch("engine.agent.input", return_value="exit")
    def test_run_agent_exit_command(self, mock_input, mock_load_tools, mock_load_conversation,
                                   mock_create_conversation, mock_load_settings):
        """Test that the run_agent function exits correctly when 'exit' is entered."""
        from engine import agent
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
    def test_run_agent_normal_input(self, mock_handle_input, mock_input, mock_save_conversation,
                                   mock_load_tools, mock_load_conversation,
                                   mock_create_conversation, mock_load_settings):
        """Test that the run_agent function processes normal input correctly."""
        from engine import agent
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
    def test_run_agent_tool_match(self, mock_match_tools, mock_input, mock_load_tools,
                                 mock_load_conversation, mock_create_conversation,
                                 mock_load_settings):
        """Test that the run_agent function handles tool matches correctly."""
        from engine import agent
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
    def test_run_agent_switch_backend(self, mock_switch_backend, mock_input, mock_load_tools,
                                     mock_load_conversation, mock_create_conversation,
                                     mock_load_settings):
        """Test that the run_agent function handles backend switching correctly."""
        from engine import agent
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
    @patch("engine.agent.container.get_typed")
    def test_run_agent_mode_command(self, mock_get_typed, mock_input, mock_load_tools,
                                   mock_load_conversation, mock_create_conversation,
                                   mock_load_settings):
        """Test that the run_agent function handles !mode commands correctly."""
        from engine import agent
        # Setup mocks
        mock_load_settings.return_value = {"llm_backend": "ollama", "llm_model": "llama3"}
        mock_create_conversation.return_value = "test-conversation-id"
        mock_profile = {"history": [], "preferences": {}}
        mock_load_conversation.return_value = mock_profile
        mock_load_tools.return_value = []

        # Mock vectorstore manager
        mock_vectorstore_manager = MagicMock()
        mock_vectorstore_manager.current_vector_mode = None
        mock_get_typed.return_value = mock_vectorstore_manager

        # Set up input to first provide a mode command, then exit
        mock_input.side_effect = ["!mode creative", "exit"]

        # Run the function
        agent.run_agent()

        # Verify the function updated the profile correctly
        assert mock_input.call_count == 2
        assert mock_profile["mode"] == "creative"
        mock_vectorstore_manager.get_vectorstore.assert_called_once_with(mock_profile)

    @patch("engine.agent.load_settings")
    @patch("engine.agent.create_new_conversation")
    @patch("engine.agent.load_conversation")
    @patch("engine.agent.load_tools")
    @patch("engine.agent.input")
    @patch("engine.agent.container.get_typed")
    def test_run_agent_project_command(self, mock_get_typed, mock_input, mock_load_tools,
                                      mock_load_conversation, mock_create_conversation,
                                      mock_load_settings):
        """Test that the run_agent function handles !project commands correctly."""
        from engine import agent
        # Setup mocks
        mock_load_settings.return_value = {"llm_backend": "ollama", "llm_model": "llama3"}
        mock_create_conversation.return_value = "test-conversation-id"
        mock_profile = {"history": [], "preferences": {}}
        mock_load_conversation.return_value = mock_profile
        mock_load_tools.return_value = []

        # Mock vectorstore manager
        mock_vectorstore_manager = MagicMock()
        mock_get_typed.return_value = mock_vectorstore_manager

        # Set up input to first provide a project command, then exit
        mock_input.side_effect = ["!project c:\\path\\to\\project", "exit"]

        # Run the function
        agent.run_agent()

        # Verify the function updated the profile correctly
        assert mock_input.call_count == 2
        assert mock_profile["project_path"] == "c:\\path\\to\\project"
        assert mock_profile["mode"] == "development"
        mock_vectorstore_manager.get_vectorstore.assert_called_once_with(mock_profile)

    @patch("engine.agent.load_settings")
    @patch("engine.agent.create_new_conversation")
    @patch("engine.agent.load_conversation")
    @patch("engine.agent.load_tools")
    @patch("engine.agent.input")
    @patch("engine.agent.subprocess.run")
    @patch("engine.agent.container.get_typed")
    def test_run_agent_reindex_command(self, mock_get_typed, mock_subprocess, mock_input,
                                      mock_load_tools, mock_load_conversation,
                                      mock_create_conversation, mock_load_settings):
        """Test that the run_agent function handles !reindex commands correctly."""
        from engine import agent
        # Setup mocks
        mock_load_settings.return_value = {"llm_backend": "ollama", "llm_model": "llama3"}
        mock_create_conversation.return_value = "test-conversation-id"
        mock_profile = {"history": [], "preferences": {}, "project_path": "C:\\test\\path"}
        mock_load_conversation.return_value = mock_profile
        mock_load_tools.return_value = []

        # Create a mock for the vectorstore_manager
        mock_vectorstore_manager = MagicMock()
        mock_vectorstore_manager.reset_vectorstore = MagicMock()
        mock_vectorstore_manager.get_vectorstore = MagicMock()
        mock_get_typed.return_value = mock_vectorstore_manager

        # Set up input to first provide a reindex command, then exit
        mock_input.side_effect = ["!reindex", "exit"]

        # Run the function
        agent.run_agent()

        # Verify the function called the expected dependencies
        assert mock_input.call_count == 2
        mock_subprocess.assert_called_once_with(["python", "ingest_project.py", "C:\\test\\path"])
        mock_vectorstore_manager.reset_vectorstore.assert_called_once()
        mock_vectorstore_manager.get_vectorstore.assert_called_with(mock_profile)

    @patch("engine.agent.load_settings")
    @patch("engine.agent.create_new_conversation")
    @patch("engine.agent.load_conversation")
    @patch("engine.agent.load_tools")
    @patch("engine.agent.input")
    @patch("engine.agent.add_memory_fact")
    def test_run_agent_remember_command(self, mock_add_memory, mock_input, mock_load_tools,
                                       mock_load_conversation, mock_create_conversation,
                                       mock_load_settings):
        """Test that the run_agent function handles !remember commands correctly."""
        from engine import agent
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
    def test_run_agent_recall_command(self, mock_recall_memory, mock_input, mock_load_tools,
                                     mock_load_conversation, mock_create_conversation,
                                     mock_load_settings):
        """Test that the run_agent function handles !recall commands correctly."""
        from engine import agent
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
    def test_run_agent_forget_command(self, mock_forget_memory, mock_input, mock_load_tools,
                                     mock_load_conversation, mock_create_conversation,
                                     mock_load_settings):
        """Test that the run_agent function handles !forget commands correctly."""
        from engine import agent
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
