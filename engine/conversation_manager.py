import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import logging
import shutil

logger = logging.getLogger(__name__)

class ConversationManager:
    """
    Manages conversations with support for user-specific storage and organization.

    This class handles:
    - Storing conversations in user-specific directories
    - Conversation categories/folders
    - Metadata for better conversation organization
    - Conversation archiving and backup
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize the ConversationManager.

        Args:
            base_dir: Base directory for the application. If None, uses the parent directory of the current file.
        """
        self.base_dir = base_dir or Path(__file__).parent.parent
        self.users_dir = self.base_dir / "users"
        self.legacy_conversations_dir = self.base_dir / "conversations"

    def get_user_conversations_dir(self, user_id: str) -> Path:
        """
        Get the conversations directory for a specific user.

        Args:
            user_id: User ID to get conversations directory for

        Returns:
            Path to the user's conversations directory
        """
        user_conversations_dir = self.users_dir / user_id / "conversations"
        user_conversations_dir.mkdir(parents=True, exist_ok=True)
        return user_conversations_dir

    def get_conversation_path(self, user_id: str, conversation_id: str) -> Path:
        """
        Get the path to a specific conversation file.

        Args:
            user_id: User ID that owns the conversation
            conversation_id: ID of the conversation

        Returns:
            Path to the conversation file
        """
        return self.get_user_conversations_dir(user_id) / f"{conversation_id}.json"

    def get_conversation_meta_path(self, user_id: str, conversation_id: str) -> Path:
        """
        Get the path to a specific conversation metadata file.

        Args:
            user_id: User ID that owns the conversation
            conversation_id: ID of the conversation

        Returns:
            Path to the conversation metadata file
        """
        return self.get_user_conversations_dir(user_id) / f"{conversation_id}.meta.json"

    def list_conversations(self, user_id: str, category: Optional[str] = None) -> List[str]:
        """
        List all conversation IDs for a specific user, optionally filtered by category.

        Args:
            user_id: User ID to list conversations for
            category: Optional category to filter by

        Returns:
            List of conversation IDs
        """
        conversations_dir = self.get_user_conversations_dir(user_id)

        # If category is specified, look in the category subdirectory
        if category:
            category_dir = conversations_dir / category
            if category_dir.exists():
                conversations_dir = category_dir

        # Get all .json files that don't end with .meta.json
        return sorted([
            f.stem for f in conversations_dir.glob("*.json")
            if not f.name.endswith(".meta.json")
        ])

    def list_conversation_meta(self, user_id: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List metadata for all conversations for a specific user, optionally filtered by category.

        Args:
            user_id: User ID to list conversation metadata for
            category: Optional category to filter by

        Returns:
            List of dictionaries containing conversation metadata
        """
        conversations_dir = self.get_user_conversations_dir(user_id)

        # If category is specified, look in the category subdirectory
        if category:
            category_dir = conversations_dir / category
            if category_dir.exists():
                conversations_dir = category_dir

        results = []
        for f in conversations_dir.glob("*.meta.json"):
            try:
                with open(f, "r", encoding="utf-8") as meta_file:
                    meta_data = json.load(meta_file)

                    # Add conversation ID and category to metadata
                    conv_id = f.stem.replace(".meta", "")
                    meta_data["id"] = conv_id
                    meta_data["category"] = category or "default"

                    results.append(meta_data)
            except Exception as e:
                logger.error(f"Error loading conversation metadata for {f.name}: {e}")

        # Sort by last_updated, most recent first
        return sorted(results, key=lambda x: x.get("last_updated", ""), reverse=True)

    def list_categories(self, user_id: str) -> List[str]:
        """
        List all conversation categories for a specific user.

        Args:
            user_id: User ID to list categories for

        Returns:
            List of category names
        """
        conversations_dir = self.get_user_conversations_dir(user_id)

        # Get all subdirectories
        return sorted([d.name for d in conversations_dir.iterdir() if d.is_dir()])

    def create_category(self, user_id: str, category: str) -> bool:
        """
        Create a new conversation category for a specific user.

        Args:
            user_id: User ID to create category for
            category: Name of the category to create

        Returns:
            True if category was created successfully, False otherwise
        """
        try:
            category_dir = self.get_user_conversations_dir(user_id) / category
            category_dir.mkdir(exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Error creating category '{category}' for user '{user_id}': {e}")
            return False

    def move_conversation_to_category(self, user_id: str, conversation_id: str, category: str) -> bool:
        """
        Move a conversation to a specific category.

        Args:
            user_id: User ID that owns the conversation
            conversation_id: ID of the conversation to move
            category: Name of the category to move the conversation to

        Returns:
            True if conversation was moved successfully, False otherwise
        """
        try:
            # Ensure category exists
            category_dir = self.get_user_conversations_dir(user_id) / category
            category_dir.mkdir(exist_ok=True)

            # Get paths to conversation files
            conv_path = self.get_conversation_path(user_id, conversation_id)
            meta_path = self.get_conversation_meta_path(user_id, conversation_id)

            # Get paths to destination files
            dest_conv_path = category_dir / f"{conversation_id}.json"
            dest_meta_path = category_dir / f"{conversation_id}.meta.json"

            # Move files if they exist
            if conv_path.exists():
                shutil.move(str(conv_path), str(dest_conv_path))

            if meta_path.exists():
                # Update metadata with new category
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta_data = json.load(f)

                meta_data["category"] = category

                # Write to new location
                with open(dest_meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta_data, f, indent=2)

                # Remove old file
                meta_path.unlink()

            return True
        except Exception as e:
            logger.error(f"Error moving conversation '{conversation_id}' to category '{category}': {e}")
            return False

    def load_conversation(self, user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a conversation for a specific user.

        Args:
            user_id: User ID that owns the conversation
            conversation_id: ID of the conversation to load

        Returns:
            Dictionary containing the conversation data, or None if conversation doesn't exist
        """
        # First, try to find the conversation in the user's directory
        conv_path = self.get_conversation_path(user_id, conversation_id)
        meta_path = self.get_conversation_meta_path(user_id, conversation_id)

        # If not found, check categories
        if not conv_path.exists():
            for category in self.list_categories(user_id):
                category_conv_path = self.get_user_conversations_dir(user_id) / category / f"{conversation_id}.json"
                if category_conv_path.exists():
                    conv_path = category_conv_path
                    meta_path = self.get_user_conversations_dir(user_id) / category / f"{conversation_id}.meta.json"
                    break

        # If still not found, return None
        if not conv_path.exists():
            return None

        try:
            # Load conversation data
            with open(conv_path, "r", encoding="utf-8") as f:
                conversation = json.load(f)

            # Load metadata if it exists
            if meta_path.exists():
                with open(meta_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                    conversation.update(metadata)

            # Add conversation ID
            conversation["id"] = conversation_id

            return conversation
        except Exception as e:
            logger.error(f"Error loading conversation '{conversation_id}' for user '{user_id}': {e}")
            return None

    def save_conversation(self, user_id: str, conversation_id: str, conversation: Dict[str, Any]) -> bool:
        """
        Save a conversation for a specific user.

        Args:
            user_id: User ID that owns the conversation
            conversation_id: ID of the conversation to save
            conversation: Dictionary containing the conversation data

        Returns:
            True if conversation was saved successfully, False otherwise
        """
        try:
            # Extract history and metadata
            history = conversation.get("history", [])

            # Determine category
            category = conversation.get("category")

            # Determine the path to save to
            if category and category != "default":
                category_dir = self.get_user_conversations_dir(user_id) / category
                category_dir.mkdir(exist_ok=True)
                conv_path = category_dir / f"{conversation_id}.json"
                meta_path = category_dir / f"{conversation_id}.meta.json"
            else:
                conv_path = self.get_conversation_path(user_id, conversation_id)
                meta_path = self.get_conversation_meta_path(user_id, conversation_id)

            # Save conversation data
            with open(conv_path, "w", encoding="utf-8") as f:
                json.dump({"history": history}, f, indent=2)

            # Save metadata
            meta_data = {
                "title": conversation.get("title", history[0]["content"][0:15] if history else "New Conversation"),
                "created": conversation.get("created", datetime.now().isoformat()),
                "last_updated": datetime.now().isoformat(),
                "category": category or "default",
                "tags": conversation.get("tags", []),
                "starred": conversation.get("starred", False),
                "archived": conversation.get("archived", False)
            }

            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta_data, f, indent=2)

            return True
        except Exception as e:
            logger.error(f"Error saving conversation '{conversation_id}' for user '{user_id}': {e}")
            return False

    def create_new_conversation(self, user_id: str, title: Optional[str] = None, category: Optional[str] = None) -> str:
        """
        Create a new conversation for a specific user.

        Args:
            user_id: User ID to create conversation for
            title: Optional title for the conversation
            category: Optional category for the conversation

        Returns:
            ID of the new conversation
        """
        conversation_id = str(uuid.uuid4())

        # Create empty conversation
        conversation = {
            "history": [],
            "title": title or "New Conversation",
            "category": category
        }

        # Save the conversation
        self.save_conversation(user_id, conversation_id, conversation)

        return conversation_id

    def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """
        Delete a conversation for a specific user.

        Args:
            user_id: User ID that owns the conversation
            conversation_id: ID of the conversation to delete

        Returns:
            True if conversation was deleted successfully, False otherwise
        """
        try:
            # First, try to find the conversation in the user's directory
            conv_path = self.get_conversation_path(user_id, conversation_id)
            meta_path = self.get_conversation_meta_path(user_id, conversation_id)

            # If not found, check categories
            if not conv_path.exists():
                for category in self.list_categories(user_id):
                    category_conv_path = self.get_user_conversations_dir(user_id) / category / f"{conversation_id}.json"
                    if category_conv_path.exists():
                        conv_path = category_conv_path
                        meta_path = self.get_user_conversations_dir(user_id) / category / f"{conversation_id}.meta.json"
                        break

            # Delete files if they exist
            if conv_path.exists():
                conv_path.unlink()

            if meta_path.exists():
                meta_path.unlink()

            return True
        except Exception as e:
            logger.error(f"Error deleting conversation '{conversation_id}' for user '{user_id}': {e}")
            return False

    def archive_conversation(self, user_id: str, conversation_id: str) -> bool:
        """
        Archive a conversation for a specific user.

        Args:
            user_id: User ID that owns the conversation
            conversation_id: ID of the conversation to archive

        Returns:
            True if conversation was archived successfully, False otherwise
        """
        try:
            # Load the conversation
            conversation = self.load_conversation(user_id, conversation_id)
            if not conversation:
                return False

            # Mark as archived
            conversation["archived"] = True

            # Save the conversation
            return self.save_conversation(user_id, conversation_id, conversation)
        except Exception as e:
            logger.error(f"Error archiving conversation '{conversation_id}' for user '{user_id}': {e}")
            return False

    def star_conversation(self, user_id: str, conversation_id: str, starred: bool = True) -> bool:
        """
        Star or unstar a conversation for a specific user.

        Args:
            user_id: User ID that owns the conversation
            conversation_id: ID of the conversation to star/unstar
            starred: Whether to star (True) or unstar (False) the conversation

        Returns:
            True if conversation was starred/unstarred successfully, False otherwise
        """
        try:
            # Load the conversation
            conversation = self.load_conversation(user_id, conversation_id)
            if not conversation:
                return False

            # Set starred status
            conversation["starred"] = starred

            # Save the conversation
            return self.save_conversation(user_id, conversation_id, conversation)
        except Exception as e:
            logger.error(f"Error {'starring' if starred else 'unstarring'} conversation '{conversation_id}' for user '{user_id}': {e}")
            return False

    def search_conversations(self, user_id: str, query: str) -> List[Dict[str, Any]]:
        """
        Search for conversations containing the query string.

        Args:
            user_id: User ID to search conversations for
            query: Query string to search for

        Returns:
            List of dictionaries containing conversation metadata
        """
        results = []
        query = query.lower()

        # Get all conversation metadata
        all_meta = []
        for category in [None] + self.list_categories(user_id):
            all_meta.extend(self.list_conversation_meta(user_id, category))

        # First, search in metadata (titles, etc.)
        for meta in all_meta:
            if query in meta.get("title", "").lower():
                results.append(meta)
                continue

            # Check tags
            if any(query in tag.lower() for tag in meta.get("tags", [])):
                results.append(meta)
                continue

        # Then, search in conversation content
        for conv_id in self.list_conversations(user_id):
            # Skip if already in results
            if any(r["id"] == conv_id for r in results):
                continue

            # Load conversation
            conversation = self.load_conversation(user_id, conv_id)
            if not conversation:
                continue

            # Search in history
            for message in conversation.get("history", []):
                if query in message.get("content", "").lower():
                    # Add metadata to results
                    for meta in all_meta:
                        if meta["id"] == conv_id:
                            results.append(meta)
                            break
                    break

        return results

    def export_conversation(self, user_id: str, conversation_id: str, format: str = "json") -> Optional[str]:
        """
        Export a conversation to a specific format.

        Args:
            user_id: User ID that owns the conversation
            conversation_id: ID of the conversation to export
            format: Format to export to (json, markdown, text)

        Returns:
            String containing the exported conversation, or None if export failed
        """
        try:
            # Load the conversation
            conversation = self.load_conversation(user_id, conversation_id)
            if not conversation:
                return None

            if format == "json":
                return json.dumps(conversation, indent=2)
            elif format == "markdown":
                return self._export_to_markdown(conversation)
            elif format == "text":
                return self._export_to_text(conversation)
            else:
                logger.error(f"Unsupported export format: {format}")
                return None
        except Exception as e:
            logger.error(f"Error exporting conversation '{conversation_id}' for user '{user_id}': {e}")
            return None

    def _export_to_markdown(self, conversation: Dict[str, Any]) -> str:
        """
        Export a conversation to Markdown format.

        Args:
            conversation: Dictionary containing the conversation data

        Returns:
            String containing the conversation in Markdown format
        """
        title = conversation.get("title", "Conversation")
        created = conversation.get("created", "")

        md = f"# {title}\n\n"
        md += f"Created: {created}\n\n"

        for message in conversation.get("history", []):
            role = message.get("role", "unknown")
            content = message.get("content", "")

            md += f"## {role.capitalize()}\n\n"
            md += f"{content}\n\n"

        return md

    def _export_to_text(self, conversation: Dict[str, Any]) -> str:
        """
        Export a conversation to plain text format.

        Args:
            conversation: Dictionary containing the conversation data

        Returns:
            String containing the conversation in plain text format
        """
        title = conversation.get("title", "Conversation")
        created = conversation.get("created", "")

        text = f"{title}\n\n"
        text += f"Created: {created}\n\n"

        for message in conversation.get("history", []):
            role = message.get("role", "unknown")
            content = message.get("content", "")

            text += f"{role.capitalize()}: {content}\n\n"

        return text
