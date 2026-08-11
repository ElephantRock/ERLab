"""Multi-source literature searcher.

Fans out queries across multiple search engines concurrently,
merges and deduplicates results by DOI/title similarity.
"""
from __future__ import annotations

import asyncio
import logging

from backend.pipeline.literature.base import AcademicSearchSource
from backend.pipeline.literature.models import SearchResult

logger = logging.getLogger(__name__)


class MultiSourceSearcher:
    """Search multiple literature sources concurrently.

    Each source fails independently (HB-01). Results are merged
    and deduplicated by DOI and title similarity.
    """

    def __init__(self, sources: list[AcademicSearchSource] | None = None) -> None:
        self._sources: dict[str, AcademicSearchSource] = {}
        if sources:
            for source in sources:
                self.register(source)

    def register(self, source: AcademicSearchSource) -> None:
        """Register a literature source."""
        self._sources[source.source_name] = source
        logger.debug("Registered literature source: %s", source.source_name)

    async def search(
        self,
        query: str,
        limit: int = 20,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[SearchResult]:
        """Search all registered sources concurrently and merge results.

        Args:
            query: Search query string.
            limit: Maximum results per source.
            year_from: Optional start year filter.
            year_to: Optional end year filter.

        Returns:
            Merged, deduplicated list of SearchResult.
        """
        if not self._sources:
            logger.warning("No literature sources registered")
            return []

        # Fan out to all sources concurrently
        tasks = {}
        for name, source in self._sources.items():
            tasks[name] = asyncio.create_task(
                self._safe_search(name, source, query, limit, year_from, year_to)
            )

        # Collect results
        all_results: list[SearchResult] = []
        for name, task in tasks.items():
            try:
                results = await task
                all_results.extend(results)
                logger.debug("Source '%s' returned %d results", name, len(results))
            except Exception as e:
                logger.warning("Source '%s' failed: %s", name, e)

        # Merge and deduplicate
        merged = self._deduplicate(all_results)
        logger.info(
            "Multi-source search '%s': %d results from %d sources, %d after dedup",
            query[:50], len(all_results), len(self._sources), len(merged),
        )
        return merged

    async def _safe_search(
        self,
        name: str,
        source: AcademicSearchSource,
        query: str,
        limit: int,
        year_from: int | None,
        year_to: int | None,
    ) -> list[SearchResult]:
        """Search a single source with error handling (HB-01)."""
        try:
            return await source.search(query, limit, year_from, year_to)
        except Exception as e:
            logger.warning("Source '%s' search failed: %s", name, e)
            return []

    @staticmethod
    def _deduplicate(results: list[SearchResult]) -> list[SearchResult]:
        """Deduplicate results by DOI and title similarity.

        Keeps the result with the highest relevance score.
        """
        seen_dois: set[str] = set()
        seen_titles: set[str] = set()
        unique: list[SearchResult] = []

        # Sort by relevance score descending (keep highest first)
        sorted_results = sorted(results, key=lambda r: r.relevance_score, reverse=True)

        for result in sorted_results:
            paper = result.paper

            # Check DOI
            if paper.doi:
                doi_key = paper.doi.lower().strip()
                if doi_key in seen_dois:
                    continue
                seen_dois.add(doi_key)

            # Check title
            title_key = paper.title.lower().strip()
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)

            unique.append(result)

        return unique

    def list_sources(self) -> list[str]:
        """List registered source names."""
        return list(self._sources.keys())
