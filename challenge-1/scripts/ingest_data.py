#!/usr/bin/env python3
"""Ingest EU AI Act website data into pgvector using Docling."""

import sys
import os

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.logging_config import setup_logging
from config.settings import settings

# Key pages from the EU AI Act website to ingest
EU_AI_ACT_URLS = [
    "https://artificialintelligenceact.eu/high-level-summary/",
    "https://artificialintelligenceact.eu/ai-act-implementation-timelines-next-steps/",
]


def main() -> None:
    setup_logging(settings.log_level)

    from src.database.connection import init_db
    from src.ingestion.chunker import chunk_documents
    from src.ingestion.docling_parser import parse_multiple_urls
    from src.ingestion.vectorizer import vectorize_and_store

    # Step 0: Ensure DB is ready
    print("Ensuring database is initialized...")
    init_db()

    # Step 1: Parse URLs with Docling
    print(f"\nParsing {len(EU_AI_ACT_URLS)} URLs with Docling...")
    for url in EU_AI_ACT_URLS:
        print(f"  - {url}")

    documents = parse_multiple_urls(EU_AI_ACT_URLS)
    print(f"Parsed {len(documents)} documents.")

    if not documents:
        print("No documents parsed. Exiting.")
        return

    # Step 2: Chunk documents
    print("\nChunking documents...")
    chunks = chunk_documents(documents)
    print(f"Created {len(chunks)} chunks.")

    # Step 3: Embed and store in pgvector
    print("\nEmbedding and storing in pgvector...")
    inserted = vectorize_and_store(chunks)
    print(f"\nDone! Inserted {inserted} new chunks into the database.")


if __name__ == "__main__":
    main()
