"""Dynamic retrieval orchestrator for real-time data.

Uses Firecrawl (when FIRECRAWL_API_KEY is set) or OpenAI web_search for news/finance/govt/science,
and Open-Meteo API for weather. Domain configuration is read from config/sources.yaml.

When searching a domain with multiple sources, we query sources in parallel (up to max_domains)
to reduce wall-clock time, and stop once we have enough evidence.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from config.settings import get_allowed_domains, get_domain_config, settings
from src.scrapers.weather import WeatherFetcher
from src.scrapers.web_search import search_web

logger = logging.getLogger(__name__)

# Stop once we have at least this many evidence items
MIN_EVIDENCE_FOR_EARLY_EXIT = 1
# Max domains to try per category (avoids 7+ sequential calls when first few return nothing)
MAX_DOMAINS_PER_CATEGORY = 2
# Max parallel workers for domain search
MAX_PARALLEL_DOMAINS = 3


def search_dynamic(
    query: str,
    domain: str | None = None,
    *,
    domains: list[str] | None = None,
) -> list[dict]:
    """
    Search dynamic (real-time) sources for evidence.

    Args:
        query: The claim or search query.
        domain: The domain to search (news, finance, govt, weather, science).
                If set, only this domain is searched.
        domains: When domain is None, limit to these domains (e.g. skip weather).
                 Example: domains=["news", "science", "finance", "govt"].
                 If None, all configured domains are tried.

    Returns:
        List of evidence items.
    """
    if domain:
        return _search_single_domain(query, domain)

    to_search = domains if domains is not None else ["news", "finance", "govt", "science", "weather"]
    all_results: list[dict] = []
    for d in to_search:
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

    use_firecrawl = getattr(settings, "firecrawl_api_key", None) and str(settings.firecrawl_api_key or "").strip()
    # Agentic = Firecrawl Agent (app.agent()) + our LLM validation. Set FIRECRAWL_USE_AGENT=true to use.
    use_agent = use_firecrawl and getattr(settings, "firecrawl_use_agent", False)
    domains_to_try = allowed[:MAX_DOMAINS_PER_CATEGORY]

    # Firecrawl: agentic (if FIRECRAWL_USE_AGENT) or search → LLM filter links → scrape selected URLs
    if use_firecrawl:
        try:
            if use_agent:
                from src.scrapers.firecrawl_search import search_firecrawl_agent
                all_results = search_firecrawl_agent(
                    query, domain,
                    allowed_domains_override=domains_to_try,
                    claim_context=query,
                )
            else:
                from src.scrapers.firecrawl_search import search_firecrawl
                all_results = search_firecrawl(
                    query, domain,
                    allowed_domains_override=domains_to_try,
                    claim_context=query,
                )
            logger.debug("Domain '%s': Firecrawl → %d evidence items.", domain, len(all_results))
            return all_results
        except Exception as e:
            logger.warning("Firecrawl failed for domain '%s', falling back to OpenAI: %s", domain, e)

    def search_one(source_domain: str) -> list[dict]:
        logger.debug("Using OpenAI web search for domain '%s', source=%s.", domain, source_domain)
        return search_web(query, domain, allowed_domains_override=[source_domain])

    all_results = []
    workers = min(MAX_PARALLEL_DOMAINS, len(domains_to_try))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_domain = {executor.submit(search_one, d): d for d in domains_to_try}
        for future in as_completed(future_to_domain):
            try:
                results = future.result()
                all_results.extend(results)
                # Early exit once we have enough evidence
                if len(all_results) >= MIN_EVIDENCE_FOR_EARLY_EXIT:
                    for f in future_to_domain:
                        f.cancel()
                    break
            except Exception as e:
                logger.warning("Search failed for %s: %s", future_to_domain.get(future), e)

    logger.debug("Domain '%s': %d domains in parallel → %d evidence items.", domain, len(domains_to_try), len(all_results))
    return all_results
