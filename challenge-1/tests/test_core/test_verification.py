"""Tests for claim verification logic."""

import pytest
from unittest.mock import patch, MagicMock


class TestVerification:
    """Test verification logic."""

    def test_empty_evidence_returns_not_enough(self):
        """With no evidence, should return 'Not Enough Evidence'."""
        from src.core.verification import verify_claim

        result = verify_claim("Some claim", [])

        assert result["verdict"] == "Not Enough Evidence"
        assert result["citations"] == []

    def test_verify_returns_dict_with_required_keys(self):
        """verify_claim should return dict with verdict, reasoning, citations."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"verdict": "Supported", "reasoning": "Evidence supports claim.", "citations": []}'
                )
            )
        ]

        with patch("src.core.verification.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            from src.core.verification import verify_claim

            result = verify_claim("test claim", [{"content": "test evidence", "source_url": "http://example.com"}])

            assert "verdict" in result
            assert "reasoning" in result
            assert "citations" in result


class TestSynthesis:
    """Test response synthesis."""

    def test_synthesize_formats_response(self):
        """synthesize_response should produce a formatted string."""
        from src.core.verification import synthesize_response

        result = synthesize_response(
            claim="Test claim",
            verification_result={
                "verdict": "Supported",
                "reasoning": "Evidence clearly supports the claim.",
                "citations": [
                    {
                        "source_url": "http://example.com",
                        "source_title": "Example",
                        "relevant_snippet": "relevant text",
                    }
                ],
            },
        )

        assert "Supported" in result
        assert "Example" in result
        assert "http://example.com" in result
