import sys, types
import pytest
from fastapi.testclient import TestClient


# Ensure optional heavy/third-party modules won't break import
# Mock AI libraries if not installed
sys.modules['google'] = types.ModuleType('google')
sys.modules['google.generativeai'] = types.ModuleType('google.generativeai')
anthropic_mod = types.ModuleType('anthropic')
class Anthropic: ...
anthropic_mod.Anthropic = Anthropic
sys.modules['anthropic'] = anthropic_mod

from api_server import app, verify_api_key
from unittest.mock import MagicMock, patch
from unittest import mock

# Override the dependency in the app
app.dependency_overrides[verify_api_key] = lambda: "test_user_id"

# Create a test client
client = TestClient(app)

# Mock the verify_api_key dependency
@pytest.fixture
def mock_verify_api_key():
    """Mock the verify_api_key dependency to return a test user ID."""
    # The dependency is already overridden at the app level
    return "test_user_id"

def test_create_api_key(mock_verify_api_key):
    """Test creating a new API key."""
    with patch("engine.api_key_store.get_api_key_manager") as mock_get_api_key_manager, \
         patch("engine.security.access_control.check_permission", return_value=False) as mock_check_permission:
        # Setup the mock
        mock_api_key_manager = MagicMock()
        mock_get_api_key_manager.return_value = mock_api_key_manager
        mock_api_key_manager.create_api_key.return_value = "new_api_key"

        # Make the request
        response = client.post(
            "/api-keys",
            json={"name": "New Test Key"}
        )

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["key"] == "new_api_key"
        assert data["name"] == "New Test Key"

        # Verify the mock was called correctly
        mock_api_key_manager.create_api_key.assert_called_once_with(
            user_id="test_user_id",
            name="New Test Key",
            rate_limit=mock.ANY,
            permissions=["user"]
        )

def test_revoke_api_key(mock_verify_api_key):
    """Test revoking an API key."""
    with patch("engine.api_key_store.get_api_key_manager") as mock_get_api_key_manager:
        # Setup the mock
        mock_api_key_manager = MagicMock()
        mock_get_api_key_manager.return_value = mock_api_key_manager
        mock_api_key_manager.get_key_info.return_value = {"user_id": "test_user_id"}
        mock_api_key_manager.revoke_api_key.return_value = True

        # Make the request
        response = client.delete("/api-keys/test_api_key")

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

        # Verify the mock was called correctly
        mock_api_key_manager.get_key_info.assert_called_once_with("test_api_key")
        mock_api_key_manager.revoke_api_key.assert_called_once_with("test_api_key")

def test_get_api_key_usage(mock_verify_api_key):
    """Test getting API key usage statistics."""
    with patch("engine.api_key_store.get_api_key_manager") as mock_get_api_key_manager, \
         patch("engine.security.access_control.check_permission", return_value=False) as mock_check_permission:
        # Setup the mock
        mock_api_key_manager = MagicMock()
        mock_get_api_key_manager.return_value = mock_api_key_manager
        mock_api_key_manager.get_usage_stats.return_value = {
            "total_requests": 100,
            "requests_today": 10,
            "average_per_day": 5
        }

        # Make the request
        response = client.get("/api-keys/usage")

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["stats"]["total_requests"] == 100
        assert data["stats"]["requests_today"] == 10
        assert data["stats"]["average_per_day"] == 5

        # Verify the mock was called correctly
        mock_check_permission.assert_called_once()
        mock_api_key_manager.get_usage_stats.assert_called_once_with(user_id="test_user_id")

