"""LLM-based query router for claim classification."""

import json
import logging

from openai import OpenAI

from config.settings import get_llm_temperature, settings
from src.agent.prompts import ROUTER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def route_claim(claim: str) -> dict:
    """
    Route a claim to static, dynamic, or invalid with an optional domain.

    Returns: {"route": "static"|"dynamic"|"invalid", "domain": str|None}
    """
    client = OpenAI(api_key=settings.openai_api_key)

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": claim},
        ],
        temperature=get_llm_temperature(),
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()
    logger.debug("Router response: %s", raw)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse router response: %s", raw)
        return {"route": "invalid", "domain": None}

    route = result.get("route", "invalid")
    domain = result.get("domain")

    if route not in ("static", "dynamic", "invalid"):
        route = "invalid"
    if domain == "null" or domain not in ("news", "finance", "weather", "govt", "science", "historical"):
        domain = None

    return {"route": route, "domain": domain}
