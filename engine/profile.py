import json
import os
from pathlib import Path

PROFILE_PATH = Path(__file__).parent.parent / "profile.json"

default_profile = {
    "name": "User",
    "history": [],
    "preferences": {
        "preferred_language": "English",
        "communication_style": "neutral",
        "focus": "general"
    },
    "memory": [
    {
      "type": "fact",
      "content": "Suhana should act like a helpful AI teammate, not a servant."
    }
  ]
}

def load_profile():
    if os.path.exists(PROFILE_PATH):
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return default_profile.copy()

def save_profile(profile):
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)

def summarize_profile_for_prompt(profile) -> str:
    preferences = profile.get("preferences", {})
    memory = profile.get("memory", [])

    summary = f"You are Suhana, You are speaking to {profile.get('name', 'User')}.\nPreferences:\n"
    summary += "\n".join([f"- {k.replace('_', ' ').capitalize()}: {v}" for k, v in preferences.items()]) or "None"
    if memory:
        summary += "\nKnown facts:\n"
        summary += "\n".join([f"- {item['content']}" for item in memory])
    return summary
