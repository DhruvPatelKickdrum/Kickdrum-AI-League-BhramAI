"""Logic for deciding whether to store retrieved information as stable facts."""

import json
import logging

from openai import OpenAI
from sqlalchemy import select

from config.settings import get_llm_temperature, settings
from src.agent.prompts import STABILITY_PROMPT
from src.core.embeddings import get_embedding
from src.database.connection import get_session
from src.database.models import Fact
from src.database.operations import insert_fact
from src.utils.hashing import compute_content_hash

logger = logging.getLogger(__name__)


def evaluate_and_store(
    claim: str,
    evidence: list[dict],
    domain: str | None = None,
) -> dict:
    """
    Evaluate if evidence is stable enough to store, and if so, store it.

    Args:
        claim: The original claim.
        evidence: List of evidence dicts.
        domain: The domain (news, finance, weather, govt).

    Returns:
        {"stored": bool, "fact": str | None}
    """
    # Weather is never stored
    if domain == "weather":
        logger.debug("Weather data is ephemeral, not storing.")
        return {"stored": False, "fact": None}

    if not evidence:
        return {"stored": False, "fact": None}

    # Combine top evidence for evaluation
    evidence_text = "\n".join(
        f"- {e.get('content', '')}" for e in evidence[:3]
    )

    client = OpenAI(api_key=settings.openai_api_key)

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": STABILITY_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Claim: {claim}\n"
                    f"Domain: {domain or 'general'}\n"
                    f"Evidence:\n{evidence_text}"
                ),
            },
        ],
        temperature=get_llm_temperature(),
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse stability response: %s", raw)
        return {"stored": False, "fact": None}

    is_stable = result.get("is_stable", False)
    normalized_fact = result.get("normalized_fact")

    if not is_stable or not normalized_fact:
        logger.debug("Evidence is not stable enough to store.")
        return {"stored": False, "fact": None}

    # Skip re-embedding and insert if fact already in KB (e.g. evidence came from static KB)
    content_hash = compute_content_hash(normalized_fact)
    session = get_session()
    try:
        existing = session.execute(
            select(Fact).where(Fact.content_hash == content_hash)
        ).scalar_one_or_none()
        if existing:
            logger.debug("Fact already in knowledge base, skipping re-embedding and insert.")
            return {"stored": True, "fact": normalized_fact}
    finally:
        session.close()

    # Store the normalized fact (embed only when not already present)
    logger.debug("Storing stable fact: %s", normalized_fact[:100])
    embedding = get_embedding(normalized_fact)
    session = get_session()
    try:
        source_url = evidence[0].get("source_url") if evidence else None
        source_title = evidence[0].get("source_title") if evidence else None

        fact = insert_fact(
            session=session,
            content=normalized_fact,
            embedding=embedding,
            source_url=source_url,
            source_title=source_title,
        )
        stored = fact is not None
    except Exception as e:
        logger.error("Failed to store fact: %s", e)
        stored = False
    finally:
        session.close()

    return {"stored": stored, "fact": normalized_fact if stored else None}
