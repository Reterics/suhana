import pytest
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock
import types

@pytest.fixture(autouse=True)
def patch_subprocess_run(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: None)


# Provide a tiny fake sounddevice so imports succeed.
fake_sd = SimpleNamespace(
    play=lambda *a, **k: None,
    rec=lambda *a, **k: None,
    wait=lambda *a, **k: None,
    stop=lambda *a, **k: None,
    default=SimpleNamespace(samplerate=16000)
)

sys.modules.setdefault("sounddevice", fake_sd)
sys.modules.setdefault("TTS", MagicMock())
sys.modules.setdefault("TTS.api", MagicMock())
sys.modules.setdefault('langchain_community',MagicMock())
sys.modules.setdefault('langchain_community.vectorstores',MagicMock())
sys.modules.setdefault('langchain_community.embeddings',types.ModuleType("langchain_community.embeddings"))
sys.modules.setdefault('langchain_community.vectorstores.FAISS',MagicMock())

fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: False),
        device=SimpleNamespace,
        nn=SimpleNamespace(Module=object),
        __version__="0.0.0-mock",
    )
sys.modules.setdefault("torch", fake_torch)

sys.modules.setdefault('sentence_transformers', MagicMock())
sys.modules.setdefault('sentence_transformers.SentenceTransformer', MagicMock())
huggingface_mod = types.ModuleType("langchain_huggingface")
huggingface_mod.HuggingFaceEmbeddings = MagicMock()
sys.modules.setdefault('langchain_huggingface', huggingface_mod)
sys.modules.setdefault('faiss', MagicMock())

# Mock voice module dependencies
sys.modules.setdefault('sounddevice', MagicMock())
sys.modules.setdefault('whisper', MagicMock())
sys.modules.setdefault('TTS', MagicMock())
sys.modules.setdefault('TTS.api', MagicMock())
sys.modules.setdefault('soundfile', MagicMock())
sys.modules.setdefault('scipy', MagicMock())
sys.modules.setdefault('scipy.io', MagicMock())
sys.modules.setdefault('scipy.io.wavfile', MagicMock())

fake_tf = SimpleNamespace(
    AutoModel=MagicMock(),
    AutoTokenizer=MagicMock(),
    pipeline=lambda *a, **k: lambda *aa, **kk: [],
    __version__="0.0.0-mock",
)
for name in ["transformers", "transformers.pipelines", "transformers.models"]:
    sys.modules.setdefault(name, fake_tf)