# User Management Tests
def test_register_user():
    """Test user registration."""
    with patch("api_server.user_manager") as mock_user_manager, \
         patch("engine.api_key_store.get_api_key_manager") as mock_get_api_key_manager:
        # Setup the mocks
        mock_user_manager.create_user.return_value = (True, "User created successfully")

        mock_api_key_manager = MagicMock()
        mock_get_api_key_manager.return_value = mock_api_key_manager
        mock_api_key_manager.create_api_key.return_value = "new_api_key"

        # Make the request
        response = client.post(
            "/register",
            json={
                "username": "testuser",
                "password": "password123",
                "name": "Test User"
            }
        )

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "testuser"
        assert data["api_key"] == "new_api_key"
        assert data["message"] == "User created successfully"

        # Verify the mocks were called correctly
        mock_user_manager.create_user.assert_called_once_with(
            username="testuser",
            password="password123",
            name="Test User",
            role="user"
        )
        mock_api_key_manager.create_api_key.assert_called_once_with(
            user_id="testuser",
            name="Initial API Key",
            rate_limit=mock.ANY,
            permissions=["user"]
        )

def test_login_user():
    """Test user login."""
    with patch("api_server.user_manager") as mock_user_manager, \
         patch("engine.api_key_store.get_api_key_manager") as mock_get_api_key_manager:
        # Setup the mocks
        mock_user_manager.authenticate.return_value = (True, "auth_token")
        mock_user_manager.get_profile.return_value = {
            "name": "Test User",
            "avatar": "avatar.jpg"
        }

        mock_api_key_manager = MagicMock()
        mock_get_api_key_manager.return_value = mock_api_key_manager
        mock_api_key_manager.get_user_keys.return_value = [{"key": "existing_api_key"}]

        # Make the request
        response = client.post(
            "/login",
            json={
                "username": "testuser",
                "password": "password123"
            }
        )

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "testuser"
        assert data["api_key"] == "existing_api_key"
        assert "profile" in data

        # Verify the mocks were called correctly
        mock_user_manager.authenticate.assert_called_once_with(
            username="testuser",
            password="password123"
        )
        mock_api_key_manager.get_user_keys.assert_called_once_with("testuser")
        mock_user_manager.get_profile.assert_called_once_with("testuser")
        # Since we returned existing keys, create_api_key should not be called
        mock_api_key_manager.create_api_key.assert_not_called()

# Conversation Management Tests
def test_get_conversations(mock_verify_api_key):
    """Test getting a list of conversations."""
    with patch("api_server.conversation_store") as mock_conv_store:
        # Setup the mock
        mock_conv_store.list_conversation_meta.return_value = [
            {"id": "conv1", "title": "Conversation 1"},
            {"id": "conv2", "title": "Conversation 2"}
        ]

        # Make the request
        response = client.get("/conversations")

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == "conv1"
        assert data[1]["id"] == "conv2"

        # Verify the mock was called correctly
        mock_conv_store.list_conversation_meta.assert_called_once_with("test_user_id")

def test_get_conversation(mock_verify_api_key):
    """Test getting a specific conversation."""
    with patch("api_server.conversation_store") as mock_conv_store:
        # Setup the mock
        mock_conv_store.load_conversation.return_value = {
            "id": "conv1",
            "title": "Conversation 1",
            "history": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"}
            ]
        }

        # Make the request
        response = client.get("/conversations/conv1")

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "conv1"
        assert data["title"] == "Conversation 1"
        assert len(data["history"]) == 2

        # Verify the mock was called correctly
        mock_conv_store.load_conversation.assert_called_once_with("conv1", "test_user_id")

# User Profile Tests
def test_get_profile(mock_verify_api_key):
    """Test getting a user profile."""
    with patch("api_server.user_manager") as mock_user_manager:
        # Setup the mock
        mock_user_manager.get_profile.return_value = {
            "name": "Test User",
            "bio": "This is a test user",
            "avatar": "avatar.jpg"
        }

        # Make the request
        response = client.get("/profile/test_user_id")

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["name"] == "Test User"
        assert data["profile"]["bio"] == "This is a test user"
        assert data["profile"]["avatar"] == "avatar.jpg"

        # Verify the mock was called correctly
        mock_user_manager.get_profile.assert_called_once_with("test_user_id")

