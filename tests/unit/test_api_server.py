import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from api_server import app, verify_api_key, ApiKeyCreate, UserRegistration, UserLogin, ProfileUpdate, user_manager

# Create a test client
client = TestClient(app)

# Mock the verify_api_key dependency
@pytest.fixture
def mock_verify_api_key():
    """Mock the verify_api_key dependency to return a test user ID."""
    with patch("api_server.verify_api_key", return_value="test_user_id"):
        yield "test_user_id"

# API Key Management Tests
def test_list_api_keys(mock_verify_api_key):
    """Test listing API keys for a user."""
    with patch("api_server.user_manager") as mock_user_manager:
        # Setup the mock
        mock_user_manager.list_api_keys.return_value = [
            {"key": "api_key_1", "name": "Test Key 1", "created_at": "2025-01-01T00:00:00"},
            {"key": "api_key_2", "name": "Test Key 2", "created_at": "2025-01-02T00:00:00"}
        ]

        # Make the request
        response = client.get("/api-keys")

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert len(data["keys"]) == 2
        assert data["keys"][0]["key"] == "api_key_1"
        assert data["keys"][1]["key"] == "api_key_2"

        # Verify the mock was called correctly
        mock_user_manager.list_api_keys.assert_called_once_with("test_user_id")

def test_create_api_key(mock_verify_api_key):
    """Test creating a new API key."""
    with patch("api_server.user_manager") as mock_user_manager:
        # Setup the mock
        mock_user_manager.create_api_key.return_value = "new_api_key"

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
        mock_user_manager.create_api_key.assert_called_once()

def test_revoke_api_key(mock_verify_api_key):
    """Test revoking an API key."""
    with patch("api_server.UserManager") as mock_user_manager:
        # Setup the mock
        mock_instance = mock_user_manager.return_value
        mock_instance.revoke_api_key.return_value = True

        # Make the request
        response = client.delete("/api-keys/test_api_key")

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify the mock was called correctly
        mock_instance.revoke_api_key.assert_called_once_with("test_user_id", "test_api_key")

def test_get_api_key_usage(mock_verify_api_key):
    """Test getting API key usage statistics."""
    with patch("api_server.UserManager") as mock_user_manager:
        # Setup the mock
        mock_instance = mock_user_manager.return_value
        mock_instance.get_api_key_usage.return_value = {
            "total_requests": 100,
            "requests_today": 10,
            "average_per_day": 5
        }

        # Make the request
        response = client.get("/api-keys/usage")

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["total_requests"] == 100
        assert data["requests_today"] == 10
        assert data["average_per_day"] == 5

        # Verify the mock was called correctly
        mock_instance.get_api_key_usage.assert_called_once_with("test_user_id")

# User Management Tests
def test_register_user():
    """Test user registration."""
    with patch("api_server.UserManager") as mock_user_manager:
        # Setup the mock
        mock_instance = mock_user_manager.return_value
        mock_instance.register_user.return_value = {
            "user_id": "new_user_id",
            "username": "testuser",
            "api_key": "new_api_key"
        }

        # Make the request
        response = client.post(
            "/register",
            json={
                "username": "testuser",
                "password": "password123",
                "email": "test@example.com"
            }
        )

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "new_user_id"
        assert data["username"] == "testuser"
        assert data["api_key"] == "new_api_key"

        # Verify the mock was called correctly
        mock_instance.register_user.assert_called_once()
        args = mock_instance.register_user.call_args.args[0]
        assert args.username == "testuser"
        assert args.password == "password123"
        assert args.email == "test@example.com"

