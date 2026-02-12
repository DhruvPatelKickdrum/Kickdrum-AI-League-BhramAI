"""
Firecrawl integration: Search (links only) → LLM selects authentic links → Scrape those URLs.
Optional: Firecrawl Agent mode, then validate result with our LLM.
"""

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from openai import OpenAI

from config.settings import get_allowed_domains, get_llm_temperature, settings

logger = logging.getLogger(__name__)

# Max links to send to LLM for selection, and max to scrape after selection
MAX_CANDIDATE_LINKS = 5
MAX_LINKS_TO_SCRAPE = 1
AGENT_POLL_INTERVAL_SEC = 2
AGENT_MAX_WAIT_SEC = 120
FIRECRAWL_API_BASE = "https://api.firecrawl.dev/v2"

LINK_SELECT_PROMPT = """You are helping verify a factual claim. Below are search result links (URL, title, description).

Claim to verify: {claim}

Candidate sources (one per line, format: URL | title | description):
{candidates}

Which links look AUTHENTIC and RELEVANT for verifying this claim? Choose trusted sources (e.g. established news, encyclopedias, official sites). Return a JSON array of exactly the URLs to use, in order of relevance, maximum {max_links} URLs. If none look trustworthy, return [].

Reply with ONLY a JSON array of URL strings, no other text. Example: ["https://example.com/page", "https://bbc.com/news/..."]
"""

AGENT_VALIDATE_PROMPT = """You are validating evidence extracted by an automated agent for claim verification.

Claim: {claim}

Extracted data from the agent:
{agent_data}

Is this evidence relevant and trustworthy for verifying or refuting the claim? In 1-2 short paragraphs, summarize the key factual evidence (quotes, dates, sources) that support or contradict the claim. If the data is irrelevant or low quality, say so briefly. Output only the summary, no preamble."""


def _normalize_domain(domain: str) -> str:
    s = (domain or "").strip()
    s = re.sub(r"^https?://", "", s, flags=re.IGNORECASE)
    return s.rstrip("/") or domain


def _search_one_domain(client, query: str, single_domain: str, limit: int) -> list[dict]:
    """Search a single domain via Firecrawl and return candidate links."""
    site_query = f"site:{single_domain} {query}"
    try:
        resp = client.search(site_query, limit=min(limit, 5))
    except Exception:
        try:
            resp = client.search({"query": site_query, "limit": min(limit, 5)})
        except Exception as e:
            logger.warning("Firecrawl search failed for %s: %s", single_domain, e)
            return []
    if not isinstance(resp, dict):
        return []
    data = resp.get("data") or resp
    web = data.get("web") if isinstance(data, dict) else []
    news = data.get("news") if isinstance(data, dict) else []
    candidates = []
    for item in (web or []) + (news or []):
        if not isinstance(item, dict):
            continue
        url = item.get("url") or (item.get("metadata") or {}).get("sourceURL") if isinstance(item.get("metadata"), dict) else ""
        title = item.get("title") or "Untitled"
        desc = item.get("description") or item.get("snippet") or ""
        if url:
            candidates.append({"url": url, "title": title, "description": (desc or "")[:300]})
    return candidates


def _search_links_only(client, query: str, allowed: list[str], limit: int) -> list[dict]:
    """Firecrawl Search without scrapeOptions: get url, title, description only. Searches domains in parallel."""
    domains_to_search = allowed[:2]  # Limit to 2 domains for speed
    all_candidates: list[dict] = []

    with ThreadPoolExecutor(max_workers=len(domains_to_search)) as executor:
        futures = {
            executor.submit(_search_one_domain, client, query, d, limit): d
            for d in domains_to_search
        }
        for future in as_completed(futures):
            try:
                candidates = future.result()
                all_candidates.extend(candidates)
                # Early exit once we have enough candidates
                if len(all_candidates) >= MAX_CANDIDATE_LINKS:
                    for f in futures:
                        f.cancel()
                    break
            except Exception as e:
                logger.warning("Firecrawl domain search failed: %s", e)

    return all_candidates[:MAX_CANDIDATE_LINKS]


