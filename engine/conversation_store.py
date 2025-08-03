# engine/conversation_store.py
import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from engine.user_manager import UserManager

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
USERS_DIR = BASE_DIR / "users"
DEFAULT_CATEGORY = "general"

class ConversationStore:
    """Manages conversation storage."""

    def __init__(self, base_dir: Optional[Path] = None, user_manager: Optional[UserManager] = None):
        self.base_dir = base_dir or BASE_DIR
        self.user_manager = user_manager or UserManager(base_dir=self.base_dir)
        self.users_dir = USERS_DIR

    def get_user_conversations_dir(self, user_id: str, category: str = DEFAULT_CATEGORY) -> Path:
        """Get the path to a user's conversations directory."""
        user_conv_dir = self.users_dir / user_id / "conversations" / category
        user_conv_dir.mkdir(parents=True, exist_ok=True)
        return user_conv_dir

    def get_conversation_path(self, conversation_id: str, user_id: str,
                             category: str = DEFAULT_CATEGORY) -> Path:
        """Get the path to a conversation file."""
        return self.get_user_conversations_dir(user_id, category) / f"{conversation_id}.json"

    def get_conversation_meta_path(self, conversation_id: str, user_id: str,
                                  category: str = DEFAULT_CATEGORY) -> Path:
        """Get the path to a conversation metadata file."""
        return self.get_user_conversations_dir(user_id, category) / f"{conversation_id}.meta.json"

    def create_category(self, user_id: str, category_name: str) -> bool:
        """Create a new conversation category for a user."""
        try:
            category_dir = self.users_dir / user_id / "conversations" / category_name
            category_dir.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Error creating category '{category_name}' for user '{user_id}': {e}")
            return False



    def list_conversation_meta(self, user_id: str, category: str = DEFAULT_CATEGORY) -> List[Dict[str, Any]]:
        """List metadata for all conversations for a user in a specific category."""
        results = []
        conv_dir = self.get_user_conversations_dir(user_id, category)

        for f in conv_dir.glob("*.meta.json"):
            try:
                with open(f, "r", encoding="utf-8") as meta_file:
                    meta_data = json.load(meta_file)
                    meta_data["category"] = category
                    results.append({
                        "id": f.stem.replace(".meta", ""),
                        **meta_data
                    })
            except Exception as e:
                logger.error(f"Error loading conversation metadata from {f}: {e}")

        return sorted(results, key=lambda x: x.get("last_updated", ""), reverse=True)

    def load_conversation(self, conversation_id: str, user_id: str,
                         category: str = DEFAULT_CATEGORY) -> Dict[str, Any]:
        """Load a conversation."""
        path = self.get_conversation_path(conversation_id, user_id, category)
        meta_path = self.get_conversation_meta_path(conversation_id, user_id, category)

        # Initialize with empty history
        data = {"history": []}

        # Add user profile data
        profile = self.user_manager.get_profile(user_id)
        if profile:
            data.update({
                "name": profile.get("name", "User"),
                "preferences": profile.get("preferences", {})
            })

        if not path.exists():
            return data

        try:
            with open(path, "r", encoding="utf-8") as f:
                file_data = json.load(f)
                data.update(file_data)
                data.setdefault("mode", "normal")
                data.setdefault("project_path", None)
        except Exception as e:
            logger.error(f"Error loading conversation {conversation_id}: {e}")
            return data

        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as mf:
                    meta_data = json.load(mf)
                    data.update(meta_data)
                    data["category"] = category
            except Exception as e:
                logger.error(f"Error loading conversation metadata for {conversation_id}: {e}")

        return data

    def save_conversation(self, conversation_id: str, data: Dict[str, Any],
                         user_id: str, category: str = DEFAULT_CATEGORY) -> bool:
        """Save a conversation."""
        try:
            path = self.get_conversation_path(conversation_id, user_id, category)
            history = data.get("history", [])

            if not isinstance(history, list):
                raise ValueError("Conversation history must be a list")

            # Save conversation history
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"history": history}, f, indent=2)

            # Save metadata
            meta_path = self.get_conversation_meta_path(conversation_id, user_id, category)

            # Determine title
            title = data.get("title")
            if not title and history and len(history) > 0 and history[0].get('content'):
                title = history[0].get('content', "")[0:15]
            if not title:
                title = "New Conversation"

            meta_doc = {
                "title": title,
                "created": data.get("created", datetime.now().isoformat()),
                "last_updated": datetime.now().isoformat(),
                "mode": data.get("mode", "normal"),
                "project_path": data.get("project_path", None),
                "tags": data.get("tags", []),
                "starred": data.get("starred", False),
                "archived": data.get("archived", False)
            }

            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta_doc, f, indent=2)

            return True
        except Exception as e:
            logger.error(f"Error saving conversation {conversation_id}: {e}")
            return False

    def create_new_conversation(self, user_id: str, category: str = DEFAULT_CATEGORY) -> str:
        """Create a new conversation."""
        conversation_id = str(uuid.uuid4())
        self.create_category(user_id, category)
        self.save_conversation(conversation_id, {"history": []}, user_id, category)
        return conversation_id





conversation_store = ConversationStore()

def list_conversation_meta(user_id: Optional[str] = None, category: str = DEFAULT_CATEGORY) -> List[dict]:
    """List metadata for all conversations for a user."""
    if user_id is None:
        # For backward compatibility, return empty list when user_id is not provided
        return []
    return conversation_store.list_conversation_meta(user_id, category)

def load_conversation(conversation_id: str, user_id: Optional[str] = None, category: str = DEFAULT_CATEGORY) -> dict:
    """Load a conversation."""
    if user_id is None:
        # For backward compatibility, return empty conversation when user_id is not provided
        return {"history": [], "mode": "normal", "project_path": None}
    return conversation_store.load_conversation(conversation_id, user_id, category)

def save_conversation(conversation_id: str, profile: dict, user_id: str = None, category: str = DEFAULT_CATEGORY) -> bool:
    """Save a conversation."""
    # Extract user_id from profile if not explicitly provided
    if user_id is None and isinstance(profile, dict) and "user_id" in profile:
        user_id = profile["user_id"]

    if not user_id:
        raise ValueError("user_id is required")

    return conversation_store.save_conversation(conversation_id, profile, user_id, category)

def create_new_conversation(user_id: str, category: str = DEFAULT_CATEGORY) -> str:
    """Create a new conversation."""
    return conversation_store.create_new_conversation(user_id, category)