def test_login_user():
    """Test user login."""
    with patch("api_server.UserManager") as mock_user_manager:
        # Setup the mock
        mock_instance = mock_user_manager.return_value
        mock_instance.login_user.return_value = {
            "user_id": "user_id",
            "username": "testuser",
            "api_key": "api_key"
        }

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
        assert data["user_id"] == "user_id"
        assert data["username"] == "testuser"
        assert data["api_key"] == "api_key"

        # Verify the mock was called correctly
        mock_instance.login_user.assert_called_once()
        args = mock_instance.login_user.call_args.args[0]
        assert args.username == "testuser"
        assert args.password == "password123"

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
    with patch("api_server.UserManager") as mock_user_manager:
        # Setup the mock
        mock_instance = mock_user_manager.return_value
        mock_instance.get_profile.return_value = {
            "name": "Test User",
            "bio": "This is a test user",
            "avatar": "avatar.jpg"
        }

        # Make the request
        response = client.get("/users/test_user_id/profile")

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test User"
        assert data["bio"] == "This is a test user"
        assert data["avatar"] == "avatar.jpg"

        # Verify the mock was called correctly
        mock_instance.get_profile.assert_called_once_with("test_user_id")

def test_update_profile(mock_verify_api_key):
    """Test updating a user profile."""
    with patch("api_server.UserManager") as mock_user_manager:
        # Setup the mock
        mock_instance = mock_user_manager.return_value
        mock_instance.update_profile.return_value = {
            "name": "Updated User",
            "bio": "This is an updated bio",
            "avatar": "new_avatar.jpg"
        }

        # Make the request
        response = client.put(
            "/users/test_user_id/profile",
            json={
                "name": "Updated User",
                "bio": "This is an updated bio",
                "avatar": "new_avatar.jpg"
            }
        )

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated User"
        assert data["bio"] == "This is an updated bio"
        assert data["avatar"] == "new_avatar.jpg"

        # Verify the mock was called correctly
        mock_instance.update_profile.assert_called_once()
        args = mock_instance.update_profile.call_args
        assert args[0][0] == "test_user_id"  # First positional arg
        profile_update = args[0][1]  # Second positional arg
        assert profile_update.name == "Updated User"
        assert profile_update.bio == "This is an updated bio"
        assert profile_update.avatar == "new_avatar.jpg"

# User Settings Tests
def test_get_user_settings(mock_verify_api_key):
    """Test getting user settings."""
    with patch("api_server.UserManager") as mock_user_manager:
        # Setup the mock
        mock_instance = mock_user_manager.return_value
        mock_instance.get_settings.return_value = {
            "theme": "dark",
            "language": "en",
            "notifications_enabled": True
        }

        # Make the request
        response = client.get("/users/test_user_id/settings")

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["theme"] == "dark"
        assert data["language"] == "en"
        assert data["notifications_enabled"] is True

        # Verify the mock was called correctly
        mock_instance.get_settings.assert_called_once_with("test_user_id")

def test_update_user_settings(mock_verify_api_key):
    """Test updating user settings."""
    with patch("api_server.UserManager") as mock_user_manager:
        # Setup the mock
        mock_instance = mock_user_manager.return_value
        mock_instance.update_settings.return_value = {
            "theme": "light",
            "language": "fr",
            "notifications_enabled": False
        }

        # Make the request
        response = client.put(
            "/users/test_user_id/settings",
            json={
                "theme": "light",
                "language": "fr",
                "notifications_enabled": False
            }
        )

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["theme"] == "light"
        assert data["language"] == "fr"
        assert data["notifications_enabled"] is False

        # Verify the mock was called correctly
        mock_instance.update_settings.assert_called_once()

# Browsing Tests
def test_browse_folders(mock_verify_api_key):
    """Test browsing folders."""
    with patch("api_server.os.path.isdir") as mock_isdir, \
         patch("api_server.os.path.isfile") as mock_isfile, \
         patch("api_server.os.listdir") as mock_listdir, \
         patch("api_server.os.path.getmtime") as mock_getmtime, \
         patch("api_server.os.path.getsize") as mock_getsize:

        # Setup the mocks
        mock_isdir.return_value = True
        mock_isfile.side_effect = lambda path: path.endswith(".txt")
        mock_listdir.return_value = ["folder1", "file1.txt", "file2.txt"]
        mock_getmtime.return_value = 1609459200  # 2021-01-01
        mock_getsize.return_value = 1024

        # Make the request
        response = client.get("/browse?path=test_path")

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3

        # Check folder
        folder = next(item for item in data["items"] if item["name"] == "folder1")
        assert folder["type"] == "directory"

        # Check files
        files = [item for item in data["items"] if item["type"] == "file"]
        assert len(files) == 2
        assert files[0]["name"] in ["file1.txt", "file2.txt"]
        assert files[1]["name"] in ["file1.txt", "file2.txt"]
        assert files[0]["size"] == 1024

        # Verify the mocks were called correctly
        mock_listdir.assert_called_once_with("test_path")

