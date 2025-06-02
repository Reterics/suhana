import sys
import types
import pytest
from unittest.mock import MagicMock

@pytest.fixture(autouse=True)
def fake_genai_module(monkeypatch):
    # Before import, inject fake genai module into sys.modules
    fake_genai = types.ModuleType("google.generativeai")
    fake_GenerativeModel = MagicMock()
    fake_genai.GenerativeModel = fake_GenerativeModel
    sys.modules["google.generativeai"] = fake_genai
    yield


@pytest.fixture(autouse=True)
def mock_dependencies():
    # Mock any unrelated dependencies for full isolation, like in your other tests
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
        "gemini_api_key": "fake-key",
        "gemini_model": "gemini-test"
    }

@pytest.fixture
def profile():
    return {"history": [
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "What's the weather?"},
    ]}

def test_summarize_history_gemini_success(monkeypatch, settings):
    import engine.backends.gemini as gemini_backend

    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Summary generated."
    mock_model.generate_content.return_value = mock_response

    # Patch SDK entry points
    monkeypatch.setattr(gemini_backend, "genai", MagicMock())
    gemini_backend.genai.GenerativeModel.return_value = mock_model

    summary = gemini_backend.summarize_history_gemini(
        [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ],
        settings["gemini_api_key"],
        settings["gemini_model"],
    )
    assert summary == "Summary generated."
    gemini_backend.genai.GenerativeModel.assert_called_with(settings["gemini_model"])
    mock_model.generate_content.assert_called_once()

def test_query_gemini_no_stream_success(monkeypatch, settings, profile):
    import engine.backends.gemini as gemini_backend

    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Gemini reply!"
    mock_model.generate_content.return_value = mock_response

    monkeypatch.setattr(gemini_backend, "genai", MagicMock())
    gemini_backend.genai.GenerativeModel.return_value = mock_model
    monkeypatch.setattr(gemini_backend, "trim_message_history", lambda msgs, model: msgs)

    reply = gemini_backend.query_gemini("Tell me a joke.", "You are funny.", profile, settings, force_stream=False)
    assert reply == "Gemini reply!"
    assert profile["history"][-1]["role"] == "assistant"
    gemini_backend.genai.GenerativeModel.assert_called_with(settings["gemini_model"])
    mock_model.generate_content.assert_called_once()

def test_query_gemini_no_api_key(monkeypatch, profile):
    import engine.backends.gemini as gemini_backend

    monkeypatch.setattr(gemini_backend, "genai", MagicMock())
    monkeypatch.setattr(gemini_backend, "trim_message_history", lambda msgs, model: msgs)

    settings = {"gemini_model": "model"}
    result = gemini_backend.query_gemini("prompt", "sys", profile, settings, force_stream=False)
    assert "not set" in result
    gemini_backend.genai.GenerativeModel.assert_not_called()

def test_query_gemini_post_exception(monkeypatch, settings, profile):
    import engine.backends.gemini as gemini_backend

    mock_model = MagicMock()
    mock_model.generate_content.side_effect = Exception("Failure")

    monkeypatch.setattr(gemini_backend, "genai", MagicMock())
    gemini_backend.genai.GenerativeModel.return_value = mock_model
    monkeypatch.setattr(gemini_backend, "trim_message_history", lambda msgs, model: msgs)

    reply = gemini_backend.query_gemini("Error test?", "Sys", profile, settings, force_stream=False)
    assert "[Gemini connection error]" in reply

def test_query_gemini_stream_mode(monkeypatch, settings, profile):
    import engine.backends.gemini as gemini_backend

    mock_model = MagicMock()
    chunk1 = MagicMock()
    chunk1.text = "streamed!"
    mock_model.generate_content.return_value = iter([chunk1])

    monkeypatch.setattr(gemini_backend, "genai", MagicMock())
    gemini_backend.genai.GenerativeModel.return_value = mock_model
    monkeypatch.setattr(gemini_backend, "trim_message_history", lambda msgs, model: msgs)

    gen = gemini_backend.query_gemini("Say hi.", "Sys", profile, settings, force_stream=True)
    token = next(gen)
    assert "streamed!" in token

def test_query_gemini_stream_exception(monkeypatch, settings, profile):
    import engine.backends.gemini as gemini_backend

    mock_model = MagicMock()
    mock_model.generate_content.side_effect = Exception("err")

    monkeypatch.setattr(gemini_backend, "genai", MagicMock())
    gemini_backend.genai.GenerativeModel.return_value = mock_model
    monkeypatch.setattr(gemini_backend, "trim_message_history", lambda msgs, model: msgs)

    gen = gemini_backend.query_gemini("oops", "Sys", profile, settings, force_stream=True)
    token = next(gen)
    assert "[Gemini connection error]" in token
