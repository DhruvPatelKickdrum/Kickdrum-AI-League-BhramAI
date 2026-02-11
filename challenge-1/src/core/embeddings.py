"""Embedding model wrapper using OpenAI."""

import logging

from openai import OpenAI

from config.settings import settings

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def get_embedding(text: str) -> list[float]:
    """Get embedding for a single text string."""
    client = _get_client()
    response = client.embeddings.create(
        input=[text],
        model=settings.embedding_model,
    )
    return response.data[0].embedding


def get_embeddings(texts: list[str], batch_size: int = 100) -> list[list[float]]:
    """
    Get embeddings for a list of texts.

    Batches requests to stay within API limits.
    """
    client = _get_client()
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        logger.debug("Embedding batch %d-%d of %d", i, i + len(batch), len(texts))
        response = client.embeddings.create(
            input=batch,
            model=settings.embedding_model,
        )
        batch_embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(batch_embeddings)

    return all_embeddings
