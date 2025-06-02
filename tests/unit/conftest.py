import pytest
import subprocess

@pytest.fixture(autouse=True)
def patch_subprocess_run(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: None)
