"""Weather data fetcher using Open-Meteo API (free, no key required).

API URL is read from config/sources.yaml — not hardcoded.
"""

import logging
from datetime import datetime

import requests

from config.settings import get_domain_config
from src.utils.text_processing import normalize_text

logger = logging.getLogger(__name__)

# Default API URL (overridden by config/sources.yaml if present)
_DEFAULT_API_URL = "https://api.open-meteo.com/v1/forecast"


def _get_api_url() -> str:
    """Read the weather API URL from sources.yaml, falling back to default."""
    cfg = get_domain_config("weather")
    if cfg and cfg.get("api_url"):
        return cfg["api_url"]
    return _DEFAULT_API_URL

# Common Indian cities with coordinates
CITY_COORDINATES: dict[str, tuple[float, float]] = {
    "mumbai": (19.0760, 72.8777),
    "delhi": (28.6139, 77.2090),
    "new delhi": (28.6139, 77.2090),
    "bangalore": (12.9716, 77.5946),
    "bengaluru": (12.9716, 77.5946),
    "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639),
    "hyderabad": (17.3850, 78.4867),
    "pune": (18.5204, 73.8567),
    "ahmedabad": (23.0225, 72.5714),
    "jaipur": (26.9124, 75.7873),
    "lucknow": (26.8467, 80.9462),
    # International
    "london": (51.5074, -0.1278),
    "new york": (40.7128, -74.0060),
    "tokyo": (35.6762, 139.6503),
    "paris": (48.8566, 2.3522),
    "sydney": (-33.8688, 151.2093),
    "washington": (38.9072, -77.0369),
    "beijing": (39.9042, 116.4074),
    "singapore": (1.3521, 103.8198),
}


def _extract_city(query: str) -> tuple[str, float, float]:
    """
    Extract a city name from the query and return its coordinates.

    Falls back to Delhi if no city is recognized.
    """
    query_lower = query.lower()
    for city, (lat, lon) in CITY_COORDINATES.items():
        if city in query_lower:
            return city.title(), lat, lon

    # Default to Delhi
    return "Delhi", 28.6139, 77.2090


class WeatherFetcher:
    """Fetch current weather using the Open-Meteo API (URL from config)."""

    def search(self, query: str) -> list[dict]:
        """
        Fetch current weather for a location mentioned in the query.

        Weather data is always ephemeral (never stored in pgvector).
        """
        city, lat, lon = _extract_city(query)
        logger.info("Fetching weather for %s (%.4f, %.4f)", city, lat, lon)

        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                       "precipitation,weather_code,wind_speed_10m",
            "timezone": "auto",
        }

        api_url = _get_api_url()
        try:
            resp = requests.get(api_url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error("Open-Meteo API error: %s", e)
            return []

        current = data.get("current", {})
        if not current:
            return []

        temp = current.get("temperature_2m", "N/A")
        humidity = current.get("relative_humidity_2m", "N/A")
        feels_like = current.get("apparent_temperature", "N/A")
        precip = current.get("precipitation", 0)
        wind_speed = current.get("wind_speed_10m", "N/A")
        weather_code = current.get("weather_code", 0)

        weather_desc = _weather_code_to_text(weather_code)
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        content = (
            f"Current weather in {city} as of {now}: "
            f"{weather_desc}. Temperature: {temp}°C (feels like {feels_like}°C). "
            f"Humidity: {humidity}%. Precipitation: {precip}mm. "
            f"Wind speed: {wind_speed} km/h."
        )

        return [{
            "content": normalize_text(content),
            "source_url": "https://open-meteo.com/",
            "source_title": f"Open-Meteo Weather: {city}",
            "date": now,
        }]


def _weather_code_to_text(code: int) -> str:
    """Convert WMO weather code to human-readable text."""
    codes = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snowfall",
        73: "Moderate snowfall",
        75: "Heavy snowfall",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail",
    }
    return codes.get(code, "Unknown conditions")
