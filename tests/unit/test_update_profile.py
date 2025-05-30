from unittest.mock import patch, mock_open
import json

from tools.update_profile import action

class MockPath:
    """A mock Path object that can be configured to exist or not exist."""
    def __init__(self, exists=True):
        self.exists_value = exists
        self.path = "profile.json"
    def exists(self):
        return self.exists_value
    def __str__(self):
        return self.path

def test_action_creates_new_profile():
    mock_file = mock_open()
    mock_path = MockPath(exists=False)

    with patch('tools.update_profile.PROFILE_PATH', mock_path), \
         patch('builtins.open', mock_file), \
         patch('json.dump') as mock_dump:

        result = action("theme", "dark")

        assert "Preference 'theme' updated to 'dark'" in result

        mock_file.assert_called_once_with(mock_path, "w", encoding="utf-8")
        # Should create a profile with only preferences
        mock_dump.assert_called_once_with({"preferences": {"theme": "dark"}}, mock_file(), indent=2)

def test_action_updates_existing_profile():
    data = {
        "name": "Test User",
        "preferences": {
            "language": "en"
        }
    }
    mock_file = mock_open(read_data=json.dumps(data))
    mock_path = MockPath(exists=True)

    with patch('tools.update_profile.PROFILE_PATH', mock_path), \
         patch('builtins.open', mock_file), \
         patch('json.dump') as mock_dump:

        result = action("theme", "dark")

        assert "Preference 'theme' updated to 'dark'" in result
        assert mock_file.call_count == 2
        mock_file.assert_any_call(mock_path, "r", encoding="utf-8")
        mock_file.assert_any_call(mock_path, "w", encoding="utf-8")

        expected = {
            "name": "Test User",
            "preferences": {
                "language": "en",
                "theme": "dark"
            }
        }
        mock_dump.assert_called_once_with(expected, mock_file(), indent=2)

def test_action_updates_existing_preference():
    data = {
        "preferences": {
            "theme": "light"
        }
    }
    mock_file = mock_open(read_data=json.dumps(data))
    mock_path = MockPath(exists=True)

    with patch('tools.update_profile.PROFILE_PATH', mock_path), \
         patch('builtins.open', mock_file), \
         patch('json.dump') as mock_dump:

        result = action("theme", "dark")
        assert "Preference 'theme' updated to 'dark'" in result
        assert mock_file.call_count == 2
        expected = {
            "preferences": {
                "theme": "dark"
            }
        }
        mock_dump.assert_called_once_with(expected, mock_file(), indent=2)

def test_action_with_json_error():
    mock_file = mock_open(read_data="invalid json")
    mock_path = MockPath(exists=True)

    with patch('tools.update_profile.PROFILE_PATH', mock_path), \
         patch('builtins.open', mock_file), \
         patch('json.load', side_effect=json.JSONDecodeError("Invalid JSON", "", 0)), \
         patch('json.dump') as mock_dump:

        result = action("theme", "dark")
        assert "Preference 'theme' updated to 'dark'" in result
        mock_dump.assert_called_once_with({"preferences": {"theme": "dark"}}, mock_file(), indent=2)
