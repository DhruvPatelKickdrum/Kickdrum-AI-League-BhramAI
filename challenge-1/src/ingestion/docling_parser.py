"""Parse documents using Docling for structured text extraction."""

import logging
from typing import Optional

from docling.document_converter import DocumentConverter

logger = logging.getLogger(__name__)


def parse_url(url: str) -> list[dict]:
    """
    Parse a URL using Docling and return structured text chunks.

    Returns a list of dicts: [{"text": ..., "source_url": ..., "title": ...}]
    """
    logger.info("Parsing URL with Docling: %s", url)

    converter = DocumentConverter()
    result = converter.convert(url)

    doc = result.document
    title = doc.name or url

    # Export the full document as markdown text
    full_text = doc.export_to_markdown()

    if not full_text or not full_text.strip():
        logger.warning("Docling returned empty content for %s", url)
        return []

    logger.info("Parsed %d characters from %s", len(full_text), url)

    return [{
        "text": full_text,
        "source_url": url,
        "title": title,
    }]


def parse_multiple_urls(urls: list[str]) -> list[dict]:
    """Parse multiple URLs and aggregate results."""
    all_docs: list[dict] = []
    for url in urls:
        try:
            docs = parse_url(url)
            all_docs.extend(docs)
        except Exception as e:
            logger.error("Failed to parse %s: %s", url, e)
    return all_docs