def _llm_select_authentic_links(claim_context: str, candidates: list[dict], max_links: int = MAX_LINKS_TO_SCRAPE) -> list[str]:
    """Use our LLM to pick which links look authentic and relevant for the claim."""
    if not candidates:
        return []
    lines = []
    for c in candidates:
        lines.append(f"{c['url']} | {c.get('title', '')} | {c.get('description', '')}")
    prompt = LINK_SELECT_PROMPT.format(
        claim=claim_context[:1500],
        candidates="\n".join(lines),
        max_links=max_links,
    )
    client = OpenAI(api_key=settings.openai_api_key)
    try:
        resp = client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=get_llm_temperature(),
        )
        raw = (resp.choices[0].message.content or "").strip()
        # Extract JSON array (handle markdown code blocks)
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        urls = json.loads(raw)
        if not isinstance(urls, list):
            return []
        valid = [u for u in urls if isinstance(u, str) and u.startswith("http")][:max_links]
        logger.debug("LLM selected %d links to scrape: %s", len(valid), [u[:60] for u in valid])
        return valid
    except Exception as e:
        logger.warning("LLM link selection failed: %s", e)
        return [c["url"] for c in candidates[:max_links]]


def _scrape_single_url(client, url: str) -> dict | None:
    """Scrape a single URL with Firecrawl Scrape API; return evidence item or None."""
    try:
        out = client.scrape(url, formats=["markdown"])
        if not out or not isinstance(out, dict):
            return None
        data = out.get("data") or out
        md = data.get("markdown") or data.get("content") or ""
        meta = data.get("metadata") or {}
        title = meta.get("title") or data.get("title") or url
        if md or title:
            return {
                "content": (md or title)[:12000],
                "source_url": url,
                "source_title": (title or "Untitled")[:500],
                "date": meta.get("publishedTime") or meta.get("lastModified"),
            }
    except Exception as e:
        logger.warning("Firecrawl scrape failed for %s: %s", url[:60], e)
    return None


def _scrape_urls(client, urls: list[str]) -> list[dict]:
    """Scrape URLs with Firecrawl Scrape API in parallel; return evidence items."""
    if not urls:
        return []
    results = []
    with ThreadPoolExecutor(max_workers=min(3, len(urls))) as executor:
        futures = {executor.submit(_scrape_single_url, client, url): url for url in urls}
        for future in as_completed(futures):
            try:
                item = future.result()
                if item:
                    results.append(item)
                    # Early exit: 1 evidence item is enough
                    if results:
                        for f in futures:
                            f.cancel()
                        break
            except Exception as e:
                logger.warning("Firecrawl scrape failed: %s", e)
    return results


