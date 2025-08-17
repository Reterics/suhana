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

    # Voice-related (not needed for ollama, but harmless)
    sys.modules['sounddevice'] = MagicMock()
    sys.modules['whisper'] = MagicMock()
    sys.modules['TTS'] = MagicMock()
    sys.modules['TTS.api'] = MagicMock()
    sys.modules['soundfile'] = MagicMock()

    # Ollama dependencies
    #sys.modules['requests'] = MagicMock()
    #sys.modules['numpy'] = MagicMock()
    yield

def test_query_ollama_offline(monkeypatch):
    import engine.backends.ollama as ollama

    # Patch trim_message_history to return trimmed list
    monkeypatch.setattr(ollama, "trim_message_history", lambda msgs, model=None, current_prompt=None: msgs)

    # Patch summarize_history_offline to avoid requests
    monkeypatch.setattr(ollama, "summarize_history_offline", lambda messages, model: "Earlier summary.")

    # Patch requests.post to fake API response
    fake_resp = MagicMock()
    fake_resp.json.return_value = {"response": "Hello, test user!"}
    monkeypatch.setattr(ollama.requests, "post", MagicMock(return_value=fake_resp))
    with patch("requests.post", return_value=fake_resp) as mock_post:
        profile = {
            "history": [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello!"},
            ]
        }
        prompt = "What's up?"
        system_prompt = "You are a helpful assistant."
        settings = {"llm_model": "llama3"}
        force_stream = False

        reply = ollama.query_ollama(prompt, system_prompt, profile, settings, force_stream)

        # Check the reply is as expected
        assert reply == "Hello, test user!"

        # Check history is updated correctly
        assert profile["history"][-2]["role"] == "user"
        assert profile["history"][-2]["content"] == prompt
        assert profile["history"][-1]["role"] == "assistant"
        assert profile["history"][-1]["content"] == reply

def test_query_ollama_stream(monkeypatch):
    import engine.backends.ollama as ollama

    # Patch trim_message_history
    monkeypatch.setattr(ollama, "trim_message_history", lambda msgs, model=None, current_prompt=None: msgs)

    # Patch summarize_history_offline
    monkeypatch.setattr(ollama, "summarize_history_offline", lambda messages, model: "Earlier summary.")

    # Fake requests.post as a streaming generator
    class FakeResp:
        def __enter__(self): return self
        def __exit__(self, exc_type, exc_val, exc_tb): return False
        def raise_for_status(self): return None
        def iter_lines(self):
            # Simulate two lines of streamed JSON
            yield b'{"response": "Hello, "}'
            yield b'{"response": "world!"}'
    monkeypatch.setattr(ollama.requests, "post", MagicMock(return_value=FakeResp()))

    profile = {
        "history": [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
    }
    prompt = "Say hi."
    system_prompt = "You are a helpful assistant."
    settings = {"llm_model": "llama3", "streaming": True}
    force_stream = True

    gen = ollama.query_ollama(prompt, system_prompt, profile, settings, force_stream)
    tokens = list(gen)
    assert "Hello, " in tokens[0]
    assert "world!" in tokens[1]
    # After generator runs, profile's history should contain the conversation and stream
    assert profile["history"][-2]["role"] == "user"
    assert profile["history"][-1]["role"] == "assistant"
    assert "Hello, world!" in profile["history"][-1]["content"]

