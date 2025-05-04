import json
import os

SETTINGS_PATH = "settings.json"

def load_settings():
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

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