def search_firecrawl(
    query: str,
    domain: str,
    *,
    allowed_domains_override: list[str] | None = None,
    claim_context: str | None = None,
) -> list[dict]:
    """
    1. Firecrawl Search (links only, no scrape).
    2. Our LLM selects which links look authentic/relevant.
    3. Firecrawl Scrape on selected URLs.
    Returns evidence list: [{"content", "source_url", "source_title", "date"}].
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

    limit = min(getattr(settings, "firecrawl_search_limit", 8) or 8, 15)
    client = Firecrawl(api_key=settings.firecrawl_api_key)

    # 1. Search (links only)
    candidates = _search_links_only(client, query, allowed, limit)
    if not candidates:
        logger.debug("Firecrawl search [%s] returned no links.", domain)
        return []

    logger.debug("Firecrawl search [%s] returned %d candidate links.", domain, len(candidates))

    max_scrape = getattr(settings, "firecrawl_max_links_to_scrape", MAX_LINKS_TO_SCRAPE) or MAX_LINKS_TO_SCRAPE

    # 2. Skip LLM link selection when candidates are few (saves ~5-10s LLM call)
    if len(candidates) <= max_scrape:
        to_scrape = [c["url"] for c in candidates[:max_scrape]]
        logger.debug("Few candidates (%d); skipping LLM selection.", len(candidates))
    else:
        to_scrape = _llm_select_authentic_links(claim_context or query, candidates, max_links=max_scrape)
        if not to_scrape:
            to_scrape = [c["url"] for c in candidates[:max_scrape]]

    # 3. Scrape selected URLs (parallel)
    evidence = _scrape_urls(client, to_scrape)
    logger.debug("Firecrawl [%s]: scraped %d URLs → %d evidence items.", domain, len(to_scrape), len(evidence))
    return evidence


def _llm_validate_agent_result(claim: str, agent_data: dict | str) -> str:
    """Validate/summarize Firecrawl agent output with our LLM."""
    data_str = agent_data if isinstance(agent_data, str) else json.dumps(agent_data)[:8000]
    prompt = AGENT_VALIDATE_PROMPT.format(claim=claim[:1500], agent_data=data_str)
    client = OpenAI(api_key=settings.openai_api_key)
    try:
        resp = client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=get_llm_temperature(),
        )
        return (resp.choices[0].message.content or "").strip() or data_str
    except Exception as e:
        logger.warning("LLM agent validation failed: %s", e)
        return data_str


def _agent_run_via_api(api_key: str, prompt: str, urls: list[str] | None) -> dict | None:
    """Start agent via REST API and poll until completed; return extracted data or None."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        r = requests.post(
            f"{FIRECRAWL_API_BASE}/agent",
            headers=headers,
            json={"prompt": prompt, "urls": urls or []},
            timeout=30,
        )
        r.raise_for_status()
        body = r.json()
        job_id = body.get("id")
        if not job_id:
            return None
        deadline = time.time() + AGENT_MAX_WAIT_SEC
        while time.time() < deadline:
            time.sleep(AGENT_POLL_INTERVAL_SEC)
            s = requests.get(f"{FIRECRAWL_API_BASE}/agent/{job_id}", headers=headers, timeout=30)
            s.raise_for_status()
            status_resp = s.json()
            status = status_resp.get("status")
            if status == "completed":
                return status_resp.get("data")
            if status == "failed":
                logger.warning("Firecrawl agent job failed: %s", status_resp.get("error"))
                return None
    except Exception as e:
        logger.warning("Firecrawl agent API failed: %s", e)
    return None


def _run_firecrawl_agent(api_key: str, prompt: str, urls: list[str] | None) -> dict | None:
    """Run Firecrawl agent via SDK agent() (blocking, returns result.data), else fallback to REST."""
    try:
        from firecrawl import Firecrawl
        app = Firecrawl(api_key=api_key)
        # SDK: app.agent(prompt=..., urls=..., model="spark-1-mini") -> result with .data
        result = app.agent(
            prompt=prompt,
            urls=urls or [],
            model="spark-1-mini",
        )
        if result is None:
            return None
        data = getattr(result, "data", None) or (result.get("data") if isinstance(result, dict) else None)
        return data
    except Exception as e:
        logger.debug("Firecrawl SDK agent() failed, trying REST: %s", e)
    return _agent_run_via_api(api_key, prompt, urls)


def search_firecrawl_agent(
    query: str,
    domain: str,
    *,
    allowed_domains_override: list[str] | None = None,
    claim_context: str | None = None,
) -> list[dict]:
    """
    Use Firecrawl Agent (SDK agent() or REST) to extract data, then validate with our LLM.
    """
    if not getattr(settings, "firecrawl_api_key", None) or not settings.firecrawl_api_key.strip():
        return []

    raw_allowed = allowed_domains_override or get_allowed_domains(domain)
    allowed = [d for d in (_normalize_domain(d) for d in raw_allowed) if d]
    claim = claim_context or query
    start_urls = [f"https://{d}" for d in allowed[:3]] if allowed else None
    prompt = f"Find factual evidence that could verify or refute this claim. Extract relevant quotes and cite the source URL for each. Claim: {claim[:2000]}"

    data = _run_firecrawl_agent(settings.firecrawl_api_key, prompt, start_urls)
    if not data:
        return []

    validated = _llm_validate_agent_result(claim, data)
    return [{
        "content": validated[:12000],
        "source_url": "",
        "source_title": "Firecrawl Agent (LLM-validated)",
        "date": None,
    }]
