"""Tool definitions for the LangGraph agent.

All domain-specific search tools delegate to OpenAI web search with
allowed_domains configured in config/sources.yaml. No hardcoded URLs.
"""

import logging
from typing import Annotated

from langchain_core.tools import tool

from config.settings import get_allowed_domains
from src.core.router import route_claim as _route_claim
from src.core.verification import verify_claim as _verify_claim
from src.retrieval.dynamic import search_dynamic
from src.retrieval.static import search_static_kb as _search_static_kb
from src.retrieval.store import evaluate_and_store

logger = logging.getLogger(__name__)


@tool
def route_claim(claim: Annotated[str, "The claim text to classify"]) -> dict:
    """Classify a claim as static, dynamic, or invalid, and identify its domain."""
    logger.debug("Tool: route_claim(%s)", claim[:80])
    return _route_claim(claim)


@tool
def search_static_kb(query: Annotated[str, "Search query for the knowledge base"]) -> dict:
    """Search the local pgvector knowledge base for verified facts and documents."""
    logger.debug("Tool: search_static_kb(%s)", query[:80])
    result = _search_static_kb(query)
    # Simplify for the agent — return just the essentials
    simplified_results = [
        {
            "content": r["content"],
            "source_url": r.get("source_url", ""),
            "source_title": r.get("source_title", ""),
            "similarity": r.get("similarity", 0.0),
        }
        for r in result["results"]
    ]
    return {
        "results": simplified_results,
        "above_threshold": result["above_threshold"],
        "max_similarity": result["max_similarity"],
    }


@tool
def scrape_news(query: Annotated[str, "Search query for news articles"]) -> list[dict]:
    """Search configured news sources (e.g. BBC, ANI) via OpenAI web search for current articles."""
    logger.debug("Tool: scrape_news(%s) domains=%s", query[:80], get_allowed_domains("news"))
    return search_dynamic(query, domain="news")


@tool
def scrape_finance(query: Annotated[str, "Search query for financial data"]) -> list[dict]:
    """Search configured finance sources (e.g. Livemint) via OpenAI web search for market data."""
    logger.debug("Tool: scrape_finance(%s) domains=%s", query[:80], get_allowed_domains("finance"))
    return search_dynamic(query, domain="finance")


@tool
def scrape_government(query: Annotated[str, "Search query for government policies"]) -> list[dict]:
    """Search configured government sources (e.g. RBI, IBEF) via OpenAI web search for policies."""
    logger.debug("Tool: scrape_government(%s) domains=%s", query[:80], get_allowed_domains("govt"))
    return search_dynamic(query, domain="govt")


@tool
def fetch_weather(query: Annotated[str, "Weather query including location"]) -> list[dict]:
    """Get current weather data for a location using Open-Meteo API (configured in sources.yaml)."""
    logger.debug("Tool: fetch_weather(%s)", query[:80])
    return search_dynamic(query, domain="weather")


@tool
def scrape_science(query: Annotated[str, "Search query for scientific or general factual claims"]) -> list[dict]:
    """Search configured science/reference sources (e.g. Britannica, Wikipedia) for scientific facts and definitions."""
    logger.debug("Tool: scrape_science(%s) domains=%s", query[:80], get_allowed_domains("science"))
    return search_dynamic(query, domain="science")


# Minimum evidence items from Wikipedia/science before we skip news
_MIN_HISTORICAL_SCIENCE_THRESHOLD = 2


@tool
def search_historical(query: Annotated[str, "Search query for historical events, dates, or figures"]) -> list[dict]:
    """For historical claims: search Wikipedia and reference sources first; if insufficient, then search news. Use this when the routed domain is 'historical'."""
    logger.debug("Tool: search_historical(%s)", query[:80])
    science_results = search_dynamic(query, domain="science")
    if len(science_results) >= _MIN_HISTORICAL_SCIENCE_THRESHOLD:
        logger.debug("search_historical: got %d from science/Wikipedia, skipping news.", len(science_results))
        return science_results
    news_results = search_dynamic(query, domain="news")
    combined = science_results + news_results
    logger.debug("search_historical: science=%d, news=%d, total=%d.", len(science_results), len(news_results), len(combined))
    return combined


@tool
def store_fact(
    claim: Annotated[str, "The original claim"],
    evidence: Annotated[list[dict], "List of evidence items with content, source_url, source_title"],
    domain: Annotated[str, "The domain: news, finance, govt, weather, science, historical, or null"],
) -> dict:
    """Evaluate if evidence is stable enough to store in the knowledge base, and store if yes."""
    logger.debug("Tool: store_fact(domain=%s)", domain)
    return evaluate_and_store(claim, evidence, domain)


@tool
def verify_and_synthesize(
    claim: Annotated[str, "The original claim to verify"],
    evidence: Annotated[
        list[dict],
        "Gathered evidence items with content, source_url, source_title. Pass empty list if no evidence found.",
    ] = None,
) -> dict:
    """Verify a claim against evidence and produce a verdict with citations."""
    if evidence is None:
        evidence = []
    logger.debug("Tool: verify_and_synthesize(%s) evidence_count=%d", claim[:80], len(evidence))
    return _verify_claim(claim, evidence)


# All tools available to the agent
ALL_TOOLS = [
    route_claim,
    search_static_kb,
    scrape_news,
    scrape_finance,
    scrape_government,
    scrape_science,
    fetch_weather,
    search_historical,
    store_fact,
    verify_and_synthesize,
]
