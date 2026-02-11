"""Dynamic retrieval orchestrator for real-time data.

Uses OpenAI web_search with allowed_domains for news/finance/govt,
and Open-Meteo API for weather. Domain configuration is read from
config/sources.yaml — no hardcoded URLs.
"""

import logging

from config.settings import get_domain_config
from src.scrapers.weather import WeatherFetcher
from src.scrapers.web_search import search_web

logger = logging.getLogger(__name__)


def search_dynamic(query: str, domain: str | None = None) -> list[dict]:
    """
    Search dynamic (real-time) sources for evidence.

    Args:
        query: The claim or search query.
        domain: The domain to search (news, finance, govt, weather).
                If None, tries all configured domains.

    Returns:
        List of evidence items.
    """
    if domain:
        return _search_single_domain(query, domain)

    # Search all configured domains
    all_results: list[dict] = []
    for d in ("news", "finance", "govt", "weather"):
        cfg = get_domain_config(d)
        if cfg:
            try:
                results = _search_single_domain(query, d)
                all_results.extend(results)
            except Exception as e:
                logger.error("Error searching %s: %s", d, e)
    return all_results


def _search_single_domain(query: str, domain: str) -> list[dict]:
    """Search a single domain using the appropriate method."""
    cfg = get_domain_config(domain)
    if not cfg:
        logger.warning("No config found for domain '%s'.", domain)
        return []

    # Weather uses a dedicated API fetcher (not web search)
    if cfg.get("type") == "api" or domain == "weather":
        logger.info("Using API fetcher for domain '%s'.", domain)
        fetcher = WeatherFetcher()
        return fetcher.search(query)

    # All other domains use OpenAI web search with allowed_domains
    logger.info("Using OpenAI web search for domain '%s'.", domain)
    return search_web(query, domain)
