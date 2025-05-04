import json
import os
import secrets
from pathlib import Path

API_KEY_PATH = Path(__file__).parent.parent / "api_keys.json"

def get_default_key():
    return os.getenv("SUHANA_DEFAULT_API_KEY") or secrets.token_urlsafe(32)

def ensure_api_keys_file():
    if not API_KEY_PATH.exists():
        default_key = get_default_key()
        print("🔐 Creating default API key store...")
        data = {
            "keys": [
                {"key": default_key, "owner": "dev", "active": True}
            ]
        }
        API_KEY_PATH.write_text(json.dumps(data, indent=2))

def load_valid_api_keys():
    ensure_api_keys_file()
    with open(API_KEY_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {entry["key"] for entry in data.get("keys", []) if entry.get("active")}
