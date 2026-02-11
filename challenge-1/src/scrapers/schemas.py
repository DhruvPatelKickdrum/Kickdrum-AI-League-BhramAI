"""Pydantic models for structured web search output."""

from pydantic import BaseModel, Field


class SearchEvidence(BaseModel):
    """A single piece of evidence returned by web search."""

    content: str = Field(description="The relevant factual content extracted from the source.")
    source_url: str = Field(description="The URL where this information was found.")
    source_title: str = Field(description="Title or name of the source.")
    date: str | None = Field(
        default=None,
        description="Date of the information if available (e.g. publication date).",
    )


class SearchResult(BaseModel):
    """Structured output from an OpenAI web search call."""

    evidence: list[SearchEvidence] = Field(
        description="List of evidence items found, each with content and source citation."
    )
    summary: str = Field(
        description="Brief summary of what was found across all sources."
    )