# Post Conversation Test
def test_post_conversation(mock_verify_api_key):
    """Test posting to a conversation."""
    with patch("api_server.conversation_store") as mock_conv_store, \
         patch("api_server.handle_input") as mock_handle_input:

        # Setup the mocks
        mock_conv_store.load_conversation.return_value = {
            "id": "conv1",
            "title": "Conversation 1",
            "history": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"}
            ]
        }
        mock_handle_input.return_value = "This is a response"
        mock_conv_store.save_conversation.return_value = True

        # Make the request
        response = client.post(
            "/conversations/conv1",
            json={
                "query": "How are you?",
                "conversation_id": "conv1"
            }
        )

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "This is a response"

        # Verify the mocks were called correctly
        mock_conv_store.load_conversation.assert_called_once_with("conv1", "test_user_id")
        mock_handle_input.assert_called_once()
        mock_conv_store.save_conversation.assert_called_once()

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
    with patch("api_server.UserManager") as mock_user_manager:
        # Setup the mock to return False (key not found or not revoked)
        mock_instance = mock_user_manager.return_value
        mock_instance.revoke_api_key.return_value = False

        # Make the request
        response = client.delete("/api-keys/nonexistent_key")

        # Verify the response
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower() or "could not be revoked" in data["detail"].lower()

        # Verify the mock was called correctly
        mock_instance.revoke_api_key.assert_called_once_with("test_user_id", "nonexistent_key")

def test_login_user_invalid_credentials():
    """Test login with invalid credentials."""
    with patch("api_server.UserManager") as mock_user_manager:
        # Setup the mock to raise an exception for invalid credentials
        mock_instance = mock_user_manager.return_value
        mock_instance.login_user.side_effect = Exception("Invalid credentials")

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
        assert "invalid" in data["detail"].lower() or "failed" in data["detail"].lower()

        # Verify the mock was called correctly
        mock_instance.login_user.assert_called_once()

def test_verify_api_key_invalid():
    """Test the verify_api_key function with an invalid API key."""
    # Create a direct test for the verify_api_key function
    with patch("api_server.UserManager") as mock_user_manager:
        # Setup the mock to raise an exception for invalid API key
        mock_instance = mock_user_manager.return_value
        mock_instance.verify_api_key.side_effect = Exception("Invalid API key")

        # Create a test client that doesn't override the verify_api_key dependency
        test_client = TestClient(app)

        # Make a request that requires API key verification
        response = test_client.get(
            "/conversations",
            headers={"X-API-Key": "invalid_key"}
        )

        # Verify the response
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "unauthorized" in data["detail"].lower() or "invalid" in data["detail"].lower()

def test_update_profile_unauthorized(mock_verify_api_key):
    """Test updating a profile for a different user without permission."""
    with patch("api_server.UserManager") as mock_user_manager:
        # Setup the mock to raise an exception for unauthorized access
        mock_instance = mock_user_manager.return_value
        mock_instance.update_profile.side_effect = Exception("Unauthorized")

        # Make the request to update a different user's profile
        response = client.put(
            "/users/different_user_id/profile",
            json={
                "name": "Updated User",
                "bio": "This is an updated bio",
                "avatar": "new_avatar.jpg"
            }
        )

        # Verify the response
        assert response.status_code == 403
        data = response.json()
        assert "detail" in data
        assert "permission" in data["detail"].lower() or "unauthorized" in data["detail"].lower()

        # Verify the mock was called correctly
        mock_instance.update_profile.assert_called_once()
