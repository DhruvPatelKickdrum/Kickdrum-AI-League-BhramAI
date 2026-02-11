"""Dynamic retrieval orchestrator for real-time data.

Uses Firecrawl (when FIRECRAWL_API_KEY is set) or OpenAI web_search for news/finance/govt/science,
and Open-Meteo API for weather. Domain configuration is read from config/sources.yaml.

When searching a domain with multiple sources, we try one source at a time and stop
as soon as we have enough evidence (early exit).
"""

import logging

from config.settings import get_allowed_domains, get_domain_config, settings
from src.scrapers.weather import WeatherFetcher
from src.scrapers.web_search import search_web

logger = logging.getLogger(__name__)

# Stop querying more domains once we have at least this many evidence items from one/batch
MIN_EVIDENCE_FOR_EARLY_EXIT = 2


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
    for d in ("news", "finance", "govt", "science", "weather"):
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
        logger.debug("Using API fetcher for domain '%s'.", domain)
        fetcher = WeatherFetcher()
        return fetcher.search(query)

    # Web search: try one source domain at a time; stop when we have enough evidence
    allowed = get_allowed_domains(domain)
    if not allowed:
        logger.warning("No allowed domains for '%s'.", domain)
        return []

    all_results: list[dict] = []
    use_firecrawl = getattr(settings, "firecrawl_api_key", None) and str(settings.firecrawl_api_key or "").strip()

    for single_domain in allowed:
        if use_firecrawl:
            try:
                from src.scrapers.firecrawl_search import search_firecrawl
                results = search_firecrawl(query, domain, allowed_domains_override=[single_domain])
            except Exception as e:
                logger.warning("Firecrawl failed, falling back to OpenAI web search: %s", e)
                results = search_web(query, domain, allowed_domains_override=[single_domain])
        else:
            logger.debug("Using OpenAI web search for domain '%s', source=%s.", domain, single_domain)
            results = search_web(query, domain, allowed_domains_override=[single_domain])
        all_results.extend(results)
        if len(all_results) >= MIN_EVIDENCE_FOR_EARLY_EXIT:
            logger.debug(
                "Early exit: got %d evidence items (>= %d), skipping remaining sources for '%s'.",
                len(all_results),
                MIN_EVIDENCE_FOR_EARLY_EXIT,
                domain,
            )
            return all_results

    return all_results
