import sys
import types

import numpy as np
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
    #sys.modules['numpy'] = MagicMock()

    # Mock voice module dependencies
    sys.modules['sounddevice'] = MagicMock()
    sys.modules['whisper'] = MagicMock()
    sys.modules['TTS'] = MagicMock()
    sys.modules['TTS.api'] = MagicMock()
    sys.modules['soundfile'] = MagicMock()
    sys.modules['scipy'] = MagicMock()
    sys.modules['scipy.io'] = MagicMock()
    sys.modules['scipy.io.wavfile'] = MagicMock()
    yield

# ---- UNIT TEST FOR speak_text ----

def test_speak_text_runs_and_cleans_up(tmp_path, monkeypatch):
    import builtins
    import engine.voice as voice

    # Mock TTS object with .tts returning a numpy array
    fake_tts_instance = MagicMock()
    fake_wav = [0.0, 0.1, -0.1]  # Simulate a simple waveform
    fake_tts_instance.tts.return_value = fake_wav

    # Patch TTS constructor to return our fake instance
    monkeypatch.setattr(voice, "TTS", MagicMock(return_value=fake_tts_instance))

    # Patch sf.write to avoid file IO
    fake_sf = MagicMock()
    monkeypatch.setattr(voice, "sf", fake_sf)

    # Patch subprocess.run to simulate ffplay
    monkeypatch.setattr(voice.subprocess, "run", MagicMock())

    # Patch uuid to create a fixed filename (avoid randomness)
    monkeypatch.setattr(voice.uuid, "uuid4", MagicMock(return_value=MagicMock(hex="testhex")))

    # Patch os.remove to track file deletion
    deleted_files = []
    monkeypatch.setattr(voice.os, "remove", lambda f: deleted_files.append(f))

    # Patch os.path.abspath to return a dummy path
    monkeypatch.setattr(voice.os.path, "abspath", lambda f: "/tmp/" + f)

    # Call the function
    voice.speak_text("Hello World!")

    # Check: TTS.tss was called
    assert fake_tts_instance.tts.called
    # Check: file was "written"
    fake_sf.write.assert_called_once()
    # Check: subprocess.run was called to "play" the file
    voice.subprocess.run.assert_called_once()
    # Check: file was "removed"
    assert deleted_files, "The temporary speech file should be cleaned up."

def test_get_whisper_model(monkeypatch):
    import engine.voice as voice

    mock_model = MagicMock()
    monkeypatch.setattr(voice.whisper, "load_model", MagicMock(return_value=mock_model))
    # Reset model cache
    voice._model = None
    model = voice.get_whisper_model()
    assert model is mock_model
    # Subsequent call uses cache, not loader
    assert voice.get_whisper_model() is mock_model

def test_record_audio(monkeypatch):
    import engine.voice as voice

    mock_rec = np.array([[1, 2], [3, 4]])
    monkeypatch.setattr(voice.sd, "rec", MagicMock(return_value=mock_rec))
    monkeypatch.setattr(voice.sd, "wait", MagicMock())
    monkeypatch.setattr(voice.np, "squeeze", lambda arr: arr)
    res = voice.record_audio(1, 16000)
    assert (res == mock_rec).all()

def test_estimate_noise_floor(monkeypatch):
    import engine.voice as voice

    fake_audio = np.array([[10, 20], [30, 40]])
    monkeypatch.setattr(voice.sd, "rec", MagicMock(return_value=fake_audio))
    monkeypatch.setattr(voice.sd, "wait", MagicMock())
    monkeypatch.setattr(voice.np, "abs", np.abs)
    monkeypatch.setattr(voice.np, "mean", np.mean)
    result = voice.estimate_noise_floor()
    assert isinstance(result, (float, np.floating))

def test_record_audio_until_silence_no_speech(monkeypatch):
    import engine.voice as voice

    # Mock estimate_noise_floor to set a threshold
    monkeypatch.setattr(voice, "estimate_noise_floor", lambda *a, **k: 10)
    # Mock sd.InputStream to return None, triggers the fallback branch
    monkeypatch.setattr(voice.sd, "InputStream", MagicMock(return_value=None))
    monkeypatch.setattr(voice.np, "zeros", lambda shape, dtype: np.array([0], dtype=np.int16))
    audio = voice.record_audio_until_silence()
    assert (audio == np.array([0], dtype=np.int16)).all()

