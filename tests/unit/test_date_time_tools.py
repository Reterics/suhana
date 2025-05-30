import pytest
from unittest.mock import patch
from datetime import datetime
from tools.get_date import action as date_action
from tools.get_time import action as time_action

@pytest.fixture
def mock_datetime():
    """Mock datetime.now() to return a fixed date and time"""
    with patch('tools.get_date.datetime') as mock_date, \
         patch('tools.get_time.datetime') as mock_time:

        # Create a fixed datetime object for testing
        fixed_datetime = datetime(2023, 5, 15, 14, 30, 45)

        # Configure both mocks to return the fixed datetime
        mock_date.now.return_value = fixed_datetime
        mock_time.now.return_value = fixed_datetime

        yield fixed_datetime

def test_get_date(mock_datetime):
    """Test that get_date returns the correct date string"""
    result = date_action()
    assert "Today is: 2023-05-15" in result

def test_get_date_with_input(mock_datetime):
    """Test that get_date works with user input parameter"""
    result = date_action("what is the date")
    assert "Today is: 2023-05-15" in result

def test_get_time(mock_datetime):
    """Test that get_time returns the correct time string"""
    result = time_action()
    assert "Current time: 14:30:45" in result

def test_get_time_with_input(mock_datetime):
    """Test that get_time works with user input parameter"""
    result = time_action("what is the time")
    assert "Current time: 14:30:45" in result
