import json
import os
from pathlib import Path

PROFILE_PATH = Path(__file__).parent.parent / "profile.json"

default_profile_meta = {
    "name": "User",
    "history": [],
    "preferences": {
        "preferred_language": "English",
        "communication_style": "friendly, brief, couple of sentente max",
        "focus": "general"
    }
}

def load_profile_meta():
    if os.path.exists(PROFILE_PATH):
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return default_profile_meta.copy()

def save_profile_meta(profile):
    cleaned = {k: profile.get(k, default_profile_meta[k]) for k in default_profile_meta}
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2)

def summarize_profile_for_prompt(profile) -> str:
    preferences = profile.get("preferences", {})
    name = profile.get("name", "User")

    summary = f"You are Suhana, who speaks with {name}.\n"
    summary += "Communication preferences:\n"

    summary += "\n".join([
        f"- {k.replace('_', ' ').capitalize()}: {v}"
        for k, v in preferences.items()
    ]) or "- No specific preferences defined."
    return summary
