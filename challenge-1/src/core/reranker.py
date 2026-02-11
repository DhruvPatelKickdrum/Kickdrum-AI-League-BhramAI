"""Reranking logic using a cross-encoder model."""

import logging

from sentence_transformers import CrossEncoder

from config.settings import settings

logger = logging.getLogger(__name__)

_reranker: CrossEncoder | None = None


def _get_reranker() -> CrossEncoder:
    """Lazy-load the cross-encoder reranker model."""
    global _reranker
    if _reranker is None:
        model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"
        logger.debug("Loading reranker model: %s", model_name)
        # Use CPU to avoid MPS/MTLCompilerService crashes on macOS in Gunicorn workers
        # (second request often fails with "Unable to reach MTLCompilerService" when using MPS)
        _reranker = CrossEncoder(model_name, device="cpu")
    return _reranker


def rerank(
    query: str,
    candidates: list[dict],
    top_k: int | None = None,
    content_key: str = "content",
) -> list[dict]:
    """
    Rerank candidate documents using a cross-encoder.

    Args:
        query: The user's claim / query.
        candidates: List of dicts, each with a 'content' key (or specified content_key).
        top_k: Number of top results to return after reranking.
        content_key: Key in the candidate dict that contains the text.

    Returns:
        Reranked list of candidates, each with an added 'rerank_score' field.
    """
    top_k = top_k or settings.top_k_rerank

    if not candidates:
        return []

    reranker = _get_reranker()

    pairs = [(query, c[content_key]) for c in candidates]
    scores = reranker.predict(pairs)

    for candidate, score in zip(candidates, scores):
        candidate["rerank_score"] = float(score)

    ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)

    logger.debug(
        "Reranked %d candidates → top-%d (best score=%.4f)",
        len(candidates),
        top_k,
        ranked[0]["rerank_score"] if ranked else 0.0,
    )

    return ranked[:top_k]
