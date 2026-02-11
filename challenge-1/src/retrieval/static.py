"""Static retrieval from pgvector with reranking."""

import logging

from config.settings import settings
from src.core.embeddings import get_embedding
from src.core.reranker import rerank
from src.database.connection import get_session
from src.database.operations import search_documents, search_facts

logger = logging.getLogger(__name__)


def search_static_kb(query: str) -> dict:
    """
    Search the static knowledge base (pgvector) for evidence.

    1. Embed the query.
    2. Search both documents and facts tables.
    3. Rerank combined results.
    4. Check similarity threshold.

    Returns:
        {
            "results": [...],
            "above_threshold": bool,
            "max_similarity": float,
        }
    """
    logger.debug("Searching static KB for: %s", query[:100])

    query_embedding = get_embedding(query)
    session = get_session()

    try:
        # Search both tables
        doc_results = search_documents(
            session, query_embedding, top_k=settings.top_k_retrieval
        )
        fact_results = search_facts(
            session, query_embedding, top_k=settings.top_k_retrieval
        )
    finally:
        session.close()

    # Merge results
    all_results = doc_results + fact_results

    if not all_results:
        logger.debug("No results found in static KB.")
        return {
            "results": [],
            "above_threshold": False,
            "max_similarity": 0.0,
        }

    # Rerank
    reranked = rerank(
        query=query,
        candidates=all_results,
        top_k=settings.top_k_rerank,
    )

    # Determine max similarity from original vector search (before rerank)
    max_similarity = max(r.get("similarity", 0.0) for r in all_results)
    above_threshold = max_similarity >= settings.similarity_threshold

    logger.debug(
        "Static KB: %d results, max similarity=%.4f, above_threshold=%s",
        len(reranked),
        max_similarity,
        above_threshold,
    )

    return {
        "results": reranked,
        "above_threshold": above_threshold,
        "max_similarity": max_similarity,
    }
