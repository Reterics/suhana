import sys
import types
import pytest
from unittest.mock import MagicMock

@pytest.fixture(autouse=True)
def fake_anthropic_module(monkeypatch):
    # Inject a fake anthropic module so the backend can import it
    fake_anthropic = types.ModuleType("anthropic")
    sys.modules["anthropic"] = fake_anthropic
    # Fake the Anthropic class in the module
    fake_anthropic.Anthropic = MagicMock()
    yield

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
    yield

@pytest.fixture
def settings():
    return {
        "claude_api_key": "test-key",
        "claude_model": "claude-3-opus-20240229"
    }

@pytest.fixture
def profile():
    return {"history": [
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "What's the weather?"},
    ]}

def test_summarize_history_claude(monkeypatch, settings):
    import engine.backends.claude as claude_backend

    # Fake response object as returned by the SDK
    fake_content_block = MagicMock()
    fake_content_block.text = "Summary response"
    fake_response = MagicMock()
    fake_response.content = [fake_content_block]
    # Patch the Anthropic client
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    summary = claude_backend.summarize_history_claude(
        [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ],
        fake_client,
        settings["claude_model"],
    )
    assert summary == "Summary response"
    fake_client.messages.create.assert_called_once()

def test_query_claude_no_api_key(monkeypatch, profile):
    import engine.backends.claude as claude_backend
    settings = {"claude_model": "claude-3-opus-20240229"}
    reply = claude_backend.query_claude("prompt", "sys", profile, settings, force_stream=False)
    assert "not set" in reply

def test_query_claude_basic(monkeypatch, settings, profile):
    import engine.backends.claude as claude_backend

    # Patch trim_message_history and summarize_history_claude
    monkeypatch.setattr(claude_backend, "trim_message_history", lambda msgs, model: msgs)
    monkeypatch.setattr(claude_backend, "summarize_history_claude", lambda messages, client, model: "Earlier summary.")

    # Patch Anthropic SDK
    fake_client = MagicMock()
    fake_content_block = MagicMock()
    fake_content_block.text = "Hello, Claude!"
    fake_response = MagicMock()
    fake_response.content = [fake_content_block]
    fake_client.messages.create.return_value = fake_response

    monkeypatch.setattr(claude_backend, "Anthropic", MagicMock(return_value=fake_client))

    reply = claude_backend.query_claude("What's up?", "You are an assistant.", profile, settings, force_stream=False)

    assert reply == "Hello, Claude!"
    assert profile["history"][-2]["role"] == "user"
    assert profile["history"][-1]["role"] == "assistant"
    assert profile["history"][-1]["content"] == "Hello, Claude!"

def test_query_claude_post_exception(monkeypatch, settings, profile):
    import engine.backends.claude as claude_backend

    monkeypatch.setattr(claude_backend, "trim_message_history", lambda msgs, model: msgs)
    monkeypatch.setattr(claude_backend, "summarize_history_claude", lambda messages, client, model: "Summary.")

    fake_client = MagicMock()
    fake_client.messages.create.side_effect = Exception("Failure")
    monkeypatch.setattr(claude_backend, "Anthropic", MagicMock(return_value=fake_client))

    reply = claude_backend.query_claude("Error test?", "Sys", profile, settings, force_stream=False)
    assert "[Claude connection error]" in reply

def test_query_claude_stream(monkeypatch, settings, profile):
    import engine.backends.claude as claude_backend

    monkeypatch.setattr(claude_backend, "trim_message_history", lambda msgs, model: msgs)
    monkeypatch.setattr(claude_backend, "summarize_history_claude", lambda messages, client, model: "Earlier summary.")

    # Prepare streaming response
    fake_event = MagicMock()
    fake_content = MagicMock()
    fake_content.text = "Hello, "
    fake_event.content_block_delta = fake_content
    fake_event2 = MagicMock()
    fake_content2 = MagicMock()
    fake_content2.text = "world!"
    fake_event2.content_block_delta = fake_content2

    fake_client = MagicMock()
    fake_client.messages.create.return_value = iter([fake_event, fake_event2])
    monkeypatch.setattr(claude_backend, "Anthropic", MagicMock(return_value=fake_client))

    gen = claude_backend.query_claude("Say hi.", "Sys", profile, settings, force_stream=True)
    tokens = list(gen)
    assert "Hello, " in tokens[0]
    assert "world!" in tokens[1]
    assert profile["history"][-2]["role"] == "user"
    assert profile["history"][-1]["role"] == "assistant"
    assert "Hello, world!" in profile["history"][-1]["content"]

def test_query_claude_stream_exception(monkeypatch, settings, profile):
    import engine.backends.claude as claude_backend

    monkeypatch.setattr(claude_backend, "trim_message_history", lambda msgs, model: msgs)
    monkeypatch.setattr(claude_backend, "summarize_history_claude", lambda messages, client, model: "Summary.")

    fake_client = MagicMock()
    fake_client.messages.create.side_effect = Exception("Stream failure")
    monkeypatch.setattr(claude_backend, "Anthropic", MagicMock(return_value=fake_client))

    gen = claude_backend.query_claude("oops", "Sys", profile, settings, force_stream=True)
    token = next(gen)
    assert "[Claude connection error]" in token