def test_update_profile(mock_verify_api_key):
    """Test updating a user profile."""
    with patch("api_server.user_manager") as mock_user_manager, \
         patch("engine.security.access_control.check_permission", return_value=False) as mock_check_permission:
        # Setup the mock
        mock_user_manager.get_profile.return_value = {
            "name": "Test User",
            "bio": "This is a test user",
            "avatar": "avatar.jpg"
        }
        mock_user_manager.save_profile.return_value = True

        # Make the request
        response = client.post(
            "/profile/test_user_id",
            json={
                "name": "Updated User",
                "avatar": "new_avatar.jpg"
            }
        )

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["name"] == "Updated User"
        assert data["profile"]["bio"] == "This is a test user"  # Unchanged
        assert data["profile"]["avatar"] == "new_avatar.jpg"

        # Verify the mocks were called correctly
        mock_user_manager.get_profile.assert_called_once_with("test_user_id")
        mock_user_manager.save_profile.assert_called_once()

# User Settings Tests
def test_get_user_settings(mock_verify_api_key):
    """Test getting user settings."""
    with patch("api_server.settings_manager") as mock_settings_manager, \
         patch("api_server.get_downloaded_models", return_value=["llama2", "mistral"]) as mock_get_models:
        # Setup the mock
        mock_settings_manager.get_settings.return_value = {
            "theme": "dark",
            "language": "en",
            "notifications_enabled": True
        }

        # Make the request
        response = client.get("/settings/test_user_id")

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert "settings" in data
        assert "llm_options" in data
        assert data["settings"]["theme"] == "dark"
        assert data["settings"]["language"] == "en"
        assert data["settings"]["notifications_enabled"] is True
        assert "ollama" in data["llm_options"]
        assert "openai" in data["llm_options"]

        # Verify the mock was called correctly
        mock_settings_manager.get_settings.assert_called_once_with("test_user_id")
        mock_get_models.assert_called_once()

def test_update_user_settings(mock_verify_api_key):
    """Test updating user settings."""
    with patch("api_server.settings_manager") as mock_settings_manager:
        # Setup the mock
        mock_settings_manager.get_settings.return_value = {
            "theme": "dark",
            "language": "en",
            "notifications_enabled": True
        }
        mock_settings_manager.save_settings.return_value = True

        # Make the request
        response = client.post(
            "/settings/test_user_id",
            json={
                "theme": "light",
                "language": "fr",
                "notifications_enabled": False
            }
        )

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert "settings" in data
        assert data["settings"]["theme"] == "light"
        assert data["settings"]["language"] == "fr"
        assert data["settings"]["notifications_enabled"] is False

        # Verify the mock was called correctly
        mock_settings_manager.get_settings.assert_called_once_with("test_user_id")
        mock_settings_manager.save_settings.assert_called_once()


def test_post_conversation(mock_verify_api_key):
    """Test posting to a conversation."""
    with patch("api_server.conversation_store") as mock_conv_store:

        # Setup the mocks
        mock_conv_store.load_conversation.return_value = {
            "id": "conv1",
            "title": "Conversation 1",
            "history": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"}
            ],
            "user_id": "test_user_id",
            "mode": "chat"
        }
        mock_conv_store.save_conversation.return_value = True

        # Make the request
        response = client.post(
            "/conversations/conv1",
            json={
                "input": "How are you?",
                "conversation_id": "conv1"
            }
        )

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert "conversation_id" in data
        assert "user_id" in data
        assert "mode" in data

        # Verify the mocks were called correctly
        mock_conv_store.load_conversation.assert_called_once_with("conv1", "test_user_id")
        # The endpoint saves the conversation twice: once when input is provided and once at the end
        assert mock_conv_store.save_conversation.call_count == 2

