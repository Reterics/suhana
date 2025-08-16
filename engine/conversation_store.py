import logging
from typing import List, Dict, Any, Optional

from engine.database.base import DatabaseAdapter
from engine.engine_config import get_database_adapter

logger = logging.getLogger(__name__)

# Use a capitalized default to align with DB categories
DEFAULT_CATEGORY = "General"

class ConversationStore:
    """Manage conversations using the DatabaseAdapter only."""

    def __init__(self, db: Optional[DatabaseAdapter] = None):
        self.db: DatabaseAdapter = db or get_database_adapter()
        try:
            self.db.initialize_schema()
        except Exception:
            logger.exception("Failed to initialize DB schema for conversations")

    def list_conversation_meta(self, user_id: str, category: str = DEFAULT_CATEGORY) -> List[Dict[str, Any]]:
        if not user_id:
            return []
        try:
            return self.db.list_conversation_meta(user_id=user_id, category=category)
        except Exception:
            logger.exception("Failed to list conversation meta from DB")
            return []

    def load_conversation(self, conversation_id: str, user_id: str, category: str = DEFAULT_CATEGORY) -> Optional[Dict[str, Any]]:
        if not user_id:
            raise ValueError("user_id is required")
        try:
            data = self.db.load_conversation(user_id=user_id, conversation_id=conversation_id)
            if data is None:
                return None
            # Ensure some sane defaults
            if "history" not in data:
                data["history"] = []
            if "category" not in data:
                data["category"] = category
            if "mode" not in data:
                data["mode"] = "normal"
            data.setdefault("project_path", None)
            return data
        except Exception:
            logger.exception("Failed to load conversation from DB")
            return None

    def save_conversation(self, conversation_id: str, data: Dict[str, Any], user_id: str, category: str = DEFAULT_CATEGORY) -> bool:
        if not user_id:
            raise ValueError("user_id is required")
        # Ensure category is present for metadata extraction in adapter
        payload = dict(data)
        payload.setdefault("category", category)
        try:
            return self.db.save_conversation(user_id=user_id, conversation_id=conversation_id, data=payload)
        except Exception:
            logger.exception("Failed to save conversation to DB")
            return False

    def create_new_conversation(self, user_id: str, category: str = DEFAULT_CATEGORY) -> str:
        if not user_id:
            raise ValueError("user_id is required")
        try:
            # Let adapter set metadata; title defaults are handled there as needed
            return self.db.create_new_conversation(user_id=user_id, title="New Conversation", category=category)
        except Exception:
            logger.exception("Failed to create conversation in DB")
            # If adapter failed to return an id, rethrow to make the error visible
            raise

conversation_store = ConversationStore()

def list_conversation_meta(user_id: Optional[str] = None, category: str = DEFAULT_CATEGORY) -> List[dict]:
    return conversation_store.list_conversation_meta(user_id, category) if user_id else []

def load_conversation(conversation_id: str, user_id: Optional[str] = None, category: str = DEFAULT_CATEGORY) -> dict:
    """Load a conversation."""
    return conversation_store.load_conversation(conversation_id, user_id, category)

def save_conversation(conversation_id: str, profile: dict, user_id: str = None, category: str = DEFAULT_CATEGORY) -> bool:
    """Save a conversation."""
    return conversation_store.save_conversation(conversation_id, profile, user_id, category)

def create_new_conversation(user_id: str, category: str = DEFAULT_CATEGORY) -> str:
    """Create a new conversation."""
    return conversation_store.create_new_conversation(user_id, category)
