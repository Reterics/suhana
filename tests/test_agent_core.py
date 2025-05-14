import pytest
from unittest.mock import patch

from engine import agent_core


class FakeMemory:
    def __init__(self, content): self.page_content = content


@pytest.mark.parametrize("input_text, mems, expected", [
    ("explain this", [], True),  # keyword match
    ("random question", [FakeMemory("short fact")] * 3, True),  # short memory facts
    ("random question", [], True),  # no memory
    ("random question", [FakeMemory("this memory content is intentionally made longer than ten words to bypass short fact heuristic")]*5, False),  # valid long mem
])
def test_should_include_documents(input_text, mems, expected):
    assert agent_core.should_include_documents(input_text, mems) == expected


@patch("engine.agent_core.vectorstore")
@patch("engine.agent_core.query_ollama", return_value="Mocked Ollama reply")
@patch("engine.agent_core.search_memory", return_value=[FakeMemory("test memory fact")])
@patch("engine.agent_core.summarize_profile_for_prompt", return_value="Profile summary")
def test_handle_input_ollama(mock_summary, mock_search, mock_ollama, mock_vectorstore):
    mock_vectorstore.similarity_search_with_score.return_value = [(FakeMemory("doc content"), 0.2)]
    profile = {"history": [], "preferences": {}, "name": "Test"}
    settings = {"llm_backend": "ollama", "llm_model": "fake-model"}

    result = agent_core.handle_input("test question", "ollama", profile, settings)

    assert result == "Mocked Ollama reply"
    assert mock_ollama.called
    assert "test question" in mock_ollama.call_args[0]
    assert "Profile summary" in mock_ollama.call_args[0][1]


@patch("engine.agent_core.vectorstore")
@patch("engine.agent_core.query_openai", return_value="Mocked OpenAI reply")
@patch("engine.agent_core.search_memory", return_value=[])
@patch("engine.agent_core.summarize_profile_for_prompt", return_value="Profile summary")
def test_handle_input_openai(mock_summary, mock_search, mock_openai, mock_vectorstore):
    mock_vectorstore.similarity_search_with_score.return_value = []
    profile = {"history": [], "preferences": {}, "name": "Test"}
    settings = {"llm_backend": "openai", "openai_model": "gpt-test"}

    result = agent_core.handle_input("what is this?", "openai", profile, settings)

    assert result == "Mocked OpenAI reply"
    assert mock_openai.called
    assert "what is this?" in mock_openai.call_args[0]