# Error Handling Tests
def test_get_conversation_not_found(mock_verify_api_key):
    """Test getting a conversation that doesn't exist."""
    with patch("api_server.conversation_store") as mock_conv_store:
        # Setup the mock to return None (conversation not found)
        mock_conv_store.load_conversation.return_value = None

        # Make the request
        response = client.get("/conversations/nonexistent")

        # Verify the response
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

        # Verify the mock was called correctly
        mock_conv_store.load_conversation.assert_called_once_with("nonexistent", "test_user_id")

def test_revoke_api_key_not_found(mock_verify_api_key):
    """Test revoking an API key that doesn't exist."""
    with patch("engine.api_key_store.get_api_key_manager") as mock_get_api_key_manager:
        # Setup the mock
        mock_api_key_manager = MagicMock()
        mock_get_api_key_manager.return_value = mock_api_key_manager
        # Key not found
        mock_api_key_manager.get_key_info.return_value = None

        # Make the request
        response = client.delete("/api-keys/nonexistent_key")

        # Verify the response
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

        # Verify the mock was called correctly
        mock_api_key_manager.get_key_info.assert_called_once_with("nonexistent_key")
        # revoke_api_key should not be called if the key is not found
        mock_api_key_manager.revoke_api_key.assert_not_called()

def test_login_user_invalid_credentials():
    """Test login with invalid credentials."""
    with patch("api_server.user_manager") as mock_user_manager:
        # Setup the mock to return False for authentication failure
        mock_user_manager.authenticate.return_value = (False, None)

        # Make the request
        response = client.post(
            "/login",
            json={
                "username": "testuser",
                "password": "wrong_password"
            }
        )

        # Verify the response
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "invalid" in data["detail"].lower() or "password" in data["detail"].lower()

        # Verify the mock was called correctly
        mock_user_manager.authenticate.assert_called_once_with(
            username="testuser",
            password="wrong_password"
        )

def test_verify_api_key_invalid():
    """Test the verify_api_key function with an invalid API key."""
    # Create a direct test for the verify_api_key function
    with patch("engine.api_key_store.get_api_key_manager") as mock_get_api_key_manager:
        # Setup the mock to return invalid for API key validation
        mock_api_key_manager = MagicMock()
        mock_get_api_key_manager.return_value = mock_api_key_manager
        mock_api_key_manager.validate_key.return_value = (False, None, "Invalid API Key")

        # Temporarily remove the dependency override
        original_override = app.dependency_overrides.get(verify_api_key)
        app.dependency_overrides.pop(verify_api_key, None)

        try:
            # Create a test client with the original dependency
            test_client = TestClient(app)

            # Make a request that requires API key verification
            response = test_client.get(
                "/conversations",
                headers={"X-API-Key": "invalid_key"}
            )
        finally:
            # Restore the dependency override
            if original_override:
                app.dependency_overrides[verify_api_key] = original_override

        # Verify the response
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "invalid" in data["detail"].lower()

        # Verify the mock was called correctly
        mock_api_key_manager.validate_key.assert_called_once_with("invalid_key", mock.ANY)

def test_update_profile_unauthorized(mock_verify_api_key):
    """Test updating a profile for a different user without permission."""
    with patch("api_server.user_manager") as mock_user_manager, \
         patch("engine.security.access_control.check_permission", return_value=False) as mock_check_permission:
        # Setup the mock for a different user than the authenticated one
        # The test will try to update "different_user_id" while authenticated as "test_user_id"

        # Make the request to update a different user's profile
        response = client.post(
            "/profile/different_user_id",
            json={
                "name": "Updated User",
                "avatar": "new_avatar.jpg"
            }
        )

        # Verify the response
        assert response.status_code == 403
        data = response.json()
        assert "detail" in data
        assert "permission" in data["detail"].lower() or "own" in data["detail"].lower()

        # Verify the mock was called correctly
        mock_check_permission.assert_called_once()
        # The user_manager's get_profile and save_profile should not be called
        mock_user_manager.get_profile.assert_not_called()
        mock_user_manager.save_profile.assert_not_called()
