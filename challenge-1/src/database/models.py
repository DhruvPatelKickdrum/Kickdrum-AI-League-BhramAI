"""SQLAlchemy models for the claim verification knowledge base."""

import datetime
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Fact(Base):
    """Verified, stable facts stored with their embeddings."""

    __tablename__ = "facts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content = Column(Text, nullable=False)
    source_url = Column(String(2048), nullable=True)
    source_title = Column(String(512), nullable=True)
    stored_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=datetime.datetime.utcnow,
    )
    content_hash = Column(String(64), nullable=False, unique=True, index=True)

    # OpenAI text-embedding-3-small produces 1536-dim vectors
    embedding = Column(Vector(1536), nullable=False)

    def __repr__(self) -> str:
        return f"<Fact id={self.id} source={self.source_title!r}>"


class Document(Base):
    """Ingested document chunks (from Docling or other sources)."""

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content = Column(Text, nullable=False)
    source_url = Column(String(2048), nullable=True)
    source_title = Column(String(512), nullable=True)
    chunk_index = Column(String(32), nullable=True)
    ingested_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=datetime.datetime.utcnow,
    )
    content_hash = Column(String(64), nullable=False, unique=True, index=True)

    # OpenAI text-embedding-3-small produces 1536-dim vectors
    embedding = Column(Vector(1536), nullable=False)

    def __repr__(self) -> str:
        return f"<Document id={self.id} source={self.source_title!r}>"


# Create HNSW index for fast approximate nearest-neighbor search
facts_embedding_idx = Index(
    "facts_embedding_idx",
    Fact.embedding,
    postgresql_using="hnsw",
    postgresql_with={"m": 16, "ef_construction": 64},
    postgresql_ops={"embedding": "vector_cosine_ops"},
)

documents_embedding_idx = Index(
    "documents_embedding_idx",
    Document.embedding,
    postgresql_using="hnsw",
    postgresql_with={"m": 16, "ef_construction": 64},
    postgresql_ops={"embedding": "vector_cosine_ops"},
)
