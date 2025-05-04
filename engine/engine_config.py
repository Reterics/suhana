import json
from pathlib import Path
from dotenv import load_dotenv
import os
import json

load_dotenv()

SETTINGS_PATH = Path(__file__).parent.parent / "settings.json"

def load_settings():
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        settings = json.load(f)

    # Fallback to env if not in settings
    if not settings.get("openai_api_key"):
        settings["openai_api_key"] = os.getenv("OPENAI_API_KEY")
    return settings

def save_settings(settings):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

def switch_backend(new_backend, settings):
    if new_backend in ["ollama", "openai"]:
        settings["llm_backend"] = new_backend
        save_settings(settings)
        print(f"🔁 Switched to {new_backend.upper()}")
    else:
        print("❌ Supported engines: ollama, openai")
    return new_backend
