import sys
import types
import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture(autouse=True)
def mock_dependencies():
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
    sys.modules['sounddevice'] = MagicMock()
    sys.modules['whisper'] = MagicMock()
    sys.modules['TTS'] = MagicMock()
    sys.modules['TTS.api'] = MagicMock()
    sys.modules['soundfile'] = MagicMock()
    #sys.modules['numpy'] = MagicMock()
    yield

def test_query_openai_no_api_key(monkeypatch):
    import engine.backends.openai as openai_backend

    profile = {"history": []}
    settings = {"openai_model": "gpt-3.5-turbo"}
    prompt = "Test prompt"
    system_prompt = "You are an assistant."

    reply = openai_backend.query_openai(prompt, system_prompt, profile, settings, False)
    assert "[❌ OpenAI API key not set" in reply

def test_query_openai_basic(monkeypatch):
    import engine.backends.openai as openai_backend

    # Mock trim_message_history to just pass through
    monkeypatch.setattr(openai_backend, "trim_message_history", lambda msgs, model: msgs)

    # Mock summarize_history to return a simple string
    monkeypatch.setattr(openai_backend, "summarize_history", lambda messages, client, model: "Summary text.")

    # Mock OpenAI client and its chat completion
    fake_message = MagicMock()
    fake_message.content = "Hello, world!"
    fake_choice = MagicMock()
    fake_choice.message = fake_message
    fake_response = MagicMock()
    fake_response.choices = [fake_choice]
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_response

    # Patch OpenAI constructor to return our fake client
    with patch("engine.backends.openai.OpenAI", return_value=fake_client):
        profile = {"history": [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"}]}
        settings = {"openai_api_key": "sk-abc", "openai_model": "gpt-3.5-turbo"}
        prompt = "Test prompt"
        system_prompt = "You are an assistant."

        reply = openai_backend.query_openai(prompt, system_prompt, profile, settings, False)

        assert reply == "Hello, world!"
        # Check history is updated
        assert profile["history"][-2]["role"] == "user"
        assert profile["history"][-2]["content"] == prompt
        assert profile["history"][-1]["role"] == "assistant"
        assert profile["history"][-1]["content"] == "Hello, world!"

def test_query_openai_stream(monkeypatch):
    import engine.backends.openai as openai_backend

    monkeypatch.setattr(openai_backend, "trim_message_history", lambda msgs, model: msgs)
    monkeypatch.setattr(openai_backend, "summarize_history", lambda messages, client, model: "Summary text.")

    # Prepare a streaming response generator
    class FakeChunk:
        def __init__(self, content): self.choices = [MagicMock(delta=MagicMock(content=content))]
    def fake_response_gen():
        yield FakeChunk("Hello, ")
        yield FakeChunk("world!")

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_response_gen()

    with patch("engine.backends.openai.OpenAI", return_value=fake_client):
        profile = {"history": [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"}]}
        settings = {"openai_api_key": "sk-abc", "openai_model": "gpt-3.5-turbo", "streaming": True}
        prompt = "Test stream"
        system_prompt = "You are an assistant."

        gen = openai_backend.query_openai(prompt, system_prompt, profile, settings, True)
        tokens = list(gen)
        assert tokens == ["Hello, ", "world!"]
        # After streaming, history should be updated
        assert profile["history"][-2]["role"] == "user"
        assert profile["history"][-1]["role"] == "assistant"
        assert "Hello, world!" in profile["history"][-1]["content"]
