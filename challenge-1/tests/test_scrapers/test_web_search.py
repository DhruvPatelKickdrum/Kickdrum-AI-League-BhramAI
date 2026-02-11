"""Tests for the OpenAI web search scraper."""

import pytest
from unittest.mock import patch, MagicMock

from src.scrapers.schemas import SearchEvidence, SearchResult


class TestWebSearch:
    """Test the web search scraper."""

    def test_search_web_with_valid_domain(self):
        """search_web should call OpenAI with allowed_domains from config."""
        mock_evidence = SearchEvidence(
            content="The EU AI Act bans social scoring.",
            source_url="https://bbc.com/news/ai-act",
            source_title="BBC News",
            date="2024-03-01",
        )
        mock_result = SearchResult(
            evidence=[mock_evidence],
            summary="Found information about the EU AI Act.",
        )

        mock_response = MagicMock()
        mock_response.output_parsed = mock_result

        with patch("src.scrapers.web_search.OpenAI") as mock_openai, \
             patch("src.scrapers.web_search.get_allowed_domains", return_value=["bbc.com"]), \
             patch("src.scrapers.web_search.get_search_instructions", return_value="Search news."):
            mock_client = MagicMock()
            mock_client.responses.parse.return_value = mock_response
            mock_openai.return_value = mock_client

            from src.scrapers.web_search import search_web
            results = search_web("EU AI Act bans social scoring", "news")

            assert len(results) == 1
            assert results[0]["content"] == "The EU AI Act bans social scoring."
            assert results[0]["source_url"] == "https://bbc.com/news/ai-act"

    def test_search_web_no_configured_domains(self):
        """search_web should return empty list if no domains configured."""
        with patch("src.scrapers.web_search.get_allowed_domains", return_value=[]):
            from src.scrapers.web_search import search_web
            results = search_web("test query", "unknown_domain")
            assert results == []


class TestSearchSchemas:
    """Test Pydantic schemas for structured output."""

    def test_search_evidence_model(self):
        ev = SearchEvidence(
            content="test content",
            source_url="http://example.com",
            source_title="Example",
        )
        assert ev.date is None
        assert ev.content == "test content"

    def test_search_result_model(self):
        result = SearchResult(
            evidence=[
                SearchEvidence(
                    content="test",
                    source_url="http://example.com",
                    source_title="Example",
                )
            ],
            summary="Found one result.",
        )
        assert len(result.evidence) == 1
