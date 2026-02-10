"""Content hashing for deduplication."""

import hashlib


def compute_content_hash(content: str) -> str:
    """Compute a SHA-256 hash of the content for deduplication."""
    normalized = content.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
