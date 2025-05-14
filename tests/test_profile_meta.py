import tempfile
import os
from pathlib import Path
import pytest

from engine.profile import (
    load_profile_meta,
    save_profile_meta,
    summarize_profile_for_prompt
)

@pytest.fixture
def temp_profile_path(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_path = Path(tmpdir) / "profile.json"
        monkeypatch.setattr("engine.profile.PROFILE_PATH", fake_path)
        yield fake_path

def test_load_returns_default_if_file_missing(temp_profile_path):
    if temp_profile_path.exists():
        os.remove(temp_profile_path)

    profile = load_profile_meta()
    assert profile["name"] == "User"
    assert "preferences" in profile
    assert profile["preferences"]["focus"] == "general"

def test_save_and_reload_profile(temp_profile_path):
    test_data = {
        "name": "Attila",
        "preferences": {
            "preferred_language": "Hungarian",
            "communication_style": "casual",
            "focus": "AI development"
        },
        "history": ["example"]
    }

    save_profile_meta(test_data)
    reloaded = load_profile_meta()
    assert reloaded["name"] == "Attila"
    assert reloaded["preferences"]["focus"] == "AI development"
    assert isinstance(reloaded["history"], list)

def test_summarize_profile_for_prompt_output():
    profile = {
        "name": "Gizmo",
        "preferences": {
            "preferred_language": "Spanish",
            "communication_style": "short",
            "focus": "tech"
        }
    }
    summary = summarize_profile_for_prompt(profile)
    assert "Gizmo" in summary
    assert "- Preferred language: Spanish" in summary
