"""Web search via Firecrawl API — faster alternative to OpenAI web_search with domain filtering."""

import logging
import re

from config.settings import get_allowed_domains, settings

logger = logging.getLogger(__name__)


def _normalize_domain(domain: str) -> str:
    """Strip scheme and trailing slashes."""
    s = (domain or "").strip()
    s = re.sub(r"^https?://", "", s, flags=re.IGNORECASE)
    return s.rstrip("/") or domain


def search_firecrawl(
    query: str,
    domain: str,
    *,
    allowed_domains_override: list[str] | None = None,
) -> list[dict]:
    """
    Search the web using Firecrawl's search API. Uses site: operator for domain filtering.
    Returns same evidence format as web_search: [{"content", "source_url", "source_title", "date"}].
    """
    if not getattr(settings, "firecrawl_api_key", None) or not settings.firecrawl_api_key.strip():
        return []

    raw_allowed = allowed_domains_override or get_allowed_domains(domain)
    allowed = [d for d in (_normalize_domain(d) for d in raw_allowed) if d]
    if not allowed:
        logger.warning("No allowed domains for '%s'.", domain)
        return []

    try:
        from firecrawl import Firecrawl
    except ImportError:
        logger.warning("firecrawl-py not installed; install with: pip install firecrawl-py")
        return []

    limit = min(getattr(settings, "firecrawl_search_limit", 5) or 5, 10)
    timeout_ms = getattr(settings, "firecrawl_search_timeout_ms", 30_000) or 30_000
    client = Firecrawl(api_key=settings.firecrawl_api_key)

    all_results: list[dict] = []
    for single_domain in allowed:
        # Restrict to this domain via site: operator (no scraping for speed; description only)
        site_query = f"site:{single_domain} {query}"
        logger.debug("Firecrawl search [%s] query=%s", domain, site_query[:80])

        try:
            # Firecrawl SDK: search(query, limit=...) or search({...})
            resp = client.search(site_query, limit=limit)
        except Exception:
            try:
                resp = client.search({"query": site_query, "limit": limit, "timeout": timeout_ms})
            except Exception as e:
                logger.warning("Firecrawl search failed for %s: %s", single_domain, e)
                continue

        if not isinstance(resp, dict):
            continue
        data = resp.get("data") or resp
        web = data.get("web") if isinstance(data, dict) else []
        news = data.get("news") if isinstance(data, dict) else []
        for item in (web or []) + (news or []):
            if not isinstance(item, dict):
                continue
            meta = item.get("metadata") or {}
            title = item.get("title") or (meta.get("title") if isinstance(meta, dict) else None) or single_domain
            url = item.get("url") or (meta.get("sourceURL") if isinstance(meta, dict) else None) or ""
            content = (
                item.get("markdown")
                or item.get("description")
                or item.get("snippet")
                or title
            )
            if not content and not url:
                continue
            all_results.append({
                "content": (content or "")[:8000],
                "source_url": url,
                "source_title": (title or "Unknown")[:500],
                "date": item.get("date"),
            })

        if all_results:
            logger.debug("Firecrawl search [%s] returned %d evidence items.", domain, len(all_results))
            break

    return all_results
