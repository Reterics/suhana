import pytest
from unittest.mock import patch, MagicMock
from tools.weather import action

# Sample geocoding API response
GEOCODE_RESPONSE = {
    "results": [
        {
            "name": "New York",
            "country": "United States",
            "latitude": 40.7128,
            "longitude": -74.0060
        }
    ]
}

# Sample weather API response
WEATHER_RESPONSE = {
    "current": {
        "temperature_2m": 22.5,
        "relative_humidity_2m": 65,
        "apparent_temperature": 23.1,
        "precipitation": 0,
        "weather_code": 1,
        "wind_speed_10m": 10.5,
        "wind_direction_10m": 180
    },
    "current_units": {
        "temperature_2m": "°C",
        "wind_speed_10m": "km/h",
        "precipitation": "mm"
    }
}

# Sample error response for geocoding
GEOCODE_ERROR_RESPONSE = {
    "results": []
}

# Sample error response for weather
WEATHER_ERROR_RESPONSE = {
    "error": "Invalid coordinates"
}

@pytest.fixture
def mock_get_success():
    """Mock successful API responses"""
    with patch('tools.weather.get') as mock_get:
        # Create two different response objects for the two API calls
        geocode_response = MagicMock()
        geocode_response.text = '{"results": [{"name": "New York", "country": "United States", "latitude": 40.7128, "longitude": -74.0060}]}'

        weather_response = MagicMock()
        weather_response.text = '{"current": {"temperature_2m": 22.5, "relative_humidity_2m": 65, "apparent_temperature": 23.1, "precipitation": 0, "weather_code": 1, "wind_speed_10m": 10.5, "wind_direction_10m": 180}, "current_units": {"temperature_2m": "°C", "wind_speed_10m": "km/h", "precipitation": "mm"}}'

        # Configure the mock to return different responses based on the URL
        def side_effect(url, **kwargs):
            if "geocoding-api" in url:
                return geocode_response
            else:
                return weather_response

        mock_get.side_effect = side_effect
        yield mock_get

@pytest.fixture
def mock_get_location_not_found():
    """Mock API response for location not found"""
    with patch('tools.weather.get') as mock_get:
        response = MagicMock()
        response.text = '{"results": []}'
        mock_get.return_value = response
        yield mock_get

@pytest.fixture
def mock_get_weather_error():
    """Mock API response for weather error"""
    with patch('tools.weather.get') as mock_get:
        # First call returns geocoding success
        geocode_response = MagicMock()
        geocode_response.text = '{"results": [{"name": "New York", "country": "United States", "latitude": 40.7128, "longitude": -74.0060}]}'

        # Second call returns weather error
        weather_response = MagicMock()
        weather_response.text = '{"error": "Invalid coordinates"}'

        # Configure the mock to return different responses based on the call order
        def side_effect(url, **kwargs):
            if "geocoding-api" in url:
                return geocode_response
            else:
                return weather_response

        mock_get.side_effect = side_effect
        yield mock_get

def test_weather_success(mock_get_success):
    """Test successful weather retrieval"""
    result = action("weather in New York", "New York")

    # Check that the result contains expected weather information
    assert "Weather for New York, United States" in result
    assert "Temperature: 22.5°C" in result
    assert "Feels like: 23.1°C" in result
    assert "Humidity: 65%" in result
    assert "Wind: 10.5km/h" in result
    assert "Mainly clear" in result  # Weather code 1

def test_weather_location_not_found(mock_get_location_not_found):
    """Test handling of location not found"""
    result = action("weather in NonexistentPlace", "NonexistentPlace")
    assert "couldn't find the location" in result
    assert "NonexistentPlace" in result

def test_weather_api_error(mock_get_weather_error):
    """Test handling of weather API error"""
    result = action("weather in New York", "New York")
    assert "couldn't get weather data" in result

def test_weather_exception_handling():
    """Test general exception handling"""
    with patch('tools.weather.get', side_effect=Exception("Test error")):
        result = action("weather in New York", "New York")
        assert "couldn't get weather information" in result
        assert "Test error" in result
