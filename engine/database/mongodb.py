"""
MongoDB database adapter for Suhana.

This module provides a MongoDB implementation of the DatabaseAdapter interface.
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import pymongo

from langchain_community.vectorstores import FAISS
try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    # Fallback to deprecated import
    from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

from engine.database.base import DatabaseAdapter


class MongoDBAdapter(DatabaseAdapter):
    """
    MongoDB implementation of the DatabaseAdapter interface.

    This adapter uses MongoDB for storing user profiles, settings, and conversations.
    For vector storage (memory), it uses a hybrid approach with MongoDB for metadata
    and FAISS for vector embeddings.
    """

    def __init__(self, connection_string: str, **kwargs):
        """
        Initialize the MongoDB adapter.

        Args:
            connection_string: MongoDB connection string
            **kwargs: Additional connection parameters
                - database_name: Name of the database to use (default: "suhana")
        """
        self.connection_string = connection_string
        self.database_name = kwargs.get("database_name", "suhana")
        self.client = None
        self.db = None
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        self.logger = logging.getLogger(__name__)

    def connect(self) -> bool:
        """
        Connect to the MongoDB database.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.client = pymongo.MongoClient(self.connection_string)
            self.db = self.client[self.database_name]
            # Ping the server to check if connection is successful
            self.client.admin.command('ping')
            return True
        except Exception as e:
            self.logger.error(f"Error connecting to MongoDB: {e}")
            return False

    def disconnect(self) -> bool:
        """
        Disconnect from the MongoDB database.

        Returns:
            bool: True if disconnection successful, False otherwise
        """
        try:
            if self.client:
                self.client.close()
                self.client = None
                self.db = None
            return True
        except Exception as e:
            self.logger.error(f"Error disconnecting from MongoDB: {e}")
            return False

    def initialize_schema(self) -> bool:
        """
        Initialize the MongoDB database schema.

        Creates all necessary collections and indexes.

        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            if not self.db:
                self.connect()

            # Create collections if they don't exist
            if "users" not in self.db.list_collection_names():
                self.db.create_collection("users")

            if "settings" not in self.db.list_collection_names():
                self.db.create_collection("settings")

            if "categories" not in self.db.list_collection_names():
                self.db.create_collection("categories")

            if "conversations" not in self.db.list_collection_names():
                self.db.create_collection("conversations")

            if "conversation_messages" not in self.db.list_collection_names():
                self.db.create_collection("conversation_messages")

            if "memory_facts" not in self.db.list_collection_names():
                self.db.create_collection("memory_facts")

            if "api_keys" not in self.db.list_collection_names():
                self.db.create_collection("api_keys")

            # Create indexes
            self.db.users.create_index("id", unique=True)
            self.db.users.create_index("username", unique=True)

            self.db.settings.create_index("user_id", unique=True, sparse=True)

            self.db.categories.create_index([("user_id", pymongo.ASCENDING), ("name", pymongo.ASCENDING)], unique=True)

            self.db.conversations.create_index("user_id")
            self.db.conversations.create_index("category_id")
            self.db.conversations.create_index("starred")
            self.db.conversations.create_index("archived")
            self.db.conversations.create_index([("user_id", pymongo.ASCENDING), ("id", pymongo.ASCENDING)], unique=True)

            self.db.conversation_messages.create_index("conversation_id")
            self.db.conversation_messages.create_index([("conversation_id", pymongo.ASCENDING), ("idx", pymongo.ASCENDING)], unique=False)

            self.db.memory_facts.create_index("user_id")
            self.db.memory_facts.create_index("private")

            # API keys indexes
            self.db.api_keys.create_index("key", unique=True)
            self.db.api_keys.create_index("user_id")
            self.db.api_keys.create_index("active")

            return True
        except Exception as e:
            self.logger.error(f"Error initializing MongoDB schema: {e}")
            return False

    def migrate_from_files(self, base_dir: Path) -> Tuple[int, int, int]:
        """
        Migrate data from file-based storage to MongoDB database.

        Args:
            base_dir: Base directory containing file-based storage

        Returns:
            Tuple[int, int, int]: Count of migrated (users, conversations, settings)
        """
        users_migrated = 0
        conversations_migrated = 0
        settings_migrated = 0

        try:
            if not self.db:
                self.connect()

            # Migrate global settings
            global_settings_path = base_dir / "settings.json"
            if global_settings_path.exists():
                with open(global_settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    if self.save_settings(settings):
                        settings_migrated += 1

            # Migrate users
            users_dir = base_dir / "users"
            if users_dir.exists():
                for user_dir in users_dir.iterdir():
                    if user_dir.is_dir():
                        user_id = user_dir.name

                        # Migrate user profile
                        profile_path = user_dir / "profile.json"
                        if profile_path.exists():
                            with open(profile_path, "r", encoding="utf-8") as f:
                                profile = json.load(f)
                                username = profile.get("name", f"user_{user_id}")
                                user_data = {
                                    "id": user_id,
                                    "username": username,
                                    "created_at": datetime.now().isoformat(),
                                    "profile": profile
                                }
                                if self.create_user(user_data) == user_id:
                                    users_migrated += 1

                        # Migrate user settings
                        user_settings_path = user_dir / "settings.json"
                        if user_settings_path.exists():
                            with open(user_settings_path, "r", encoding="utf-8") as f:
                                settings = json.load(f)
                                if self.save_settings(settings, user_id):
                                    settings_migrated += 1

                        # Migrate conversations
                        conversations_dir = user_dir / "conversations"
                        if conversations_dir.exists():
                            # First, create default category
                            self.create_category(user_id, "General")

                            # Migrate conversations
                            for conv_file in conversations_dir.glob("*.json"):
                                if conv_file.is_file() and not conv_file.name.endswith(".meta.json"):
                                    conversation_id = conv_file.stem
                                    with open(conv_file, "r", encoding="utf-8") as f:
                                        conversation = json.load(f)
                                        if self.save_conversation(user_id, conversation_id, conversation):
                                            conversations_migrated += 1

            return users_migrated, conversations_migrated, settings_migrated
        except Exception as e:
            self.logger.error(f"Error migrating from files: {e}")
            return users_migrated, conversations_migrated, settings_migrated

    # User methods

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user profile by ID.

        Args:
            user_id: User ID

        Returns:
            Optional[Dict[str, Any]]: User profile or None if not found
        """
        try:
            if not self.db:
                self.connect()

            user = self.db.users.find_one({"id": user_id})

            if user:
                # Convert ObjectId to string for JSON serialization if present
                try:
                    if user.get("_id") is not None:
                        user["_id"] = str(user["_id"])  # type: ignore[index]
                except Exception:
                    pass
                return user
            return None
        except Exception as e:
            self.logger.error(f"Error getting user: {e}")
            return None

    def list_users(self) -> List[Dict[str, Any]]:
        """
        List all users.

        Returns:
            List[Dict[str, Any]]: List of user profiles
        """
        try:
            if not self.db:
                self.connect()

            users = list(self.db.users.find())

            # Convert ObjectId to string for JSON serialization if present
            for user in users:
                try:
                    if user.get("_id") is not None:
                        user["_id"] = str(user["_id"])  # type: ignore[index]
                except Exception:
                    pass

            return users
        except Exception as e:
            self.logger.error(f"Error listing users: {e}")
            return []

    def create_user(self, user_data: Dict[str, Any]) -> str:
        """
        Create a new user.

        Args:
            user_data: User profile data

        Returns:
            str: ID of the created user
        """
        try:
            if not self.db:
                self.connect()

            user_id = user_data.get("id", str(uuid.uuid4()))
            username = user_data.get("username", f"user_{user_id}")
            password_hash = user_data.get("password_hash")
            created_at = user_data.get("created_at", datetime.now().isoformat())
            last_login = user_data.get("last_login")
            profile = user_data.get("profile", {})

            # Create user document
            user_doc = {
                "id": user_id,
                "username": username,
                "password_hash": password_hash,
                "created_at": created_at,
                "last_login": last_login,
                "profile": profile
            }

            # Insert user document
            result = self.db.users.insert_one(user_doc)

            if result.inserted_id:
                return user_id
            return ""
        except Exception as e:
            self.logger.error(f"Error creating user: {e}")
            return ""

    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> bool:
        """
        Update user profile.

        Args:
            user_id: User ID
            user_data: Updated user profile data

        Returns:
            bool: True if update successful, False otherwise
        """
        try:
            if not self.db:
                self.connect()

            # Build update document
            update_doc = {}

            if "username" in user_data:
                update_doc["username"] = user_data["username"]

            if "password_hash" in user_data:
                update_doc["password_hash"] = user_data["password_hash"]

            if "last_login" in user_data:
                update_doc["last_login"] = user_data["last_login"]

            if "profile" in user_data:
                update_doc["profile"] = user_data["profile"]

            if not update_doc:
                return True  # Nothing to update

            # Update user document
            result = self.db.users.update_one(
                {"id": user_id},
                {"$set": update_doc}
            )

            return result.modified_count > 0 or result.matched_count > 0
        except Exception as e:
            self.logger.error(f"Error updating user: {e}")
            return False

    def delete_user(self, user_id: str) -> bool:
        """
        Delete user.

        Args:
            user_id: User ID

        Returns:
            bool: True if deletion successful, False otherwise
        """
        try:
            if not self.db:
                self.connect()

            # Delete user document
            result = self.db.users.delete_one({"id": user_id})

            # MongoDB will automatically delete related documents due to the cascade delete behavior
            # implemented through application logic

            return result.deleted_count > 0
        except Exception as e:
            self.logger.error(f"Error deleting user: {e}")
            return False

    # Settings methods

    def get_settings(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get settings.

        Args:
            user_id: User ID for user-specific settings, None for global settings

        Returns:
            Dict[str, Any]: Settings
        """
        try:
            if not self.db:
                self.connect()

            query = {"user_id": user_id} if user_id else {"user_id": None}
            settings_doc = self.db.settings.find_one(query)

            if settings_doc:
                return settings_doc["settings"]
            return {}
        except Exception as e:
            self.logger.error(f"Error getting settings: {e}")
            return {}

    def save_settings(self, settings: Dict[str, Any], user_id: Optional[str] = None) -> bool:
        """
        Save settings.

        Args:
            settings: Settings data
            user_id: User ID for user-specific settings, None for global settings

        Returns:
            bool: True if save successful, False otherwise
        """
        try:
            if not self.db:
                self.connect()

            query = {"user_id": user_id} if user_id else {"user_id": None}
            settings_doc = self.db.settings.find_one(query)

            if settings_doc:
                # Update existing settings
                result = self.db.settings.update_one(
                    query,
                    {"$set": {"settings": settings}}
                )
                return result.modified_count > 0 or result.matched_count > 0
            else:
                # Insert new settings
                settings_id = str(uuid.uuid4())
                result = self.db.settings.insert_one({
                    "id": settings_id,
                    "user_id": user_id,
                    "settings": settings
                })
                return result.inserted_id is not None
        except Exception as e:
            self.logger.error(f"Error saving settings: {e}")
            return False

    # Conversation methods

    def list_conversations(self, user_id: str, category: Optional[str] = None) -> List[str]:
        """
        List conversations.

        Args:
            user_id: User ID
            category: Category name (optional)

        Returns:
            List[str]: List of conversation IDs
        """
        try:
            if not self.db:
                self.connect()

            if category:
                # Find category ID first
                category_doc = self.db.categories.find_one({
                    "user_id": user_id,
                    "name": category
                })

                if not category_doc:
                    return []

                category_id = category_doc["id"]

                # Find conversations in this category
                conversations = self.db.conversations.find(
                    {
                        "user_id": user_id,
                        "category_id": category_id
                    },
                    {"id": 1}
                ).sort("updated_at", pymongo.DESCENDING)
            else:
                # Find all conversations for this user
                conversations = self.db.conversations.find(
                    {"user_id": user_id},
                    {"id": 1}
                ).sort("updated_at", pymongo.DESCENDING)

            return [conv["id"] for conv in conversations]
        except Exception as e:
            self.logger.error(f"Error listing conversations: {e}")
            return []

    def list_conversation_meta(self, user_id: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List conversation metadata.

        Args:
            user_id: User ID
            category: Category name (optional)

        Returns:
            List[Dict[str, Any]]: List of conversation metadata
        """
        try:
            if not self.db:
                self.connect()

            pipeline = []

            # Match stage
            if category:
                # Find category ID first
                category_doc = self.db.categories.find_one({
                    "user_id": user_id,
                    "name": category
                })

                if not category_doc:
                    return []

                category_id = category_doc["id"]

                # Match conversations in this category
                pipeline.append({
                    "$match": {
                        "user_id": user_id,
                        "category_id": category_id
                    }
                })
            else:
                # Match all conversations for this user
                pipeline.append({
                    "$match": {
                        "user_id": user_id
                    }
                })

            # Lookup stage to get category name
            pipeline.append({
                "$lookup": {
                    "from": "categories",
                    "localField": "category_id",
                    "foreignField": "id",
                    "as": "category_info"
                }
            })

            # Unwind stage to flatten category info
            pipeline.append({
                "$unwind": {
                    "path": "$category_info",
                    "preserveNullAndEmptyArrays": True
                }
            })

            # Project stage to select fields
            pipeline.append({
                "$project": {
                    "_id": 0,
                    "id": 1,
                    "title": 1,
                    "created_at": 1,
                    "updated_at": 1,
                    "starred": 1,
                    "archived": 1,
                    "tags": 1,
                    "category": "$category_info.name"
                }
            })

            # Sort stage
            pipeline.append({
                "$sort": {
                    "updated_at": -1
                }
            })

            # Execute pipeline
            conversations = list(self.db.conversations.aggregate(pipeline))

            # Ensure category is set to "General" if not found
            for conv in conversations:
                if "category" not in conv or not conv["category"]:
                    conv["category"] = "General"

            return conversations
        except Exception as e:
            self.logger.error(f"Error listing conversation metadata: {e}")
            return []

    def load_conversation(self, user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Load conversation.

        Args:
            user_id: User ID
            conversation_id: Conversation ID

        Returns:
            Optional[Dict[str, Any]]: Conversation data or None if not found
        """
        try:
            if not self.db:
                self.connect()

            # Fetch conversation meta with category name
            conversation = self.db.conversations.find_one({
                "user_id": user_id,
                "id": conversation_id
            })
            if not conversation:
                return None

            category_name = None
            if conversation.get("category_id"):
                cat = self.db.categories.find_one({"id": conversation["category_id"]})
                if cat:
                    category_name = cat.get("name")

            # Try normalized messages first
            msgs = list(self.db.conversation_messages.find({
                "conversation_id": conversation_id
            }).sort("idx", pymongo.ASCENDING))

            history: List[Dict[str, Any]] = []
            if msgs:
                for r in msgs:
                    msg: Dict[str, Any] = {
                        "role": r.get("role"),
                        "content": r.get("content"),
                    }
                    if r.get("created_at"):
                        msg["created_at"] = r.get("created_at")
                    if r.get("meta") is not None:
                        msg["meta"] = r.get("meta")
                    history.append(msg)
            else:
                blob = conversation.get("data")
                if blob:
                    try:
                        legacy = blob if isinstance(blob, dict) else json.loads(blob)
                        history = legacy.get("history") or legacy.get("messages") or []
                    except Exception:
                        history = []

            result: Dict[str, Any] = {
                "history": history,
                "title": conversation.get("title"),
                "category": category_name or "General",
                "starred": bool(conversation.get("starred")),
                "archived": bool(conversation.get("archived")),
                "updated_at": conversation.get("updated_at"),
                "created_at": conversation.get("created_at"),
                "tags": conversation.get("tags") or []
            }
            return result
        except Exception as e:
            self.logger.error(f"Error loading conversation: {e}")
            return None

    def save_conversation(self, user_id: str, conversation_id: str, data: Dict[str, Any]) -> bool:
        """
        Save conversation.

        Args:
            user_id: User ID
            conversation_id: Conversation ID
            data: Conversation data

        Returns:
            bool: True if save successful, False otherwise
        """
        try:
            if not self.db:
                self.connect()

            # Extract metadata from conversation data
            raw_title = data.get("title")
            def _derive_title() -> str:
                placeholders = {"Untitled Conversation", "New Conversation", ""}
                if isinstance(raw_title, str) and raw_title.strip() and raw_title.strip() not in placeholders:
                    return raw_title.strip()
                def first_user_text(msgs):
                    if not isinstance(msgs, list):
                        return None
                    for m in msgs:
                        if isinstance(m, dict) and m.get("role") == "user":
                            content = m.get("content")
                            if isinstance(content, str) and content.strip():
                                return content.strip()
                    return None
                text = first_user_text(data.get("history")) or first_user_text(data.get("messages"))
                if not text:
                    return "Untitled Conversation"
                text = " ".join(text.split())
                max_len = 60
                if len(text) > max_len:
                    return text[:max_len].rstrip() + "..."
                return text
            title = _derive_title()
            category_name = data.get("category", "General")
            starred = data.get("starred", False)
            archived = data.get("archived", False)
            tags = data.get("tags", [])

            # Get current timestamp
            now = datetime.now().isoformat()

            # Get category ID
            category_doc = self.db.categories.find_one({
                "user_id": user_id,
                "name": category_name
            })

            if not category_doc:
                # Create category if it doesn't exist
                self.create_category(user_id, category_name)
                category_doc = self.db.categories.find_one({
                    "user_id": user_id,
                    "name": category_name
                })

            category_id = category_doc["id"] if category_doc else None

            # Check if conversation exists
            existing_conversation = self.db.conversations.find_one({
                "user_id": user_id,
                "id": conversation_id
            })

            if existing_conversation:
                # Update existing conversation
                self.db.conversations.update_one(
                    {
                        "user_id": user_id,
                        "id": conversation_id
                    },
                    {
                        "$set": {
                            "title": title,
                            "category_id": category_id,
                            "updated_at": now,
                            "starred": starred,
                            "archived": archived,
                            "tags": tags,
                            "data": data
                        }
                    }
                )
            else:
                # Insert new conversation
                self.db.conversations.insert_one({
                    "id": conversation_id,
                    "user_id": user_id,
                    "category_id": category_id,
                    "title": title,
                    "created_at": now,
                    "updated_at": now,
                    "starred": starred,
                    "archived": archived,
                    "tags": tags,
                    "data": data
                })

            # Normalize messages into conversation_messages collection
            messages = data.get("history")
            if not isinstance(messages, list):
                messages = data.get("messages")
            if messages is None:
                messages = []
            if not isinstance(messages, list):
                raise ValueError("Conversation history must be a list")

            # Replace strategy: delete existing and bulk insert new
            self.db.conversation_messages.delete_many({"conversation_id": conversation_id})

            bulk = []
            idx_counter = 0
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role")
                content = msg.get("content")
                if role is None or content is None:
                    continue
                created_at = msg.get("created_at") or now
                meta = msg.get("meta")
                bulk.append({
                    "id": str(uuid.uuid4()),
                    "conversation_id": conversation_id,
                    "idx": idx_counter,
                    "role": role,
                    "content": str(content),
                    "created_at": created_at,
                    "meta": meta
                })
                idx_counter += 1
            if bulk:
                self.db.conversation_messages.insert_many(bulk)

            return True
        except Exception as e:
            self.logger.error(f"Error saving conversation: {e}")
            return False

    def create_new_conversation(self, user_id: str, title: Optional[str] = None, category: Optional[str] = None) -> str:
        """
        Create a new conversation.

        Args:
            user_id: User ID
            title: Conversation title (optional)
            category: Category name (optional)

        Returns:
            str: ID of the created conversation
        """
        try:
            if not self.db:
                self.connect()

            conversation_id = str(uuid.uuid4())
            title = title or "New Conversation"
            category = category or "General"
            now = datetime.now().isoformat()

            # Create initial conversation data
            conversation_data = {
                "id": conversation_id,
                "title": title,
                "category": category,
                "created_at": now,
                "updated_at": now,
                "messages": []
            }

            # Save the conversation
            if self.save_conversation(user_id, conversation_id, conversation_data):
                return conversation_id
            return ""
        except Exception as e:
            self.logger.error(f"Error creating new conversation: {e}")
            return ""

    def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """
        Delete conversation.

        Args:
            user_id: User ID
            conversation_id: Conversation ID

        Returns:
            bool: True if deletion successful, False otherwise
        """
        try:
            if not self.db:
                self.connect()

            result = self.db.conversations.delete_one({
                "user_id": user_id,
                "id": conversation_id
            })

            return result.deleted_count > 0
        except Exception as e:
            self.logger.error(f"Error deleting conversation: {e}")
            return False

    def list_categories(self, user_id: str) -> List[str]:
        """
        List categories.

        Args:
            user_id: User ID

        Returns:
            List[str]: List of category names
        """
        try:
            if not self.db:
                self.connect()

            categories = self.db.categories.find(
                {"user_id": user_id},
                {"name": 1}
            ).sort("name", pymongo.ASCENDING)

            return [cat["name"] for cat in categories]
        except Exception as e:
            self.logger.error(f"Error listing categories: {e}")
            return []

    def create_category(self, user_id: str, category: str) -> bool:
        """
        Create a new category.

        Args:
            user_id: User ID
            category: Category name

        Returns:
            bool: True if creation successful, False otherwise
        """
        try:
            if not self.db:
                self.connect()

            # Check if category already exists
            existing_category = self.db.categories.find_one({
                "user_id": user_id,
                "name": category
            })

            if existing_category:
                return True  # Category already exists

            # Create new category
            category_id = str(uuid.uuid4())
            now = datetime.now().isoformat()

            result = self.db.categories.insert_one({
                "id": category_id,
                "user_id": user_id,
                "name": category,
                "created_at": now
            })

            return result.inserted_id is not None
        except Exception as e:
            self.logger.error(f"Error creating category: {e}")
            return False

    def move_conversation_to_category(self, user_id: str, conversation_id: str, category: str) -> bool:
        """
        Move conversation to category.

        Args:
            user_id: User ID
            conversation_id: Conversation ID
            category: Target category name

        Returns:
            bool: True if move successful, False otherwise
        """
        try:
            if not self.db:
                self.connect()

            # Ensure category exists
            category_doc = self.db.categories.find_one({
                "user_id": user_id,
                "name": category
            })

            if not category_doc:
                # Create category if it doesn't exist
                self.create_category(user_id, category)
                category_doc = self.db.categories.find_one({
                    "user_id": user_id,
                    "name": category
                })

            category_id = category_doc["id"]
            now = datetime.now().isoformat()

            # Update conversation
            result = self.db.conversations.update_one(
                {
                    "user_id": user_id,
                    "id": conversation_id
                },
                {
                    "$set": {
                        "category_id": category_id,
                        "updated_at": now
                    }
                }
            )

            return result.modified_count > 0 or result.matched_count > 0
        except Exception as e:
            self.logger.error(f"Error moving conversation to category: {e}")
            return False

    # Memory methods

    def add_memory_fact(self, user_id: Optional[str], text: str, private: bool = True) -> bool:
        """
        Add memory fact.

        Args:
            user_id: User ID (None for shared memory)
            text: Memory fact text
            private: Whether the memory is private to the user

        Returns:
            bool: True if addition successful, False otherwise
        """
        try:
            if not self.db:
                self.connect()

            # Create a unique ID for the memory fact
            fact_id = str(uuid.uuid4())
            now = datetime.now().isoformat()

            # Create embedding file path
            embedding_dir = Path("vectorstore")
            embedding_dir.mkdir(exist_ok=True)

            if user_id:
                user_embedding_dir = embedding_dir / user_id
                user_embedding_dir.mkdir(exist_ok=True)
                embedding_file = str(user_embedding_dir / f"{fact_id}.faiss")
            else:
                shared_embedding_dir = embedding_dir / "shared"
                shared_embedding_dir.mkdir(exist_ok=True)
                embedding_file = str(shared_embedding_dir / f"{fact_id}.faiss")

            # Store the text in the database
            result = self.db.memory_facts.insert_one({
                "id": fact_id,
                "user_id": user_id,
                "text": text,
                "private": private,
                "created_at": now,
                "embedding_file": embedding_file
            })

            if not result.inserted_id:
                return False

            # Create and save the embedding
            documents = [Document(page_content=text, metadata={"id": fact_id})]
            vector_store = FAISS.from_documents(documents, self.embeddings)
            vector_store.save_local(embedding_file)

            return True
        except Exception as e:
            self.logger.error(f"Error adding memory fact: {e}")
            return False

    def search_memory(self, query: str, user_id: Optional[str] = None, include_shared: bool = True, k: int = 3) -> List[Dict[str, Any]]:
        """
        Search memory.

        Args:
            query: Search query
            user_id: User ID (None for shared memory only)
            include_shared: Whether to include shared memory in search
            k: Number of results to return

        Returns:
            List[Dict[str, Any]]: List of memory facts
        """
        try:
            if not self.db:
                self.connect()

            # Get all relevant memory facts
            if user_id and include_shared:
                memory_facts = list(self.db.memory_facts.find({
                    "$or": [
                        {"user_id": user_id},
                        {"user_id": None, "private": False}
                    ]
                }))
            elif user_id:
                memory_facts = list(self.db.memory_facts.find({
                    "user_id": user_id
                }))
            else:
                memory_facts = list(self.db.memory_facts.find({
                    "user_id": None,
                    "private": False
                }))

            if not memory_facts:
                return []

            # Load all vector stores and search
            results = []
            for fact in memory_facts:
                embedding_file = fact["embedding_file"]
                if embedding_file and Path(embedding_file).exists():
                    try:
                        vector_store = FAISS.load_local(embedding_file, self.embeddings)
                        vector_results = vector_store.similarity_search_with_score(query, k=1)

                        if vector_results:
                            doc, score = vector_results[0]
                            results.append({
                                "id": fact["id"],
                                "text": fact["text"],
                                "user_id": fact["user_id"],
                                "private": fact["private"],
                                "created_at": fact["created_at"],
                                "score": float(score)
                            })
                    except Exception as e:
                        self.logger.error(f"Error searching vector store {embedding_file}: {e}")

            # Sort by score (lower is better) and take top k
            results.sort(key=lambda x: x["score"])
            return results[:k]
        except Exception as e:
            self.logger.error(f"Error searching memory: {e}")
            return []

    def forget_memory(self, keyword: str, user_id: Optional[str] = None, forget_shared: bool = False) -> int:
        """
        Forget memory facts containing keyword.

        Args:
            keyword: Keyword to search for
            user_id: User ID (None for shared memory only)
            forget_shared: Whether to forget shared memory

        Returns:
            int: Number of memory facts forgotten
        """
        try:
            if not self.db:
                self.connect()

            # Find memory facts containing the keyword
            query = {}
            if user_id and forget_shared:
                query = {
                    "$or": [
                        {"user_id": user_id},
                        {"user_id": None, "private": False}
                    ],
                    "text": {"$regex": keyword, "$options": "i"}
                }
            elif user_id:
                query = {
                    "user_id": user_id,
                    "text": {"$regex": keyword, "$options": "i"}
                }
            else:
                query = {
                    "user_id": None,
                    "private": False,
                    "text": {"$regex": keyword, "$options": "i"}
                }

            memory_facts = list(self.db.memory_facts.find(query))

            if not memory_facts:
                return 0

            # Delete the memory facts and their embeddings
            count = 0
            for fact in memory_facts:
                # Delete the embedding file
                embedding_file = fact["embedding_file"]
                if embedding_file and Path(embedding_file).exists():
                    try:
                        Path(embedding_file).unlink()
                    except Exception as e:
                        self.logger.error(f"Error deleting embedding file {embedding_file}: {e}")

                # Delete from database
                result = self.db.memory_facts.delete_one({"id": fact["id"]})
                if result.deleted_count > 0:
                    count += 1

            return count
        except Exception as e:
            self.logger.error(f"Error forgetting memory: {e}")
            return 0

    def clear_memory(self, user_id: Optional[str] = None, clear_shared: bool = False) -> int:
        """
        Clear memory.

        Args:
            user_id: User ID (None for shared memory only)
            clear_shared: Whether to clear shared memory

        Returns:
            int: Number of memory facts cleared
        """
        try:
            if not self.db:
                self.connect()

            # Find memory facts to clear
            query = {}
            if user_id and clear_shared:
                query = {
                    "$or": [
                        {"user_id": user_id},
                        {"user_id": None, "private": False}
                    ]
                }
            elif user_id:
                query = {"user_id": user_id}
            else:
                query = {"user_id": None, "private": False}

            memory_facts = list(self.db.memory_facts.find(query))

            if not memory_facts:
                return 0

            # Delete the memory facts and their embeddings
            count = 0
            for fact in memory_facts:
                # Delete the embedding file
                embedding_file = fact["embedding_file"]
                if embedding_file and Path(embedding_file).exists():
                    try:
                        Path(embedding_file).unlink()
                    except Exception as e:
                        self.logger.error(f"Error deleting embedding file {embedding_file}: {e}")

                # Delete from database
                result = self.db.memory_facts.delete_one({"id": fact["id"]})
                if result.deleted_count > 0:
                    count += 1

            return count
        except Exception as e:
            self.logger.error(f"Error clearing memory: {e}")
            return 0

    # API Key Management Methods

    def get_api_key(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get API key information.

        Args:
            key: API key

        Returns:
            Dict containing API key information or None if not found
        """
        try:
            if not self.db:
                self.connect()

            doc = self.db.api_keys.find_one({"key": key})
            if not doc:
                return None
            # Ensure types align with SQLite
            if doc.get("permissions") is None:
                doc["permissions"] = []
            doc["active"] = bool(doc.get("active", True))
            return doc
        except Exception as e:
            self.logger.error(f"Error getting API key: {e}")
            return None

    def get_user_api_keys(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all API keys for a user.
        """
        try:
            if not self.db:
                self.connect()
            keys = list(self.db.api_keys.find({"user_id": user_id}))
            for k in keys:
                if k.get("permissions") is None:
                    k["permissions"] = []
                k["active"] = bool(k.get("active", True))
            return keys
        except Exception as e:
            self.logger.error(f"Error getting user API keys: {e}")
            return []

    def create_api_key(self, user_id: str, key: str, name: Optional[str] = None,
                       rate_limit: int = 60, permissions: Optional[List[str]] = None) -> bool:
        """
        Create a new API key.
        """
        try:
            if not self.db:
                self.connect()
            if permissions is None:
                permissions = ["user"]
            now = datetime.now().isoformat()
            doc = {
                "key": key,
                "user_id": user_id,
                "name": name,
                "created_at": now,
                "last_used": None,
                "usage_count": 0,
                "rate_limit": rate_limit,
                "permissions": permissions,
                "active": True,
            }
            res = self.db.api_keys.insert_one(doc)
            return res.inserted_id is not None
        except Exception as e:
            self.logger.error(f"Error creating API key: {e}")
            return False

    def update_api_key_usage(self, key: str) -> bool:
        """
        Update API key usage statistics.
        """
        try:
            if not self.db:
                self.connect()
            now = datetime.now().isoformat()
            res = self.db.api_keys.update_one(
                {"key": key},
                {"$set": {"last_used": now}, "$inc": {"usage_count": 1}}
            )
            return res.matched_count > 0
        except Exception as e:
            self.logger.error(f"Error updating API key usage: {e}")
            return False

    def revoke_api_key(self, key: str) -> bool:
        """
        Revoke an API key.
        """
        try:
            if not self.db:
                self.connect()
            res = self.db.api_keys.update_one({"key": key}, {"$set": {"active": False}})
            return res.matched_count > 0
        except Exception as e:
            self.logger.error(f"Error revoking API key: {e}")
            return False

    def get_api_key_usage_stats(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get API key usage statistics.
        """
        try:
            if not self.db:
                self.connect()
            query = {"user_id": user_id} if user_id else {}
            keys = list(self.db.api_keys.find(query))
            # Enrich with username similar to SQLite which joins users
            user_cache = {}
            for k in keys:
                uid = k.get("user_id")
                username = None
                if uid:
                    if uid in user_cache:
                        username = user_cache[uid]
                    else:
                        u = self.db.users.find_one({"id": uid})
                        username = u.get("username") if u else None
                        user_cache[uid] = username
                k["username"] = username
                if k.get("permissions") is None:
                    k["permissions"] = []
                k["active"] = bool(k.get("active", True))
            return keys
        except Exception as e:
            self.logger.error(f"Error getting API key usage stats: {e}")
            return []
