"""
SQLite database adapter for Suhana.

This module provides a SQLite implementation of the DatabaseAdapter interface.
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from langchain_community.vectorstores import FAISS
try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    # Fallback to deprecated import
    from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

from engine.database.base import DatabaseAdapter


class SQLiteAdapter(DatabaseAdapter):
    """
    SQLite implementation of the DatabaseAdapter interface.

    This adapter uses SQLite for storing user profiles, settings, and conversations.
    For vector storage (memory), it uses a hybrid approach with SQLite for metadata
    and FAISS for vector embeddings.
    """

    def __init__(self, connection_string: str, **kwargs):
        """
        Initialize the SQLite adapter.

        Args:
            connection_string: Path to the SQLite database file
            **kwargs: Additional connection parameters
        """
        self.db_path = connection_string
        self.connection = None
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        self.logger = logging.getLogger(__name__)

        # Apply access controls to enforce permissions
        self.apply_access_controls()

    def connect(self) -> bool:
        """
        Connect to the SQLite database.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            # Enable foreign keys
            self.connection.execute("PRAGMA foreign_keys = ON")
            # Use Row factory for better column access
            self.connection.row_factory = sqlite3.Row
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Error connecting to SQLite database: {e}")
            return False

    def disconnect(self) -> bool:
        """
        Disconnect from the SQLite database.

        Returns:
            bool: True if disconnection successful, False otherwise
        """
        try:
            if self.connection:
                self.connection.close()
                self.connection = None
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Error disconnecting from SQLite database: {e}")
            return False

    def initialize_schema(self) -> bool:
        """
        Initialize the SQLite database schema.

        Creates all necessary tables, indexes, and constraints.

        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()

            # Create users table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT,
                created_at TEXT NOT NULL,
                last_login TEXT,
                profile TEXT NOT NULL
            )
            ''')

            # Create settings table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                settings TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            ''')

            # Create categories table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE (user_id, name)
            )
            ''')

            # Create conversations table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                category_id TEXT,
                title TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                starred INTEGER DEFAULT 0,
                archived INTEGER DEFAULT 0,
                tags TEXT,
                data TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
            )
            ''')

            # Create memory_facts table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS memory_facts (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                text TEXT NOT NULL,
                private INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                embedding_file TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            ''')

            # Create api_keys table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                key TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT,
                created_at TEXT NOT NULL,
                last_used TEXT,
                usage_count INTEGER DEFAULT 0,
                rate_limit INTEGER DEFAULT 60,
                permissions TEXT,
                active INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            ''')

            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_settings_user_id ON settings(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_categories_user_id ON categories(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversations_category_id ON conversations(category_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversations_starred ON conversations(starred)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversations_archived ON conversations(archived)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_memory_facts_user_id ON memory_facts(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_memory_facts_private ON memory_facts(private)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(active)')

            self.connection.commit()
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Error initializing SQLite schema: {e}")
            self.connection.rollback()
            return False

    def migrate_from_files(self, base_dir: Path) -> Tuple[int, int, int]:
        """
        Migrate data from file-based storage to SQLite database.

        Args:
            base_dir: Base directory containing file-based storage

        Returns:
            Tuple[int, int, int]: Count of migrated (users, conversations, settings)
        """
        users_migrated = 0
        conversations_migrated = 0
        settings_migrated = 0

        try:
            if not self.connection:
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
                                    "profile": json.dumps(profile)
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
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,)
            )
            row = cursor.fetchone()

            if row:
                user = dict(row)
                user["profile"] = json.loads(user["profile"])
                return user
            return None
        except sqlite3.Error as e:
            self.logger.error(f"Error getting user: {e}")
            return None

    def list_users(self) -> List[Dict[str, Any]]:
        """
        List all users.

        Returns:
            List[Dict[str, Any]]: List of user profiles
        """
        try:
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()
            cursor.execute("SELECT * FROM users")
            rows = cursor.fetchall()

            users = []
            for row in rows:
                user = dict(row)
                user["profile"] = json.loads(user["profile"])
                users.append(user)

            return users
        except sqlite3.Error as e:
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
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()

            user_id = user_data.get("id", str(uuid.uuid4()))
            username = user_data.get("username", f"user_{user_id}")
            password_hash = user_data.get("password_hash")
            created_at = user_data.get("created_at", datetime.now().isoformat())
            last_login = user_data.get("last_login")

            # Handle profile data
            if "profile" in user_data and isinstance(user_data["profile"], str):
                profile = user_data["profile"]  # Already JSON string
            else:
                profile = json.dumps(user_data.get("profile", {}))

            cursor.execute(
                """
                INSERT INTO users (id, username, password_hash, created_at, last_login, profile)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, username, password_hash, created_at, last_login, profile)
            )

            self.connection.commit()
            return user_id
        except sqlite3.Error as e:
            self.logger.error(f"Error creating user: {e}")
            self.connection.rollback()
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
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()

            # Get current user data
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()

            if not row:
                return False

            # Update fields
            updates = []
            params = []

            if "username" in user_data:
                updates.append("username = ?")
                params.append(user_data["username"])

            if "password_hash" in user_data:
                updates.append("password_hash = ?")
                params.append(user_data["password_hash"])

            if "last_login" in user_data:
                updates.append("last_login = ?")
                params.append(user_data["last_login"])

            if "profile" in user_data:
                updates.append("profile = ?")
                if isinstance(user_data["profile"], str):
                    params.append(user_data["profile"])
                else:
                    params.append(json.dumps(user_data["profile"]))

            if not updates:
                return True  # Nothing to update

            # Build and execute update query
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            params.append(user_id)

            cursor.execute(query, params)
            self.connection.commit()

            return cursor.rowcount > 0
        except sqlite3.Error as e:
            self.logger.error(f"Error updating user: {e}")
            self.connection.rollback()
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
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            self.connection.commit()

            return cursor.rowcount > 0
        except sqlite3.Error as e:
            self.logger.error(f"Error deleting user: {e}")
            self.connection.rollback()
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
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()

            if user_id:
                cursor.execute(
                    "SELECT settings FROM settings WHERE user_id = ?",
                    (user_id,)
                )
            else:
                cursor.execute(
                    "SELECT settings FROM settings WHERE user_id IS NULL"
                )

            row = cursor.fetchone()

            if row:
                return json.loads(row["settings"])
            return {}
        except sqlite3.Error as e:
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
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()
            settings_id = str(uuid.uuid4())
            settings_json = json.dumps(settings)

            # Check if settings already exist
            if user_id:
                cursor.execute(
                    "SELECT id FROM settings WHERE user_id = ?",
                    (user_id,)
                )
            else:
                cursor.execute(
                    "SELECT id FROM settings WHERE user_id IS NULL"
                )

            row = cursor.fetchone()

            if row:
                # Update existing settings
                if user_id:
                    cursor.execute(
                        "UPDATE settings SET settings = ? WHERE user_id = ?",
                        (settings_json, user_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE settings SET settings = ? WHERE user_id IS NULL",
                        (settings_json,)
                    )
            else:
                # Insert new settings
                cursor.execute(
                    "INSERT INTO settings (id, user_id, settings) VALUES (?, ?, ?)",
                    (settings_id, user_id, settings_json)
                )

            self.connection.commit()
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Error saving settings: {e}")
            self.connection.rollback()
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
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()

            if category:
                cursor.execute(
                    """
                    SELECT c.id FROM conversations c
                    JOIN categories cat ON c.category_id = cat.id
                    WHERE c.user_id = ? AND cat.name = ?
                    ORDER BY c.updated_at DESC
                    """,
                    (user_id, category)
                )
            else:
                cursor.execute(
                    """
                    SELECT id FROM conversations
                    WHERE user_id = ?
                    ORDER BY updated_at DESC
                    """,
                    (user_id,)
                )

            rows = cursor.fetchall()
            return [row["id"] for row in rows]
        except sqlite3.Error as e:
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
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()

            if category:
                cursor.execute(
                    """
                    SELECT c.id, c.title, c.created_at, c.updated_at, c.starred, c.archived, c.tags,
                           cat.name as category
                    FROM conversations c
                    LEFT JOIN categories cat ON c.category_id = cat.id
                    WHERE c.user_id = ? AND cat.name = ?
                    ORDER BY c.updated_at DESC
                    """,
                    (user_id, category)
                )
            else:
                cursor.execute(
                    """
                    SELECT c.id, c.title, c.created_at, c.updated_at, c.starred, c.archived, c.tags,
                           cat.name as category
                    FROM conversations c
                    LEFT JOIN categories cat ON c.category_id = cat.id
                    WHERE c.user_id = ?
                    ORDER BY c.updated_at DESC
                    """,
                    (user_id,)
                )

            rows = cursor.fetchall()

            result = []
            for row in rows:
                meta = dict(row)
                if meta["tags"]:
                    meta["tags"] = json.loads(meta["tags"])
                else:
                    meta["tags"] = []
                result.append(meta)

            return result
        except sqlite3.Error as e:
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
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()
            cursor.execute(
                """
                SELECT data FROM conversations
                WHERE user_id = ? AND id = ?
                """,
                (user_id, conversation_id)
            )

            row = cursor.fetchone()

            if row:
                return json.loads(row["data"])
            return None
        except sqlite3.Error as e:
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
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()

            # Extract metadata from conversation data
            title = data.get("title", "Untitled Conversation")
            category_name = data.get("category", "General")
            starred = data.get("starred", False)
            archived = data.get("archived", False)
            tags = data.get("tags", [])

            # Get current timestamp
            now = datetime.now().isoformat()

            # Get category ID
            cursor.execute(
                "SELECT id FROM categories WHERE user_id = ? AND name = ?",
                (user_id, category_name)
            )
            category_row = cursor.fetchone()

            if not category_row:
                # Create category if it doesn't exist
                self.create_category(user_id, category_name)
                cursor.execute(
                    "SELECT id FROM categories WHERE user_id = ? AND name = ?",
                    (user_id, category_name)
                )
                category_row = cursor.fetchone()

            category_id = category_row["id"] if category_row else None

            # Check if conversation exists
            cursor.execute(
                "SELECT id FROM conversations WHERE user_id = ? AND id = ?",
                (user_id, conversation_id)
            )

            row = cursor.fetchone()

            if row:
                # Update existing conversation
                cursor.execute(
                    """
                    UPDATE conversations
                    SET title = ?, category_id = ?, updated_at = ?, starred = ?, archived = ?, tags = ?, data = ?
                    WHERE user_id = ? AND id = ?
                    """,
                    (
                        title, category_id, now, 1 if starred else 0, 1 if archived else 0,
                        json.dumps(tags), json.dumps(data), user_id, conversation_id
                    )
                )
            else:
                # Insert new conversation
                cursor.execute(
                    """
                    INSERT INTO conversations
                    (id, user_id, category_id, title, created_at, updated_at, starred, archived, tags, data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        conversation_id, user_id, category_id, title, now, now,
                        1 if starred else 0, 1 if archived else 0, json.dumps(tags), json.dumps(data)
                    )
                )

            self.connection.commit()
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Error saving conversation: {e}")
            self.connection.rollback()
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
            if not self.connection:
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
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()
            cursor.execute(
                "DELETE FROM conversations WHERE user_id = ? AND id = ?",
                (user_id, conversation_id)
            )

            self.connection.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            self.logger.error(f"Error deleting conversation: {e}")
            self.connection.rollback()
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
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT name FROM categories WHERE user_id = ? ORDER BY name",
                (user_id,)
            )

            rows = cursor.fetchall()
            return [row["name"] for row in rows]
        except sqlite3.Error as e:
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
            if not self.connection:
                self.connect()

            # Check if category already exists
            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT id FROM categories WHERE user_id = ? AND name = ?",
                (user_id, category)
            )

            if cursor.fetchone():
                return True  # Category already exists

            # Create new category
            category_id = str(uuid.uuid4())
            now = datetime.now().isoformat()

            cursor.execute(
                "INSERT INTO categories (id, user_id, name, created_at) VALUES (?, ?, ?, ?)",
                (category_id, user_id, category, now)
            )

            self.connection.commit()
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Error creating category: {e}")
            self.connection.rollback()
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
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()

            # Ensure category exists
            cursor.execute(
                "SELECT id FROM categories WHERE user_id = ? AND name = ?",
                (user_id, category)
            )

            category_row = cursor.fetchone()
            if not category_row:
                # Create category if it doesn't exist
                self.create_category(user_id, category)
                cursor.execute(
                    "SELECT id FROM categories WHERE user_id = ? AND name = ?",
                    (user_id, category)
                )
                category_row = cursor.fetchone()

            category_id = category_row["id"]

            # Update conversation
            cursor.execute(
                """
                UPDATE conversations
                SET category_id = ?, updated_at = ?
                WHERE user_id = ? AND id = ?
                """,
                (category_id, datetime.now().isoformat(), user_id, conversation_id)
            )

            self.connection.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            self.logger.error(f"Error moving conversation to category: {e}")
            self.connection.rollback()
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
            if not self.connection:
                self.connect()

            # Create a unique ID for the memory fact
            fact_id = str(uuid.uuid4())
            now = datetime.now().isoformat()

            # Create embedding file path
            embedding_dir = Path(self.db_path).parent / "vectorstore"
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
            cursor = self.connection.cursor()
            cursor.execute(
                """
                INSERT INTO memory_facts (id, user_id, text, private, created_at, embedding_file)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (fact_id, user_id, text, 1 if private else 0, now, embedding_file)
            )

            # Create and save the embedding
            documents = [Document(page_content=text, metadata={"id": fact_id})]
            vector_store = FAISS.from_documents(documents, self.embeddings)
            vector_store.save_local(embedding_file)

            self.connection.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error adding memory fact: {e}")
            self.connection.rollback()
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
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()

            # Get all relevant memory facts
            if user_id and include_shared:
                cursor.execute(
                    """
                    SELECT * FROM memory_facts
                    WHERE (user_id = ? OR (user_id IS NULL AND private = 0))
                    """,
                    (user_id,)
                )
            elif user_id:
                cursor.execute(
                    "SELECT * FROM memory_facts WHERE user_id = ?",
                    (user_id,)
                )
            else:
                cursor.execute(
                    "SELECT * FROM memory_facts WHERE user_id IS NULL AND private = 0"
                )

            rows = cursor.fetchall()

            if not rows:
                return []

            # Load all vector stores and search
            results = []
            for row in rows:
                embedding_file = row["embedding_file"]
                if embedding_file and Path(embedding_file).exists():
                    try:
                        vector_store = FAISS.load_local(embedding_file, self.embeddings)
                        vector_results = vector_store.similarity_search_with_score(query, k=1)

                        if vector_results:
                            doc, score = vector_results[0]
                            results.append({
                                "id": row["id"],
                                "text": row["text"],
                                "user_id": row["user_id"],
                                "private": bool(row["private"]),
                                "created_at": row["created_at"],
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
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()

            # Find memory facts containing the keyword
            if user_id and forget_shared:
                cursor.execute(
                    """
                    SELECT * FROM memory_facts
                    WHERE (user_id = ? OR (user_id IS NULL AND private = 0))
                    AND text LIKE ?
                    """,
                    (user_id, f"%{keyword}%")
                )
            elif user_id:
                cursor.execute(
                    """
                    SELECT * FROM memory_facts
                    WHERE user_id = ? AND text LIKE ?
                    """,
                    (user_id, f"%{keyword}%")
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM memory_facts
                    WHERE user_id IS NULL AND private = 0 AND text LIKE ?
                    """,
                    (f"%{keyword}%",)
                )

            rows = cursor.fetchall()

            if not rows:
                return 0

            # Delete the memory facts and their embeddings
            count = 0
            for row in rows:
                # Delete the embedding file
                embedding_file = row["embedding_file"]
                if embedding_file and Path(embedding_file).exists():
                    try:
                        Path(embedding_file).unlink()
                    except Exception as e:
                        self.logger.error(f"Error deleting embedding file {embedding_file}: {e}")

                # Delete from database
                cursor.execute(
                    "DELETE FROM memory_facts WHERE id = ?",
                    (row["id"],)
                )
                count += 1

            self.connection.commit()
            return count
        except Exception as e:
            self.logger.error(f"Error forgetting memory: {e}")
            self.connection.rollback()
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
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()

            # Find memory facts to clear
            if user_id and clear_shared:
                cursor.execute(
                    """
                    SELECT * FROM memory_facts
                    WHERE user_id = ? OR (user_id IS NULL AND private = 0)
                    """,
                    (user_id,)
                )
            elif user_id:
                cursor.execute(
                    "SELECT * FROM memory_facts WHERE user_id = ?",
                    (user_id,)
                )
            else:
                cursor.execute(
                    "SELECT * FROM memory_facts WHERE user_id IS NULL AND private = 0"
                )

            rows = cursor.fetchall()

            if not rows:
                return 0

            # Delete the memory facts and their embeddings
            count = 0
            for row in rows:
                # Delete the embedding file
                embedding_file = row["embedding_file"]
                if embedding_file and Path(embedding_file).exists():
                    try:
                        Path(embedding_file).unlink()
                    except Exception as e:
                        self.logger.error(f"Error deleting embedding file {embedding_file}: {e}")

                # Delete from database
                cursor.execute(
                    "DELETE FROM memory_facts WHERE id = ?",
                    (row["id"],)
                )
                count += 1

            self.connection.commit()
            return count
        except Exception as e:
            self.logger.error(f"Error clearing memory: {e}")
            self.connection.rollback()
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
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT * FROM api_keys WHERE key = ?",
                (key,)
            )

            row = cursor.fetchone()

            if not row:
                return None

            # Convert row to dictionary
            columns = [column[0] for column in cursor.description]
            result = {columns[i]: row[i] for i in range(len(columns))}

            # Convert permissions from JSON string to Python list
            if result["permissions"] is not None:
                result["permissions"] = json.loads(result["permissions"])

            # Convert boolean fields
            result["active"] = bool(result["active"])

            return result
        except Exception as e:
            self.logger.error(f"Error getting API key: {e}")
            return None

    def get_user_api_keys(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all API keys for a user.

        Args:
            user_id: User ID

        Returns:
            List of dictionaries containing API key information
        """
        try:
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT * FROM api_keys WHERE user_id = ?",
                (user_id,)
            )

            rows = cursor.fetchall()

            # Convert rows to dictionaries
            columns = [column[0] for column in cursor.description]
            result = []

            for row in rows:
                item = {columns[i]: row[i] for i in range(len(columns))}

                # Convert permissions from JSON string to Python list
                if item["permissions"] is not None:
                    item["permissions"] = json.loads(item["permissions"])

                # Convert boolean fields
                item["active"] = bool(item["active"])

                result.append(item)

            return result
        except Exception as e:
            self.logger.error(f"Error getting user API keys: {e}")
            return []

    def create_api_key(self, user_id: str, key: str, name: Optional[str] = None,
                      rate_limit: int = 60, permissions: Optional[List[str]] = None) -> bool:
        """
        Create a new API key.

        Args:
            user_id: User ID
            key: API key
            name: Name for the API key
            rate_limit: Rate limit in requests per minute
            permissions: List of permissions

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()

            # Set default permissions if none provided
            if permissions is None:
                permissions = ["user"]

            # Convert permissions list to JSON string
            permissions_json = json.dumps(permissions)

            cursor.execute(
                """
                INSERT INTO api_keys (key, user_id, name, created_at, rate_limit, permissions, active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (key, user_id, name, datetime.now().isoformat(), rate_limit, permissions_json, 1)
            )

            self.connection.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error creating API key: {e}")
            self.connection.rollback()
            return False

    def update_api_key_usage(self, key: str) -> bool:
        """
        Update API key usage statistics.

        Args:
            key: API key

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()

            cursor.execute(
                """
                UPDATE api_keys
                SET usage_count = usage_count + 1, last_used = ?
                WHERE key = ?
                """,
                (datetime.now().isoformat(), key)
            )

            self.connection.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error updating API key usage: {e}")
            self.connection.rollback()
            return False

    def revoke_api_key(self, key: str) -> bool:
        """
        Revoke an API key.

        Args:
            key: API key

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()

            cursor.execute(
                "UPDATE api_keys SET active = 0 WHERE key = ?",
                (key,)
            )

            self.connection.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error revoking API key: {e}")
            self.connection.rollback()
            return False

    def get_api_key_usage_stats(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get API key usage statistics.

        Args:
            user_id: User ID (if None, gets stats for all users)

        Returns:
            List of dictionaries containing API key usage statistics
        """
        try:
            if not self.connection:
                self.connect()

            cursor = self.connection.cursor()

            if user_id:
                cursor.execute(
                    """
                    SELECT k.key, k.name, k.user_id, k.created_at, k.last_used,
                           k.usage_count, k.rate_limit, k.permissions, k.active,
                           u.username
                    FROM api_keys k
                    JOIN users u ON k.user_id = u.id
                    WHERE k.user_id = ?
                    """,
                    (user_id,)
                )
            else:
                cursor.execute(
                    """
                    SELECT k.key, k.name, k.user_id, k.created_at, k.last_used,
                           k.usage_count, k.rate_limit, k.permissions, k.active,
                           u.username
                    FROM api_keys k
                    JOIN users u ON k.user_id = u.id
                    """
                )

            rows = cursor.fetchall()

            # Convert rows to dictionaries
            columns = [column[0] for column in cursor.description]
            result = []

            for row in rows:
                item = {columns[i]: row[i] for i in range(len(columns))}

                # Convert permissions from JSON string to Python list
                if item["permissions"] is not None:
                    item["permissions"] = json.loads(item["permissions"])

                # Convert boolean fields
                item["active"] = bool(item["active"])

                result.append(item)

            return result
        except Exception as e:
            self.logger.error(f"Error getting API key usage stats: {e}")
            return []
