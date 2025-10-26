import pytest
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

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

sys.modules.setdefault("sounddevice", fake_sd())
sys.modules.setdefault("TTS", MagicMock())
sys.modules.setdefault("TTS.api", MagicMock())
