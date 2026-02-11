"""Tests for the query router."""

import pytest
from unittest.mock import patch, MagicMock


class TestRouterPrompt:
    """Test router logic and prompt structure."""

    def test_route_claim_returns_dict(self):
        """route_claim should return a dict with 'route' and 'domain' keys."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"route": "static", "domain": null}'))
        ]

        with patch("src.core.router.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            from src.core.router import route_claim
            result = route_claim("What is GDP?")

            assert "route" in result
            assert "domain" in result
            assert result["route"] in ("static", "dynamic", "invalid")

    def test_invalid_json_returns_invalid(self):
        """If LLM returns invalid JSON, router should default to invalid."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="not valid json"))
        ]

        with patch("src.core.router.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            from src.core.router import route_claim
            result = route_claim("some claim")

            assert result["route"] == "invalid"
