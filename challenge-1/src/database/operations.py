"""CRUD operations for the vector database."""

import logging
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.database.models import Document, Fact
from src.utils.hashing import compute_content_hash

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Document operations
# ---------------------------------------------------------------------------

def search_documents(
    session: Session,
    query_embedding: list[float],
    top_k: int = 20,
) -> list[dict]:
    """Search documents by cosine similarity and return results with scores."""
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
    sql = text("""
        SELECT
            id, content, source_url, source_title, chunk_index,
            1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM documents
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :top_k
    """)
    rows = session.execute(sql, {"embedding": embedding_str, "top_k": top_k}).fetchall()
    return [
        {
            "id": str(row.id),
            "content": row.content,
            "source_url": row.source_url,
            "source_title": row.source_title,
            "chunk_index": row.chunk_index,
            "similarity": float(row.similarity),
        }
        for row in rows
    ]


def insert_document(
    session: Session,
    content: str,
    embedding: list[float],
    source_url: str | None = None,
    source_title: str | None = None,
    chunk_index: str | None = None,
) -> Optional[Document]:
    """Insert a document chunk if not already present (deduplicate by hash)."""
    content_hash = compute_content_hash(content)

    existing = session.execute(
        select(Document).where(Document.content_hash == content_hash)
    ).scalar_one_or_none()

    if existing:
        logger.debug("Document chunk already exists (hash=%s), skipping.", content_hash[:12])
        return None

    doc = Document(
        content=content,
        embedding=embedding,
        source_url=source_url,
        source_title=source_title,
        chunk_index=chunk_index,
        content_hash=content_hash,
    )
    session.add(doc)
    session.commit()
    return doc


# ---------------------------------------------------------------------------
# Fact operations
# ---------------------------------------------------------------------------

def search_facts(
    session: Session,
    query_embedding: list[float],
    top_k: int = 20,
) -> list[dict]:
    """Search stored facts by cosine similarity."""
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
    sql = text("""
        SELECT
            id, content, source_url, source_title,
            1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM facts
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :top_k
    """)
    rows = session.execute(sql, {"embedding": embedding_str, "top_k": top_k}).fetchall()
    return [
        {
            "id": str(row.id),
            "content": row.content,
            "source_url": row.source_url,
            "source_title": row.source_title,
            "similarity": float(row.similarity),
        }
        for row in rows
    ]


def insert_fact(
    session: Session,
    content: str,
    embedding: list[float],
    source_url: str | None = None,
    source_title: str | None = None,
) -> Optional[Fact]:
    """Insert a normalized fact if not already present (deduplicate by hash)."""
    content_hash = compute_content_hash(content)

    existing = session.execute(
        select(Fact).where(Fact.content_hash == content_hash)
    ).scalar_one_or_none()

    if existing:
        logger.debug("Fact already exists (hash=%s), skipping.", content_hash[:12])
        return None

    fact = Fact(
        content=content,
        embedding=embedding,
        source_url=source_url,
        source_title=source_title,
        content_hash=content_hash,
    )
    session.add(fact)
    session.commit()
    return fact
