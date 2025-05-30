import pytest
from unittest.mock import patch, MagicMock
import requests


from engine.net import get, USER_AGENTS

@pytest.fixture
def mock_sleep():
    """Mock time.sleep to avoid waiting during tests."""
    with patch("time.sleep") as mock:
        yield mock

@pytest.fixture
def mock_random_choice():
    """Mock random.choice to return a predictable User-Agent."""
    with patch("random.choice", return_value=USER_AGENTS[0]) as mock:
        yield mock

def test_get_successful_request(mock_sleep, mock_random_choice):
    """Test a successful GET request."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_response) as mock_get:
        response = get("https://example.com")

        # Verify the response is returned
        assert response == mock_response

        # Verify requests.get was called with the correct parameters
        mock_get.assert_called_once_with(
            "https://example.com",
            headers={"User-Agent": USER_AGENTS[0]},
            timeout=10
        )

        # Verify raise_for_status was called
        mock_response.raise_for_status.assert_called_once()

        # Verify sleep was not called (no retries needed)
        mock_sleep.assert_not_called()

def test_get_retry_success(mock_sleep, mock_random_choice):
    """Test a request that fails on first attempt but succeeds on retry."""
    # First request fails, second succeeds
    mock_error_response = MagicMock()
    mock_error_response.raise_for_status.side_effect = requests.HTTPError("404 Client Error")

    mock_success_response = MagicMock()
    mock_success_response.raise_for_status.return_value = None

    with patch("requests.get", side_effect=[mock_error_response, mock_success_response]) as mock_get:
        response = get("https://example.com")

        # Verify the successful response is returned
        assert response == mock_success_response

        # Verify requests.get was called twice
        assert mock_get.call_count == 2

        # Verify sleep was called once (after the first failure)
        mock_sleep.assert_called_once_with(1)

def test_get_all_retries_fail(mock_sleep, mock_random_choice):
    """Test a request that fails all retries."""
    # All requests fail
    mock_error = requests.HTTPError("500 Server Error")
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = mock_error

    with patch("requests.get", return_value=mock_response) as mock_get:
        # Should raise the last error
        with pytest.raises(requests.HTTPError) as excinfo:
            get("https://example.com")

        # Verify the error is the one we expected
        assert str(excinfo.value) == "500 Server Error"

        # Verify requests.get was called the correct number of times (default retries = 2)
        assert mock_get.call_count == 2

        # Verify sleep was called for each retry
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)  # First retry
        mock_sleep.assert_any_call(2)  # Second retry

def test_get_with_custom_headers(mock_sleep, mock_random_choice):
    """Test a request with custom headers."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None

    custom_headers = {
        "Authorization": "Bearer token123",
        "Accept": "application/json"
    }

    with patch("requests.get", return_value=mock_response) as mock_get:
        response = get("https://example.com", headers=custom_headers)

        # Verify the response is returned
        assert response == mock_response

        # Verify requests.get was called with the correct parameters
        expected_headers = {
            "Authorization": "Bearer token123",
            "Accept": "application/json",
            "User-Agent": USER_AGENTS[0]
        }
        mock_get.assert_called_once_with(
            "https://example.com",
            headers=expected_headers,
            timeout=10
        )

def test_get_with_custom_timeout_and_retries(mock_sleep, mock_random_choice):
    """Test a request with custom timeout and retries."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_response) as mock_get:
        response = get("https://example.com", retries=5, timeout=30)

        # Verify the response is returned
        assert response == mock_response

        # Verify requests.get was called with the correct parameters
        mock_get.assert_called_once_with(
            "https://example.com",
            headers={"User-Agent": USER_AGENTS[0]},
            timeout=30
        )

def test_get_random_user_agent():
    """Test that a random User-Agent is selected."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_response) as mock_get:
        with patch("random.choice", return_value=USER_AGENTS[1]) as mock_choice:
            response = get("https://example.com")

            # Verify random.choice was called with USER_AGENTS
            mock_choice.assert_called_once_with(USER_AGENTS)

            # Verify the selected User-Agent was used
            mock_get.assert_called_once_with(
                "https://example.com",
                headers={"User-Agent": USER_AGENTS[1]},
                timeout=10
            )

def test_get_connection_error(mock_sleep, mock_random_choice):
    """Test handling of connection errors."""
    # Simulate a connection error
    mock_error = requests.ConnectionError("Connection refused")

    with patch("requests.get", side_effect=mock_error) as mock_get:
        # Should raise the connection error after all retries
        with pytest.raises(requests.ConnectionError) as excinfo:
            get("https://example.com")

        # Verify the error is the one we expected
        assert str(excinfo.value) == "Connection refused"

        # Verify requests.get was called the correct number of times
        assert mock_get.call_count == 2
