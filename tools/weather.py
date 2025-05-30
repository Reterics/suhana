import json
from urllib.parse import quote_plus
from engine.net import get

name = "weather"
description = "Gets current weather information for a location"
pattern = r"(?:what(?:'s| is) the )?weather(?: in| for)?\s+(?P<location>[A-Za-z0-9 ,\-]+)[\?\. ]*$"

def action(user_input: str, location: str) -> str:
    """Get current weather information for a location using OpenWeatherMap API"""
    try:
        # Clean up the location
        location = location.strip()

        # Use OpenMeteo API which doesn't require an API key
        # First, get geocoding information
        geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={quote_plus(location)}&count=1&language=en&format=json"
        geocode_response = get(geocode_url, timeout=10)
        geocode_data = json.loads(geocode_response.text)

        if not geocode_data.get("results"):
            return f"Sorry, I couldn't find the location '{location}'. Please try a different location."

        # Extract location data
        result = geocode_data["results"][0]
        lat = result["latitude"]
        lon = result["longitude"]
        full_location = f"{result.get('name', '')}, {result.get('country', '')}"

        # Get weather data
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m&timezone=auto"
        weather_response = get(weather_url, timeout=10)
        weather_data = json.loads(weather_response.text)

        if "current" not in weather_data:
            return f"Sorry, I couldn't get weather data for '{location}'."

        current = weather_data["current"]

        # Map weather codes to descriptions
        weather_descriptions = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Fog",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            56: "Light freezing drizzle",
            57: "Dense freezing drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            66: "Light freezing rain",
            67: "Heavy freezing rain",
            71: "Slight snow fall",
            73: "Moderate snow fall",
            75: "Heavy snow fall",
            77: "Snow grains",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            85: "Slight snow showers",
            86: "Heavy snow showers",
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail"
        }

        weather_code = current.get("weather_code", 0)
        weather_description = weather_descriptions.get(weather_code, "Unknown")

        # Format the response
        temp_unit = weather_data.get("current_units", {}).get("temperature_2m", "°C")
        wind_unit = weather_data.get("current_units", {}).get("wind_speed_10m", "km/h")

        response = f"Weather for {full_location}:\n"
        response += f"• Condition: {weather_description}\n"
        response += f"• Temperature: {current.get('temperature_2m', 'N/A')}{temp_unit}\n"
        response += f"• Feels like: {current.get('apparent_temperature', 'N/A')}{temp_unit}\n"
        response += f"• Humidity: {current.get('relative_humidity_2m', 'N/A')}%\n"
        response += f"• Wind: {current.get('wind_speed_10m', 'N/A')}{wind_unit}"

        if current.get('precipitation', 0) > 0:
            precip_unit = weather_data.get("current_units", {}).get("precipitation", "mm")
            response += f"\n• Precipitation: {current.get('precipitation')}{precip_unit}"

        return response

    except Exception as e:
        return f"Sorry, I couldn't get weather information. Error: {str(e)}"
