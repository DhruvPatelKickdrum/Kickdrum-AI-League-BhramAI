"""Web search scraper using OpenAI's built-in web_search tool with domain filtering."""

import logging
import re

from openai import OpenAI

from config.settings import get_allowed_domains, get_search_instructions, settings
from src.scrapers.schemas import SearchResult

logger = logging.getLogger(__name__)


def _normalize_domain(domain: str) -> str:
    """Strip scheme and trailing slashes; OpenAI expects bare hostnames e.g. bbc.com."""
    s = (domain or "").strip()
    s = re.sub(r"^https?://", "", s, flags=re.IGNORECASE)
    s = s.rstrip("/")
    return s or domain


def search_web(
    query: str,
    domain: str,
    *,
    allowed_domains_override: list[str] | None = None,
) -> list[dict]:
    """
    Search the web for evidence using OpenAI's web_search tool.

    Uses allowed_domains from config/sources.yaml to restrict results
    to trusted sources for the given domain. If allowed_domains_override
    is provided, only those domains are queried (e.g. one domain at a time).

    Args:
        query: The search query / claim.
        domain: The domain category (news, finance, govt).
        allowed_domains_override: Optional subset of domains to search; if None, use all configured.

    Returns:
        List of evidence dicts: [{"content", "source_url", "source_title", "date"}]
    """
    raw_allowed = allowed_domains_override or get_allowed_domains(domain)
    allowed = [d for d in (_normalize_domain(d) for d in raw_allowed) if d]
    instructions = get_search_instructions(domain)

    if not allowed:
        logger.warning("No allowed domains configured for '%s'.", domain)
        return []

    logger.debug(
        "Web search [%s] query=%s, domains=%s",
        domain, query[:80], allowed,
    )

    if not instructions:
        instructions = (
            "Search the web for factual information about the following query. "
            "For each piece of information, cite the specific source URL."
        )

    client = OpenAI(api_key=settings.openai_api_key)

    # Build tool spec: try with allowed_domains first; some models don't support filters
    tool_spec = {
        "type": "web_search",
        "filters": {"allowed_domains": allowed},
    }

    try:
        response = client.responses.parse(
            model=settings.llm_model,
            tools=[tool_spec],
            tool_choice="auto",
            include=["web_search_call.action.sources"],
            input=query,
            instructions=instructions,
            text_format=SearchResult,
        )
    except Exception as e:
        err_str = str(e).lower()
        if "filters" in err_str and ("not supported" in err_str or "400" in err_str):
            logger.warning(
                "Model does not support web_search filters; retrying without domain restriction."
            )
            try:
                response = client.responses.parse(
                    model=settings.llm_model,
                    tools=[{"type": "web_search"}],
                    tool_choice="auto",
                    include=["web_search_call.action.sources"],
                    input=query,
                    instructions=instructions + f" Prefer sources from: {', '.join(allowed)}.",
                    text_format=SearchResult,
                )
            except Exception as e2:
                logger.error("OpenAI web search failed for [%s]: %s", domain, e2)
                return []
        else:
            logger.error("OpenAI web search failed for [%s]: %s", domain, e)
            return []

    # Parse the structured output
    parsed: SearchResult | None = response.output_parsed

    if parsed is None:
        logger.warning("No structured output from web search for [%s].", domain)
        # Fall back: try to extract from raw text output
        return _extract_from_raw(response, domain)

    # Cap results per source to avoid sending too many items downstream
    MAX_RESULTS_PER_SOURCE = 3
    results = [
        {
            "content": ev.content,
            "source_url": ev.source_url,
            "source_title": ev.source_title,
            "date": ev.date,
        }
        for ev in parsed.evidence[:MAX_RESULTS_PER_SOURCE]
    ]

    logger.debug("Web search [%s] returned %d evidence items (capped from %d).", domain, len(results), len(parsed.evidence))
    return results


def _extract_from_raw(response, domain: str) -> list[dict]:
    """
    Fallback: extract evidence from raw response output items when
    structured parsing doesn't produce results.
    """
    results: list[dict] = []

    for item in response.output:
        item_type = getattr(item, "type", None)
        if item_type == "web_search_call":
            results.extend(_extract_web_search_sources(item, domain))
        elif item_type == "message":
            results.extend(_extract_message_content(item, domain))

    logger.debug("Fallback extraction [%s] returned %d items.", domain, len(results))
    return results


def _extract_web_search_sources(item, domain: str) -> list[dict]:
    """Extract source citations from a web_search_call output item."""
    sources = getattr(getattr(item, "action", None), "sources", None)
    if not sources:
        return []
    return [
        {
            "content": getattr(src, "snippet", ""),
            "source_url": getattr(src, "url", ""),
            "source_title": getattr(src, "title", f"{domain} source"),
            "date": None,
        }
        for src in sources
    ]


def _extract_message_content(item, domain: str) -> list[dict]:
    """Extract text content from a message output item."""
    results: list[dict] = []
    for block in getattr(item, "content", []):
        text = getattr(block, "text", "")
        if text:
            results.append({
                "content": text,
                "source_url": "",
                "source_title": f"{domain} web search",
                "date": None,
            })
    return results
