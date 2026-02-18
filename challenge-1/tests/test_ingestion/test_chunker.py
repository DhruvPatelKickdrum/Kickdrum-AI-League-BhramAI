"""Tests for text chunking."""

import pytest

from src.ingestion.chunker import chunk_text, count_tokens


class TestChunker:
    """Test chunking logic."""

    def test_short_text_single_chunk(self):
        """Text shorter than chunk_size should produce one chunk."""
        text = "This is a short text."
        chunks = chunk_text(text, chunk_size=512, chunk_overlap=50)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_multiple_chunks(self):
        """Long text should produce multiple overlapping chunks."""
        text = "word " * 1000  # ~1000 tokens
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=10)
        assert len(chunks) > 1

    def test_count_tokens(self):
        tokens = count_tokens("Hello world")
        assert tokens >= 2
