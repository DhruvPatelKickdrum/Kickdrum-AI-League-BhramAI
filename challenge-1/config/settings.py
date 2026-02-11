"""Application settings loaded from environment variables and config files."""

import os
from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings

CONFIG_DIR = Path(__file__).parent


class Settings(BaseSettings):
    """Central configuration for the claim verification pipeline."""

    # OpenAI
    openai_api_key: str = Field(default="sk-dummy-key", alias="OPENAI_API_KEY")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")

    # Database
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/claim_verifier",
        alias="DATABASE_URL",
    )

    # Cohere (optional reranker)
    cohere_api_key: str = Field(default="", alias="COHERE_API_KEY")

    # Firecrawl (optional; when set, used for web search instead of OpenAI for speed)
    firecrawl_api_key: str = Field(default="", alias="FIRECRAWL_API_KEY")
    firecrawl_search_limit: int = Field(default=5, alias="FIRECRAWL_SEARCH_LIMIT")
    firecrawl_search_timeout_ms: int = Field(default=30_000, alias="FIRECRAWL_SEARCH_TIMEOUT_MS")

    # RAG pipeline
    similarity_threshold: float = Field(default=0.6, alias="SIMILARITY_THRESHOLD")
    max_agent_steps: int = Field(default=12, alias="MAX_AGENT_STEPS")
    max_agent_response_tokens: int = Field(default=2048, alias="MAX_AGENT_RESPONSE_TOKENS")
    chunk_size: int = Field(default=512, description="Chunk size in tokens")
    chunk_overlap: int = Field(default=50, description="Chunk overlap in tokens")
    top_k_retrieval: int = Field(default=20, description="Top-K candidates from vector search")
    top_k_rerank: int = Field(default=5, description="Top-K after reranking")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "populate_by_name": True,
        "extra": "ignore",
    }


settings = Settings()


def get_llm_temperature() -> float:
    """
    Temperature for LLM calls. Some models (e.g. gpt-4.1-nano) only support default 1.0.
    """
    if "nano" in settings.llm_model.lower():
        return 1.0
    return 0.0


# ---------------------------------------------------------------------------
# Sources configuration (loaded from YAML)
# ---------------------------------------------------------------------------

_sources_config: dict | None = None


def get_sources_config() -> dict:
    """Load and cache the domain sources configuration from sources.yaml."""
    global _sources_config
    if _sources_config is None:
        sources_path = CONFIG_DIR / "sources.yaml"
        with open(sources_path, "r") as f:
            _sources_config = yaml.safe_load(f)
    return _sources_config


def get_domain_config(domain: str) -> dict | None:
    """Get configuration for a specific domain (news, finance, govt, weather)."""
    config = get_sources_config()
    return config.get("domains", {}).get(domain)


def get_allowed_domains(domain: str) -> list[str]:
    """Get the list of allowed website domains for a given domain category."""
    domain_cfg = get_domain_config(domain)
    if not domain_cfg:
        return []
    return [s["domain"] for s in domain_cfg.get("sources", [])]


def get_search_instructions(domain: str) -> str:
    """Get the search instructions prompt for a given domain."""
    domain_cfg = get_domain_config(domain)
    if not domain_cfg:
        return ""
    return domain_cfg.get("search_instructions", "").strip()
