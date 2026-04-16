"""Shared data models for the literature search module."""

from pydantic import BaseModel, Field


class Author(BaseModel):
    name: str
    id: str | None = None
    affiliations: list[str] = Field(default_factory=list)


class Paper(BaseModel):
    """Normalized paper representation across all academic sources."""
    id: str
    source: str  # semantic_scholar, arxiv, openalex
    title: str
    abstract: str | None = None
    authors: list[Author] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    citation_count: int | None = None
    url: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    keywords: list[str] = Field(default_factory=list)
    embedding: list[float] | None = None


class SearchResult(BaseModel):
    paper: Paper
    relevance_score: float | None = None
    source: str
