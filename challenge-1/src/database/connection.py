"""Database connection and session management."""

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from config.settings import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_session() -> Session:
    """Create a new database session."""
    return SessionLocal()


def init_db() -> None:
    """Initialize the database: create extensions and tables."""
    from src.database.models import Base  # noqa: import here to avoid circular

    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
        logger.info("pgvector extension ensured.")

    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created.")
