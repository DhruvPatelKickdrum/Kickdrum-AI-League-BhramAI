"""Text normalization and cleaning utilities."""

import re


def normalize_text(text: str) -> str:
    """Clean and normalize text for processing."""
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    # Strip leading/trailing whitespace
    text = text.strip()
    return text


def truncate_text(text: str, max_chars: int = 8080) -> str:
    """Truncate text to a maximum number of characters."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."
