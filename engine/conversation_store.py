# engine/conversation_store.py
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List
from engine.profile import load_profile_meta

BASE_DIR = Path(__file__).parent.parent
CONVERSATION_DIR = BASE_DIR / "conversations"
CONVERSATION_DIR.mkdir(exist_ok=True)
PROFILE_META_KEYS = ["name", "preferences"]
meta = load_profile_meta()

def get_conversation_path(conversation_id: str) -> Path:
    return CONVERSATION_DIR / f"{conversation_id}.json"

def get_conversation_meta_path(conversation_id: str) -> Path:
    return CONVERSATION_DIR / f"{conversation_id}.meta.json"


def list_conversations() -> List[str]:
    return sorted([f.stem for f in CONVERSATION_DIR.glob("*.json")])

def list_conversation_meta() -> List[dict]:
    results = []
    for f in CONVERSATION_DIR.glob("*.meta.json"):
        with open(f, "r", encoding="utf-8") as meta_file:
            meta_data = json.load(meta_file)
            results.append({
                "id": f.stem.replace(".meta", ""),
                **meta_data
            })
    return sorted(results, key=lambda x: x["last_updated"], reverse=True)

def load_conversation(conversation_id: str) -> dict:
    path = get_conversation_path(conversation_id)
    if not path.exists():
        return {**meta, "history": []}

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        data.update({k: meta[k] for k in PROFILE_META_KEYS})
        return data


def save_conversation(conversation_id: str, profile: dict):
    path = get_conversation_path(conversation_id)
    history = profile.get("history", [])
    if not isinstance(history, list):
        raise ValueError("Conversation history must be a list")
    if len(history):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"history": history}, f, indent=2)
        meta_path = get_conversation_meta_path(conversation_id)
        meta_doc = {
            "title": profile.get("title", history[0]['content'][0:15]),
            "created": profile.get("created", datetime.now().isoformat()),
            "last_updated": datetime.now().isoformat()
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta_doc, f, indent=2)


def create_new_conversation() -> str:
    conversation_id = str(uuid.uuid4())
    save_conversation(conversation_id, {"history": []})
    return conversation_id
