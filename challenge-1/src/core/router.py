"""LLM-based query router for claim classification."""

import json
import logging

from openai import OpenAI

from config.settings import get_llm_temperature, settings

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_PROMPT = """\
You are a query classifier for a claim verification system.

Given a user claim, classify it into one of three categories:
1. "static" - The claim is about a factual question with a settled answer. It can be \
answered from the knowledge base (pgvector). This includes: definitions, historical \
events, past election/sports/award results ("who won X"), established policies, \
anything that has a fixed answer we can store and reuse. Always prefer static for facts \
so we query the KB first; if the fact is already stored we use it without calling live sources.
2. "dynamic" - The claim requires real-time or changing information that is not yet \
in the KB: current weather, today's stock price, "what is happening right now", \
latest breaking news, very recent policy changes that may not be stored yet.
3. "invalid" - The claim is an opinion, subjective, inappropriate, or not verifiable.

If the route is "dynamic", also identify the domain:
- "news" - Current events, breaking news, live incidents
- "finance" - Stock market, GDP, inflation, economic data
- "weather" - Weather conditions, temperature, forecasts
- "govt" - Government policies, regulations, official announcements

Respond ONLY with valid JSON in this exact format:
{"route": "static|dynamic|invalid", "domain": "news|finance|weather|govt|null"}

Examples:
- "What is GDP?" -> {"route": "static", "domain": null}
- "Who won the 2024 US election?" -> {"route": "static", "domain": null}
- "Who won the ICC T20 World Cup 2024?" -> {"route": "static", "domain": null}
- "What is the current inflation rate in India?" -> {"route": "dynamic", "domain": "finance"}
- "Is it going to rain in Mumbai today?" -> {"route": "dynamic", "domain": "weather"}
- "What does the EU AI Act regulate?" -> {"route": "static", "domain": null}
- "What is the best programming language?" -> {"route": "invalid", "domain": null}
- "I think the government is bad" -> {"route": "invalid", "domain": null}
- "What are the latest RBI policy changes?" -> {"route": "dynamic", "domain": "govt"}
- Past event outcomes, sports results, awards -> static (query KB first; if missing, agent will fetch and store).
"""


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
    logger.info("Router response: %s", raw)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse router response: %s", raw)
        return {"route": "invalid", "domain": None}

    route = result.get("route", "invalid")
    domain = result.get("domain")

    if route not in ("static", "dynamic", "invalid"):
        route = "invalid"
    if domain == "null" or domain not in ("news", "finance", "weather", "govt"):
        domain = None

    return {"route": route, "domain": domain}
