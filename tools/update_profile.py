import json
from pathlib import Path

PROFILE_PATH = Path("profile.json")

name = "update_profile"
description = "Update user preferences or profile"
pattern = r"\b(set|change|update)\b.*\b(preference|name|profile)\b.*(?P<key>[A-Za-z_]+)\b.*\bto\b\s*(?P<value>.+)"

def action(key: str, value: str) -> str:
    profile = {}
    if PROFILE_PATH.exists():
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            profile = json.load(f)

    profile.setdefault("preferences", {})[key] = value

    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)

    return f"Preference '{key}' updated to '{value}'."
