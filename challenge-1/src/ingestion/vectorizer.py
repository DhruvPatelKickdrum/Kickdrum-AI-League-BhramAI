"""Embed text chunks and store them in pgvector."""

import logging

from src.core.embeddings import get_embeddings
from src.database.connection import get_session
from src.database.operations import insert_document

logger = logging.getLogger(__name__)


def vectorize_and_store(chunks: list[dict]) -> int:
    """
    Embed a list of text chunks and store them in the documents table.

    Input: [{"text": ..., "source_url": ..., "title": ..., "chunk_index": ...}]
    Returns: number of newly inserted chunks.
    """
    if not chunks:
        logger.warning("No chunks to vectorize.")
        return 0

    texts = [c["text"] for c in chunks]

    logger.info("Generating embeddings for %d chunks...", len(texts))
    embeddings = get_embeddings(texts)

    inserted = 0
    session = get_session()

    try:
        for chunk, embedding in zip(chunks, embeddings):
            doc = insert_document(
                session=session,
                content=chunk["text"],
                embedding=embedding,
                source_url=chunk.get("source_url"),
                source_title=chunk.get("title"),
                chunk_index=chunk.get("chunk_index"),
            )
            if doc is not None:
                inserted += 1
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    logger.info("Inserted %d new document chunks (of %d total).", inserted, len(chunks))
    return inserted
