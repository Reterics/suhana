# engine/conversation_store.py
import json
import uuid
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Import user manager for user-specific operations
from engine.user_manager import UserManager

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
LEGACY_CONVERSATION_DIR = BASE_DIR / "conversations"
LEGACY_CONVERSATION_DIR.mkdir(exist_ok=True)

# Default category for conversations
DEFAULT_CATEGORY = "general"

class ConversationStore:
    """
    Manages conversation storage with support for user-specific conversations,
    categories, and archiving.

    This class handles:
    - User-specific conversation storage
    - Conversation categories/folders
    - Conversation metadata
    - Conversation archiving and backup
    """

    def __init__(self, base_dir: Optional[Path] = None, user_manager: Optional[UserManager] = None):
        """
        Initialize the ConversationStore.

        Args:
            base_dir: Base directory for conversation files. If None, uses the parent directory of the current file.
            user_manager: UserManager instance for user operations. If None, creates a new instance.
        """
        self.base_dir = base_dir or Path(__file__).parent.parent
        self.user_manager = user_manager or UserManager(base_dir=self.base_dir)
        self.users_dir = self.base_dir / "users"

        # Ensure legacy conversation directory exists
        self.legacy_conversation_dir = self.base_dir / "conversations"
        self.legacy_conversation_dir.mkdir(exist_ok=True)

    def get_user_conversations_dir(self, user_id: str, category: str = DEFAULT_CATEGORY) -> Path:
        """
        Get the path to a user's conversations directory for a specific category.

        Args:
            user_id: User ID to get conversations directory for
            category: Conversation category (folder)

        Returns:
            Path to the user's conversations directory for the specified category
        """
        user_conv_dir = self.users_dir / user_id / "conversations" / category
        user_conv_dir.mkdir(parents=True, exist_ok=True)
        return user_conv_dir

    def get_conversation_path(self, conversation_id: str, user_id: Optional[str] = None,
                             category: str = DEFAULT_CATEGORY) -> Path:
        """
        Get the path to a conversation file.

        Args:
            conversation_id: ID of the conversation
            user_id: Optional user ID. If None, uses legacy path.
            category: Conversation category (folder)

        Returns:
            Path to the conversation file
        """
        if user_id:
            return self.get_user_conversations_dir(user_id, category) / f"{conversation_id}.json"
        else:
            # Legacy path for backward compatibility
            return self.legacy_conversation_dir / f"{conversation_id}.json"

    def get_conversation_meta_path(self, conversation_id: str, user_id: Optional[str] = None,
                                  category: str = DEFAULT_CATEGORY) -> Path:
        """
        Get the path to a conversation metadata file.

        Args:
            conversation_id: ID of the conversation
            user_id: Optional user ID. If None, uses legacy path.
            category: Conversation category (folder)

        Returns:
            Path to the conversation metadata file
        """
        if user_id:
            return self.get_user_conversations_dir(user_id, category) / f"{conversation_id}.meta.json"
        else:
            # Legacy path for backward compatibility
            return self.legacy_conversation_dir / f"{conversation_id}.meta.json"

    def list_categories(self, user_id: str) -> List[str]:
        """
        List all conversation categories for a user.

        Args:
            user_id: User ID to list categories for

        Returns:
            List of category names
        """
        user_conv_dir = self.users_dir / user_id / "conversations"
        if not user_conv_dir.exists():
            return [DEFAULT_CATEGORY]

        categories = [d.name for d in user_conv_dir.iterdir() if d.is_dir()]
        if not categories:
            return [DEFAULT_CATEGORY]

        return sorted(categories)

    def create_category(self, user_id: str, category_name: str) -> bool:
        """
        Create a new conversation category for a user.

        Args:
            user_id: User ID to create category for
            category_name: Name of the category to create

        Returns:
            True if category was created successfully, False otherwise
        """
        try:
            category_dir = self.users_dir / user_id / "conversations" / category_name
            category_dir.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Error creating category '{category_name}' for user '{user_id}': {e}")
            return False

    def rename_category(self, user_id: str, old_name: str, new_name: str) -> bool:
        """
        Rename a conversation category for a user.

        Args:
            user_id: User ID to rename category for
            old_name: Current name of the category
            new_name: New name for the category

        Returns:
            True if category was renamed successfully, False otherwise
        """
        try:
            old_dir = self.users_dir / user_id / "conversations" / old_name
            new_dir = self.users_dir / user_id / "conversations" / new_name

            if not old_dir.exists():
                return False

            if new_dir.exists():
                return False

            old_dir.rename(new_dir)
            return True
        except Exception as e:
            logger.error(f"Error renaming category from '{old_name}' to '{new_name}' for user '{user_id}': {e}")
            return False

    def delete_category(self, user_id: str, category_name: str) -> bool:
        """
        Delete a conversation category for a user.

        Args:
            user_id: User ID to delete category for
            category_name: Name of the category to delete

        Returns:
            True if category was deleted successfully, False otherwise
        """
        try:
            if category_name == DEFAULT_CATEGORY:
                return False  # Don't allow deleting the default category

            category_dir = self.users_dir / user_id / "conversations" / category_name

            if not category_dir.exists():
                return False

            # Check if category is empty
            if any(category_dir.iterdir()):
                return False  # Don't delete non-empty categories

            category_dir.rmdir()
            return True
        except Exception as e:
            logger.error(f"Error deleting category '{category_name}' for user '{user_id}': {e}")
            return False

    def list_conversations(self, user_id: Optional[str] = None,
                          category: str = DEFAULT_CATEGORY) -> List[str]:
        """
        List all conversations for a user in a specific category.

        Args:
            user_id: Optional user ID. If None, lists legacy conversations.
            category: Conversation category to list

        Returns:
            List of conversation IDs
        """
        if user_id:
            conv_dir = self.get_user_conversations_dir(user_id, category)
            return sorted([f.stem for f in conv_dir.glob("*.json") if not f.name.endswith(".meta.json")])
        else:
            # Legacy path for backward compatibility
            return sorted([f.stem for f in self.legacy_conversation_dir.glob("*.json")
                          if not f.name.endswith(".meta.json")])

    def list_conversation_meta(self, user_id: Optional[str] = None,
                              category: str = DEFAULT_CATEGORY) -> List[Dict[str, Any]]:
        """
        List metadata for all conversations for a user in a specific category.

        Args:
            user_id: Optional user ID. If None, lists legacy conversations.
            category: Conversation category to list

        Returns:
            List of dictionaries containing conversation metadata
        """
        results = []

        if user_id:
            conv_dir = self.get_user_conversations_dir(user_id, category)
            meta_pattern = "*.meta.json"
        else:
            # Legacy path for backward compatibility
            conv_dir = self.legacy_conversation_dir
            meta_pattern = "*.meta.json"

        for f in conv_dir.glob(meta_pattern):
            try:
                with open(f, "r", encoding="utf-8") as meta_file:
                    meta_data = json.load(meta_file)

                    # Add category to metadata
                    meta_data["category"] = category

                    results.append({
                        "id": f.stem.replace(".meta", ""),
                        **meta_data
                    })
            except Exception as e:
                logger.error(f"Error loading conversation metadata from {f}: {e}")

        return sorted(results, key=lambda x: x.get("last_updated", ""), reverse=True)

    def load_conversation(self, conversation_id: str, user_id: Optional[str] = None,
                         category: str = DEFAULT_CATEGORY) -> Dict[str, Any]:
        """
        Load a conversation.

        Args:
            conversation_id: ID of the conversation to load
            user_id: Optional user ID. If None, loads from legacy path.
            category: Conversation category

        Returns:
            Dictionary containing the conversation data
        """
        path = self.get_conversation_path(conversation_id, user_id, category)
        meta_path = self.get_conversation_meta_path(conversation_id, user_id, category)

        # Initialize with empty history
        data = {"history": []}

        # Add user profile data if available
        if user_id:
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
                    # Add category to data
                    data["category"] = category
            except Exception as e:
                logger.error(f"Error loading conversation metadata for {conversation_id}: {e}")

        return data

    def save_conversation(self, conversation_id: str, data: Dict[str, Any],
                         user_id: Optional[str] = None, category: str = DEFAULT_CATEGORY) -> bool:
        """
        Save a conversation.

        Args:
            conversation_id: ID of the conversation to save
            data: Dictionary containing the conversation data
            user_id: Optional user ID. If None, saves to legacy path.
            category: Conversation category

        Returns:
            True if conversation was saved successfully, False otherwise
        """
        try:
            path = self.get_conversation_path(conversation_id, user_id, category)
            history = data.get("history", [])

            if not isinstance(history, list):
                raise ValueError("Conversation history must be a list")

            if len(history):
                # Save conversation history
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"history": history}, f, indent=2)

                # Save metadata
                meta_path = self.get_conversation_meta_path(conversation_id, user_id, category)
                meta_doc = {
                    "title": data.get("title", history[0].get('content', "")[0:15] if history[0].get('content') else "New Conversation"),
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

            return False
        except Exception as e:
            logger.error(f"Error saving conversation {conversation_id}: {e}")
            return False

    def create_new_conversation(self, user_id: Optional[str] = None,
                               category: str = DEFAULT_CATEGORY) -> str:
        """
        Create a new conversation.

        Args:
            user_id: Optional user ID. If None, creates in legacy path.
            category: Conversation category

        Returns:
            ID of the new conversation
        """
        conversation_id = str(uuid.uuid4())

        # Ensure category exists if user_id is provided
        if user_id:
            self.create_category(user_id, category)

        # Initialize with empty history
        self.save_conversation(conversation_id, {"history": []}, user_id, category)

        return conversation_id

    def delete_conversation(self, conversation_id: str, user_id: Optional[str] = None,
                           category: str = DEFAULT_CATEGORY) -> bool:
        """
        Delete a conversation.

        Args:
            conversation_id: ID of the conversation to delete
            user_id: Optional user ID. If None, deletes from legacy path.
            category: Conversation category

        Returns:
            True if conversation was deleted successfully, False otherwise
        """
        try:
            path = self.get_conversation_path(conversation_id, user_id, category)
            meta_path = self.get_conversation_meta_path(conversation_id, user_id, category)

            if path.exists():
                path.unlink()

            if meta_path.exists():
                meta_path.unlink()

            return True
        except Exception as e:
            logger.error(f"Error deleting conversation {conversation_id}: {e}")
            return False

    def archive_conversation(self, conversation_id: str, user_id: str,
                            source_category: str = DEFAULT_CATEGORY) -> bool:
        """
        Archive a conversation by moving it to the 'archived' category.

        Args:
            conversation_id: ID of the conversation to archive
            user_id: User ID
            source_category: Source category of the conversation

        Returns:
            True if conversation was archived successfully, False otherwise
        """
        try:
            # Ensure archived category exists
            self.create_category(user_id, "archived")

            # Load conversation
            conversation = self.load_conversation(conversation_id, user_id, source_category)

            # Mark as archived
            conversation["archived"] = True

            # Save to archived category
            success = self.save_conversation(conversation_id, conversation, user_id, "archived")

            if success:
                # Delete from source category
                self.delete_conversation(conversation_id, user_id, source_category)

            return success
        except Exception as e:
            logger.error(f"Error archiving conversation {conversation_id}: {e}")
            return False

    def unarchive_conversation(self, conversation_id: str, user_id: str,
                              target_category: str = DEFAULT_CATEGORY) -> bool:
        """
        Unarchive a conversation by moving it from the 'archived' category to the target category.

        Args:
            conversation_id: ID of the conversation to unarchive
            user_id: User ID
            target_category: Target category to move the conversation to

        Returns:
            True if conversation was unarchived successfully, False otherwise
        """
        try:
            # Ensure target category exists
            self.create_category(user_id, target_category)

            # Load conversation from archived
            conversation = self.load_conversation(conversation_id, user_id, "archived")

            # Mark as not archived
            conversation["archived"] = False

            # Save to target category
            success = self.save_conversation(conversation_id, conversation, user_id, target_category)

            if success:
                # Delete from archived category
                self.delete_conversation(conversation_id, user_id, "archived")

            return success
        except Exception as e:
            logger.error(f"Error unarchiving conversation {conversation_id}: {e}")
            return False

    def move_conversation(self, conversation_id: str, user_id: str,
                         source_category: str, target_category: str) -> bool:
        """
        Move a conversation from one category to another.

        Args:
            conversation_id: ID of the conversation to move
            user_id: User ID
            source_category: Source category of the conversation
            target_category: Target category to move the conversation to

        Returns:
            True if conversation was moved successfully, False otherwise
        """
        try:
            # Ensure target category exists
            self.create_category(user_id, target_category)

            # Load conversation from source
            conversation = self.load_conversation(conversation_id, user_id, source_category)

            # Save to target category
            success = self.save_conversation(conversation_id, conversation, user_id, target_category)

            if success:
                # Delete from source category
                self.delete_conversation(conversation_id, user_id, source_category)

            return success
        except Exception as e:
            logger.error(f"Error moving conversation {conversation_id}: {e}")
            return False

    def star_conversation(self, conversation_id: str, user_id: str,
                         category: str = DEFAULT_CATEGORY, starred: bool = True) -> bool:
        """
        Star or unstar a conversation.

        Args:
            conversation_id: ID of the conversation to star/unstar
            user_id: User ID
            category: Conversation category
            starred: True to star, False to unstar

        Returns:
            True if operation was successful, False otherwise
        """
        try:
            # Load conversation
            conversation = self.load_conversation(conversation_id, user_id, category)

            # Update starred status
            conversation["starred"] = starred

            # Save conversation
            return self.save_conversation(conversation_id, conversation, user_id, category)
        except Exception as e:
            logger.error(f"Error {'starring' if starred else 'unstarring'} conversation {conversation_id}: {e}")
            return False

    def add_tags(self, conversation_id: str, user_id: str,
                category: str = DEFAULT_CATEGORY, tags: List[str] = None) -> bool:
        """
        Add tags to a conversation.

        Args:
            conversation_id: ID of the conversation to tag
            user_id: User ID
            category: Conversation category
            tags: List of tags to add

        Returns:
            True if operation was successful, False otherwise
        """
        if not tags:
            return True

        try:
            # Load conversation
            conversation = self.load_conversation(conversation_id, user_id, category)

            # Get existing tags
            existing_tags = conversation.get("tags", [])

            # Add new tags (avoid duplicates)
            updated_tags = list(set(existing_tags + tags))

            # Update tags
            conversation["tags"] = updated_tags

            # Save conversation
            return self.save_conversation(conversation_id, conversation, user_id, category)
        except Exception as e:
            logger.error(f"Error adding tags to conversation {conversation_id}: {e}")
            return False

    def remove_tags(self, conversation_id: str, user_id: str,
                   category: str = DEFAULT_CATEGORY, tags: List[str] = None) -> bool:
        """
        Remove tags from a conversation.

        Args:
            conversation_id: ID of the conversation to untag
            user_id: User ID
            category: Conversation category
            tags: List of tags to remove

        Returns:
            True if operation was successful, False otherwise
        """
        if not tags:
            return True

        try:
            # Load conversation
            conversation = self.load_conversation(conversation_id, user_id, category)

            # Get existing tags
            existing_tags = conversation.get("tags", [])

            # Remove specified tags
            updated_tags = [tag for tag in existing_tags if tag not in tags]

            # Update tags
            conversation["tags"] = updated_tags

            # Save conversation
            return self.save_conversation(conversation_id, conversation, user_id, category)
        except Exception as e:
            logger.error(f"Error removing tags from conversation {conversation_id}: {e}")
            return False

    def backup_conversations(self, user_id: str, backup_path: Optional[Path] = None) -> Tuple[bool, str]:
        """
        Backup all conversations for a user.

        Args:
            user_id: User ID to backup conversations for
            backup_path: Optional path to save backup. If None, creates in user directory.

        Returns:
            Tuple of (success, backup_path or error_message)
        """
        try:
            user_conv_dir = self.users_dir / user_id / "conversations"

            if not user_conv_dir.exists():
                return False, f"No conversations found for user {user_id}"

            # Create backup directory if not specified
            if not backup_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = self.users_dir / user_id / "backups" / f"conversations_{timestamp}"

            backup_path.mkdir(parents=True, exist_ok=True)

            # Copy all conversation files
            for category_dir in user_conv_dir.iterdir():
                if category_dir.is_dir():
                    category_backup = backup_path / category_dir.name
                    category_backup.mkdir(exist_ok=True)

                    for file in category_dir.glob("*.*"):
                        shutil.copy2(file, category_backup)

            return True, str(backup_path)
        except Exception as e:
            error_msg = f"Error backing up conversations for user {user_id}: {e}"
            logger.error(error_msg)
            return False, error_msg

    def restore_backup(self, user_id: str, backup_path: Path) -> Tuple[bool, str]:
        """
        Restore conversations from a backup.

        Args:
            user_id: User ID to restore conversations for
            backup_path: Path to the backup directory

        Returns:
            Tuple of (success, message)
        """
        try:
            if not backup_path.exists() or not backup_path.is_dir():
                return False, f"Backup path {backup_path} does not exist or is not a directory"

            user_conv_dir = self.users_dir / user_id / "conversations"

            # Create conversations directory if it doesn't exist
            user_conv_dir.mkdir(parents=True, exist_ok=True)

            # Copy all backup files to conversations directory
            for category_dir in backup_path.iterdir():
                if category_dir.is_dir():
                    target_category = user_conv_dir / category_dir.name
                    target_category.mkdir(exist_ok=True)

                    for file in category_dir.glob("*.*"):
                        shutil.copy2(file, target_category)

            return True, f"Backup restored successfully from {backup_path}"
        except Exception as e:
            error_msg = f"Error restoring backup for user {user_id}: {e}"
            logger.error(error_msg)
            return False, error_msg

    def migrate_legacy_conversations(self, user_id: str) -> Tuple[int, int]:
        """
        Migrate conversations from the legacy storage to user-specific storage.

        Args:
            user_id: User ID to migrate conversations to

        Returns:
            Tuple of (success_count, failure_count)
        """
        success_count = 0
        failure_count = 0

        # Ensure user conversations directory exists
        user_conv_dir = self.users_dir / user_id / "conversations" / DEFAULT_CATEGORY
        user_conv_dir.mkdir(parents=True, exist_ok=True)

        # Get all legacy conversations
        for json_file in self.legacy_conversation_dir.glob("*.json"):
            if json_file.name.endswith(".meta.json"):
                continue

            conversation_id = json_file.stem
            meta_file = self.legacy_conversation_dir / f"{conversation_id}.meta.json"

            try:
                # Load conversation data
                with open(json_file, "r", encoding="utf-8") as f:
                    conversation_data = json.load(f)

                # Load metadata if available
                meta_data = {}
                if meta_file.exists():
                    with open(meta_file, "r", encoding="utf-8") as f:
                        meta_data = json.load(f)

                # Combine data
                combined_data = {**conversation_data, **meta_data}

                # Save to user directory
                if self.save_conversation(conversation_id, combined_data, user_id, DEFAULT_CATEGORY):
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as e:
                logger.error(f"Error migrating conversation {conversation_id}: {e}")
                failure_count += 1

        return success_count, failure_count


# For backward compatibility
conversation_store = ConversationStore()

def get_conversation_path(conversation_id: str) -> Path:
    return conversation_store.get_conversation_path(conversation_id)

def get_conversation_meta_path(conversation_id: str) -> Path:
    return conversation_store.get_conversation_meta_path(conversation_id)

def list_conversations() -> List[str]:
    return conversation_store.list_conversations()

def list_conversation_meta() -> List[dict]:
    return conversation_store.list_conversation_meta()

def load_conversation(conversation_id: str) -> dict:
    return conversation_store.load_conversation(conversation_id)

def save_conversation(conversation_id: str, profile: dict):
    return conversation_store.save_conversation(conversation_id, profile)

def create_new_conversation() -> str:
    return conversation_store.create_new_conversation()
