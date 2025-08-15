import json
import os
import secrets
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

from engine.database.base import DatabaseAdapter

# Default rate limits (requests per minute)
DEFAULT_RATE_LIMIT = 60
ADMIN_RATE_LIMIT = 120

class ApiKeyManager:
    """
    Manages API keys for users, including creation, validation, and rate limiting.
    """

    def __init__(self, db_adapter: Optional[DatabaseAdapter] = None):
        """
        Initialize the API key manager.

        Args:
            db_adapter: Database adapter to use for storage
        """
        from engine.engine_config import get_database_adapter

        # Get database adapter if not provided
        self.db = db_adapter or get_database_adapter()

        # Ensure database is initialized
        self.db.initialize_schema()

        # Ensure default API key exists
        self._ensure_default_key()

        # Track API usage: {key: [(timestamp, endpoint), ...]}
        self.usage_tracking: Dict[str, List[Tuple[float, str]]] = {}

    def _get_default_key(self) -> str:
        """Generate or retrieve the default API key."""
        return os.getenv("SUHANA_DEFAULT_API_KEY") or secrets.token_urlsafe(32)

    def _ensure_default_key(self) -> None:
        """Ensure the default API key exists, creating it if necessary."""
        # Check if we have any API keys for the dev user
        dev_keys = self.db.get_user_api_keys("dev")

        if not dev_keys:
            # Create default key
            default_key = self._get_default_key()
            print("🔐 Creating default API key...")

            # Create dev user if it doesn't exist
            user = self.db.get_user("dev")
            if not user:
                self.db.create_user({
                    "id": "dev",
                    "username": "developer",
                    "password_hash": None,
                    "created_at": datetime.now().replace(tzinfo=None).isoformat(),
                    "profile": {}
                })

            # Create the API key
            self.db.create_api_key(
                user_id="dev",
                key=default_key,
                name="Default Developer Key",
                rate_limit=ADMIN_RATE_LIMIT,
                permissions=["admin"]
            )

    def get_valid_api_keys(self, user_id: str = "dev") -> Set[str]:
        """
        Get all valid API keys.

        Args:
            user_id: User ID to use for permission checks (default: "dev")

        Returns:
            Set[str]: Set of valid API key strings
        """
        # Get all API keys from all users
        all_users = self.db.list_users(user_id)
        all_keys = set()

        for user in all_users:
            user_keys = self.db.get_user_api_keys(user["id"])
            for key_info in user_keys:
                if key_info.get("active"):
                    all_keys.add(key_info["key"])

        return all_keys

    def create_api_key(self, user_id: str, name: str = None, rate_limit: int = DEFAULT_RATE_LIMIT,
                      permissions: List[str] = None) -> str:
        """
        Create a new API key for a user.

        Args:
            user_id: ID of the user
            name: Name/description of the API key
            rate_limit: Rate limit in requests per minute
            permissions: List of permission strings

        Returns:
            str: The newly created API key
        """
        # Generate a new API key
        new_key = secrets.token_urlsafe(32)

        # Set default permissions if none provided
        if permissions is None:
            permissions = ["user"]

        # Create the API key in the database
        success = self.db.create_api_key(
            user_id=user_id,
            key=new_key,
            name=name or f"API Key for {user_id}",
            rate_limit=rate_limit,
            permissions=permissions
        )

        if not success:
            return ""

        return new_key

    def revoke_api_key(self, key: str) -> bool:
        """
        Revoke (deactivate) an API key.

        Args:
            key: The API key to revoke

        Returns:
            bool: True if successful, False otherwise
        """
        return self.db.revoke_api_key(key)

    def get_key_info(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get information about an API key.

        Args:
            key: The API key

        Returns:
            Optional[Dict[str, Any]]: Key information or None if not found
        """
        return self.db.get_api_key(key)

    def validate_key(self, key: str, endpoint: str = None) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate an API key and check rate limits.

        Args:
            key: The API key to validate
            endpoint: The endpoint being accessed (for tracking)

        Returns:
            Tuple[bool, Optional[str], Optional[str]]:
                (is_valid, user_id, error_message)
        """
        # Get key info from database
        key_info = self.db.get_api_key(key)

        if not key_info or not key_info.get("active"):
            return False, None, "Invalid or inactive API key"

        # Check rate limits
        if endpoint:
            # Initialize usage tracking for this key if not exists
            if key not in self.usage_tracking:
                self.usage_tracking[key] = []

            # Add current request to usage tracking
            current_time = time.time()
            self.usage_tracking[key].append((current_time, endpoint))

            # Clean up old entries (older than 1 minute)
            one_minute_ago = current_time - 60
            self.usage_tracking[key] = [
                entry for entry in self.usage_tracking[key]
                if entry[0] >= one_minute_ago
            ]

            # Check if rate limit exceeded
            rate_limit = key_info.get("rate_limit", DEFAULT_RATE_LIMIT)
            if len(self.usage_tracking[key]) > rate_limit:
                return False, key_info["user_id"], "Rate limit exceeded"

            # Update last_used timestamp
            self.db.update_api_key_usage(key)

        return True, key_info["user_id"], None

    def get_user_keys(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all API keys for a specific user.

        Args:
            user_id: The user ID

        Returns:
            List[Dict[str, Any]]: List of API key information
        """
        return self.db.get_user_api_keys(user_id)

    def get_usage_stats(self, key: str = None, user_id: str = None) -> Dict[str, Any]:
        """
        Get usage statistics for an API key or user.

        Args:
            key: Specific API key (optional)
            user_id: User ID (optional)

        Returns:
            Dict[str, Any]: Usage statistics
        """
        stats = {}

        if key:
            # Get stats for specific key
            key_info = self.db.get_api_key(key)
            if key_info and key in self.usage_tracking:
                stats[key] = {
                    "key_info": key_info,
                    "requests_last_minute": len(self.usage_tracking[key]),
                    "endpoints": {}
                }

                # Count requests per endpoint
                for _, endpoint in self.usage_tracking[key]:
                    if endpoint not in stats[key]["endpoints"]:
                        stats[key]["endpoints"][endpoint] = 0
                    stats[key]["endpoints"][endpoint] += 1
        elif user_id:
            # Get stats for all keys belonging to user
            user_keys = self.db.get_user_api_keys(user_id)

            if user_keys:
                stats[user_id] = {
                    "total_requests_last_minute": 0,
                    "keys": {}
                }

                for key_info in user_keys:
                    user_key = key_info["key"]
                    if user_key in self.usage_tracking:
                        key_stats = {
                            "key_info": key_info,
                            "requests_last_minute": len(self.usage_tracking[user_key]),
                            "endpoints": {}
                        }

                        # Count requests per endpoint
                        for _, endpoint in self.usage_tracking[user_key]:
                            if endpoint not in key_stats["endpoints"]:
                                key_stats["endpoints"][endpoint] = 0
                            key_stats["endpoints"][endpoint] += 1

                        stats[user_id]["keys"][user_key] = key_stats
                        stats[user_id]["total_requests_last_minute"] += key_stats["requests_last_minute"]
        else:
            # Get overall stats from database
            all_keys_stats = self.db.get_api_key_usage_stats()

            # Combine with real-time tracking data
            total_requests = 0
            endpoint_counts = {}

            for key, usages in self.usage_tracking.items():
                total_requests += len(usages)

                for _, endpoint in usages:
                    if endpoint not in endpoint_counts:
                        endpoint_counts[endpoint] = 0
                    endpoint_counts[endpoint] += 1

            stats["overall"] = {
                "total_requests_last_minute": total_requests,
                "endpoints": endpoint_counts,
                "keys_data": all_keys_stats
            }

        return stats

# Create a singleton instance
_api_key_manager = None

def get_api_key_manager(db_adapter: Optional[DatabaseAdapter] = None) -> ApiKeyManager:
    """
    Get the singleton instance of the API key manager.

    Args:
        db_adapter: Database adapter to use for storage (optional)

    Returns:
        ApiKeyManager: API key manager instance
    """
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = ApiKeyManager(db_adapter)
    return _api_key_manager

# Legacy function for backward compatibility
def load_valid_api_keys() -> Set[str]:
    """
    Get all valid API keys.

    Returns:
        Set[str]: Set of valid API key strings
    """
    return get_api_key_manager().get_valid_api_keys()
