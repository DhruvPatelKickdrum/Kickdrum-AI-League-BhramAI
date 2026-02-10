#!/usr/bin/env python3
"""Initialize the database: create pgvector extension and tables."""

import sys
import os

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.logging_config import setup_logging
from config.settings import settings


def main() -> None:
    setup_logging(settings.log_level)

    from src.database.connection import init_db

    print("Initializing database...")
    print(f"  URL: {settings.database_url}")

    init_db()

    print("Database initialized successfully!")
    print("  - pgvector extension enabled")
    print("  - 'facts' table created")
    print("  - 'documents' table created")
    print("  - HNSW indexes created")


if __name__ == "__main__":
    main()