def test_save_temp_wav(monkeypatch):
    import engine.voice as voice

    class DummyFile:
        name = "/tmp/test.wav"
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(voice.tempfile, "NamedTemporaryFile", MagicMock(return_value=DummyFile()))
    fake_write = MagicMock()
    # Patch the write function in your sys.modules mock!
    sys.modules['scipy.io.wavfile'].write = fake_write

    audio = np.array([1, 2, 3])
    samplerate = 12345
    res = voice.save_temp_wav(audio, samplerate)

    assert res == "/tmp/test.wav"
    fake_write.assert_called_once_with("/tmp/test.wav", samplerate, audio)

def test_transcribe_audio(monkeypatch):
    import engine.voice as voice

    monkeypatch.setattr(voice, "record_audio_until_silence", lambda *a, **k: np.array([1, 2, 3]))
    monkeypatch.setattr(voice, "save_temp_wav", lambda *a, **k: "/tmp/audio.wav")
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"text": "Test transcript"}
    monkeypatch.setattr(voice, "get_whisper_model", lambda: mock_model)
    monkeypatch.setattr(voice.os, "remove", lambda path: None)
    text = voice.transcribe_audio()
    assert text == "Test transcript"
    mock_model.transcribe.assert_called_with("/tmp/audio.wav")

def test_speak_text_multiarray_fallback(monkeypatch):
    import engine.voice as voice

    fake_tts_instance = MagicMock()
    # First call to .tts raises an AttributeError with "multiarray" in the message
    calls = [AttributeError("multiarray"), [0.0, 0.1, -0.1]]
    def tts_side_effect(text):
        v = calls.pop(0)
        if isinstance(v, Exception):
            raise v
        return v
    fake_tts_instance.tts.side_effect = tts_side_effect
    monkeypatch.setattr(voice, "TTS", MagicMock(return_value=fake_tts_instance))
    monkeypatch.setattr(voice, "sf", MagicMock())
    monkeypatch.setattr(voice.subprocess, "run", MagicMock())
    monkeypatch.setattr(voice.uuid, "uuid4", MagicMock(return_value=MagicMock(hex="testhex")))
    monkeypatch.setattr(voice.os, "remove", MagicMock())
    monkeypatch.setattr(voice.os.path, "abspath", lambda f: "/tmp/" + f)
    # np._core.multiarray must exist, ensure it's there for patching
    import numpy as np
    if not hasattr(np._core, 'multiarray'):
        np._core.multiarray = MagicMock()
    voice._tts = None
    voice.speak_text("Hello Fallback!")
    assert fake_tts_instance.tts.call_count == 2

def test_speak_text_generator_and_flatten(monkeypatch):
    import engine.voice as voice

    # Generator returns one nested array
    def fake_generator():
        yield [1, 2, 3]
    fake_tts_instance = MagicMock()
    fake_tts_instance.tts.return_value = fake_generator()
    monkeypatch.setattr(voice, "TTS", MagicMock(return_value=fake_tts_instance))
    monkeypatch.setattr(voice, "sf", MagicMock())
    monkeypatch.setattr(voice.subprocess, "run", MagicMock())
    monkeypatch.setattr(voice.uuid, "uuid4", MagicMock(return_value=MagicMock(hex="testhex")))
    monkeypatch.setattr(voice.os, "remove", MagicMock())
    monkeypatch.setattr(voice.os.path, "abspath", lambda f: "/tmp/" + f)
    import numpy as np
    voice._tts = None
    voice.speak_text("Hello Generator!")
    # It should run to completion with all conversions and flattening
    assert fake_tts_instance.tts.called


def test_transcribe_audio_file_not_found(monkeypatch):
    import engine.voice as voice

    monkeypatch.setattr(voice, "record_audio_until_silence", lambda *a, **k: np.array([1, 2, 3]))
    monkeypatch.setattr(voice, "save_temp_wav", lambda *a, **k: "/tmp/audio.wav")
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"text": "Test transcript"}
    monkeypatch.setattr(voice, "get_whisper_model", lambda: mock_model)
    def remove_side_effect(path):
        raise FileNotFoundError("No file")
    monkeypatch.setattr(voice.os, "remove", remove_side_effect)
    text = voice.transcribe_audio()
    assert text == "Test transcript"
