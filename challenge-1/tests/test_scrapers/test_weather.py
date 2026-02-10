"""Tests for the weather scraper (Open-Meteo)."""

import pytest
from unittest.mock import patch, MagicMock

from src.scrapers.weather import WeatherFetcher, _extract_city, _weather_code_to_text


class TestWeatherFetcher:
    """Test weather data fetching."""

    def test_extract_city_mumbai(self):
        city, lat, lon = _extract_city("Is it raining in Mumbai?")
        assert city == "Mumbai"
        assert abs(lat - 19.076) < 0.01

    def test_extract_city_default_delhi(self):
        city, lat, lon = _extract_city("What is the weather?")
        assert city == "Delhi"

    def test_weather_code_to_text(self):
        assert _weather_code_to_text(0) == "Clear sky"
        assert _weather_code_to_text(65) == "Heavy rain"
        assert _weather_code_to_text(999) == "Unknown conditions"

    def test_search_returns_list(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "current": {
                "temperature_2m": 32.5,
                "relative_humidity_2m": 75,
                "apparent_temperature": 36.0,
                "precipitation": 0,
                "weather_code": 2,
                "wind_speed_10m": 12.3,
            }
        }

        with patch("src.scrapers.weather.requests.get", return_value=mock_resp):
            fetcher = WeatherFetcher()
            results = fetcher.search("weather in Delhi")

            assert len(results) == 1
            assert "Delhi" in results[0]["content"]
            assert results[0]["source_url"] == "https://open-meteo.com/"
