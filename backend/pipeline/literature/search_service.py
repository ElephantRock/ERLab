"""Unified literature search across multiple academic APIs."""

import asyncio
import hashlib
import logging

from backend.config import get_settings
from backend.pipeline.literature.base import AcademicSearchSource
from backend.pipeline.literature.models import Paper, SearchResult

logger = logging.getLogger(__name__)


class SearchService:
    """Search across multiple academic sources with deduplication."""

    def __init__(self, sources: list[AcademicSearchSource] | None = None):
        if sources is None:
            sources = self._default_sources()
        self._sources: dict[str, AcademicSearchSource] = {s.source_name: s for s in sources}

    async def search_all(
        self,
        query: str,
        sources: list[str] | None = None,
        limit_per_source: int = 20,
        year_from: int | None = None,
        year_to: int | None = None,
        deduplicate: bool = True,
    ) -> list[Paper]:
        """Search specified sources concurrently, deduplicate, and return unified results."""
        if sources is None:
            sources = list(self._sources.keys())

        active = {name: self._sources[name] for name in sources if name in self._sources}
        if not active:
            logger.warning("No valid sources specified: %s", sources)
            return []

        # Concurrent search
        tasks = [
            source.search(query, limit=limit_per_source, year_from=year_from, year_to=year_to)
            for source in active.values()
        ]
        results_per_source = await asyncio.gather(*tasks, return_exceptions=True)

        all_results: list[SearchResult] = []
        for name, result in zip(active.keys(), results_per_source, strict=True):
            if isinstance(result, Exception):
                logger.warning("Search failed for %s: %s", name, result)
            else:
                all_results.extend(result)  # type: ignore[arg-type]

        if deduplicate:
            return self._deduplicate(all_results)
        return [r.paper for r in all_results]

    async def get_citations(self, paper: Paper, limit: int = 50) -> list[Paper]:
        """Get citations from the paper's source."""
        source = self._sources.get(paper.source)
        if not source:
            return []
        return await source.get_citations(paper.id, limit=limit)

    async def get_references(self, paper: Paper, limit: int = 50) -> list[Paper]:
        """Get references from the paper's source."""
        source = self._sources.get(paper.source)
        if not source:
            return []
        return await source.get_references(paper.id, limit=limit)

    @staticmethod
    def _deduplicate(results: list[SearchResult]) -> list[Paper]:
        """Deduplicate papers by DOI or title hash, preferring Semantic Scholar data."""
        seen: list[Paper] = []  # type: ignore[assignment]
        dedup_keys: set[str] = set()

        # Sort to prefer semantic_scholar data when merging
        source_priority = {"semantic_scholar": 0, "arxiv": 1, "openalex": 2}
        sorted_results = sorted(
            results,
            key=lambda r: source_priority.get(r.source, 99),
        )

        for result in sorted_results:
            paper = result.paper
            key = paper.doi if paper.doi else _title_hash(paper.title)
            if key in dedup_keys:
                continue
            dedup_keys.add(key)
            seen.append(paper)  # type: ignore[arg-type]

        return seen  # type: ignore[return-value]

    @staticmethod
    def _default_sources() -> list[AcademicSearchSource]:
        """Create default sources from settings.

        When no Semantic Scholar API key is set, OpenAlex is placed first
        to avoid severe rate limiting (Fix #11b).
        """
        from backend.pipeline.literature.arxiv_source import ArxivSource
        from backend.pipeline.literature.openalex_source import OpenAlexSource
        from backend.pipeline.literature.semantic_scholar import SemanticScholarSource

        settings = get_settings()

        if not settings.semantic_scholar_api_key:
            logger.info(
                "No S2 API key set — using OpenAlex as primary source "
                "(free, unlimited). Get a free S2 key: "
                "https://www.semanticscholar.org/product/api#api-key"
            )
            return [
                OpenAlexSource(email=settings.openalex_email),
                ArxivSource(),
                SemanticScholarSource(api_key=None),
            ]

        return [
            SemanticScholarSource(api_key=settings.semantic_scholar_api_key),
            ArxivSource(),
            OpenAlexSource(email=settings.openalex_email),
        ]


def _title_hash(title: str) -> str:
    normalized = title.lower().strip().replace(" ", "")
    return hashlib.md5(normalized.encode()).hexdigest()
