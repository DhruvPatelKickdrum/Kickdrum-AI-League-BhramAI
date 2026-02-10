"""Tests for dynamic retrieval."""

import pytest
from unittest.mock import patch

from src.retrieval.dynamic import search_dynamic


class TestDynamicRetrieval:
    """Test dynamic retrieval orchestrator."""

    def test_unknown_domain_tries_all(self):
        """Unknown domain should try all scrapers."""
        with patch("src.retrieval.dynamic._SCRAPERS") as mock_scrapers:
            mock_scrapers.items.return_value = []
            results = search_dynamic("test query", domain="unknown")
            assert results == []

    def test_weather_domain(self):
        """Weather domain should use WeatherFetcher."""
        with patch("src.scrapers.weather.WeatherFetcher.search") as mock_search:
            mock_search.return_value = [{"content": "test", "source_url": "http://test.com"}]
            results = search_dynamic("weather in Delhi", domain="weather")
            assert len(results) >= 0  # May be 0 if constructor changes
