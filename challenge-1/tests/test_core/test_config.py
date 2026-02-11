"""Tests for config/settings sources loading."""

import pytest


class TestSourcesConfig:
    """Test YAML sources configuration loading."""

    def test_get_sources_config_loads(self):
        """get_sources_config should load the YAML file."""
        from config.settings import get_sources_config
        config = get_sources_config()
        assert "domains" in config
        assert "news" in config["domains"]
        assert "finance" in config["domains"]
        assert "govt" in config["domains"]
        assert "weather" in config["domains"]

    def test_get_domain_config(self):
        """get_domain_config should return config for a valid domain."""
        from config.settings import get_domain_config
        news_cfg = get_domain_config("news")
        assert news_cfg is not None
        assert "sources" in news_cfg
        assert len(news_cfg["sources"]) > 0

    def test_get_domain_config_invalid(self):
        """get_domain_config should return None for unknown domain."""
        from config.settings import get_domain_config
        assert get_domain_config("nonexistent") is None

    def test_get_allowed_domains(self):
        """get_allowed_domains should return list of domain strings."""
        from config.settings import get_allowed_domains
        domains = get_allowed_domains("news")
        assert isinstance(domains, list)
        assert len(domains) > 0
        assert all(isinstance(d, str) for d in domains)

    def test_get_search_instructions(self):
        """get_search_instructions should return non-empty string."""
        from config.settings import get_search_instructions
        instructions = get_search_instructions("news")
        assert isinstance(instructions, str)
        assert len(instructions) > 0

    def test_weather_has_api_type(self):
        """Weather domain should have type=api."""
        from config.settings import get_domain_config
        weather_cfg = get_domain_config("weather")
        assert weather_cfg is not None
        assert weather_cfg.get("type") == "api"
        assert "api_url" in weather_cfg
