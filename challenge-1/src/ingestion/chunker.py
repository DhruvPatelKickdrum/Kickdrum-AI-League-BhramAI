"""Text chunking logic for ingestion into the vector database."""

import logging

import tiktoken

from config.settings import settings

logger = logging.getLogger(__name__)


def count_tokens(text: str, model: str = "cl100k_base") -> int:
    """Count the number of tokens in a text string."""
    enc = tiktoken.get_encoding(model)
    return len(enc.encode(text))


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[str]:
    """
    Split text into overlapping chunks based on token count.

    Uses sentence boundaries for cleaner splits when possible.
    """
    chunk_size = chunk_size or settings.chunk_size
    chunk_overlap = chunk_overlap or settings.chunk_overlap

    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)

    if len(tokens) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0

    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text_str = enc.decode(chunk_tokens)
        chunks.append(chunk_text_str.strip())

        if end >= len(tokens):
            break

        start = end - chunk_overlap

    logger.info("Split text into %d chunks (size=%d, overlap=%d)", len(chunks), chunk_size, chunk_overlap)
    return chunks


def chunk_documents(documents: list[dict]) -> list[dict]:
    """
    Chunk a list of parsed documents.

    Input: [{"text": ..., "source_url": ..., "title": ...}]
    Output: [{"text": ..., "source_url": ..., "title": ..., "chunk_index": "0"}, ...]
    """
    chunked: list[dict] = []

    for doc in documents:
        text = doc.get("text", "")
        if not text.strip():
            continue

        chunks = chunk_text(text)

        for i, chunk in enumerate(chunks):
            chunked.append({
                "text": chunk,
                "source_url": doc.get("source_url"),
                "title": doc.get("title"),
                "chunk_index": str(i),
            })

    logger.info("Total chunked documents: %d", len(chunked))
    return chunked
