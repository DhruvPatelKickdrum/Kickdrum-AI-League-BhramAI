"""Tests for agent tool definitions."""

import pytest

from src.agent.tools import ALL_TOOLS


class TestToolDefinitions:
    """Test that all tools are properly defined."""

    def test_all_tools_registered(self):
        """ALL_TOOLS should contain all expected tools."""
        tool_names = {t.name for t in ALL_TOOLS}
        expected = {
            "route_claim",
            "search_static_kb",
            "scrape_news",
            "scrape_finance",
            "scrape_government",
            "fetch_weather",
            "store_fact",
            "verify_and_synthesize",
        }
        assert expected == tool_names

    def test_tools_have_descriptions(self):
        """All tools should have non-empty descriptions."""
        for tool in ALL_TOOLS:
            assert tool.description, f"Tool {tool.name} has no description"
