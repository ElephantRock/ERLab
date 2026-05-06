"""Search integration service: wires MultiSource + Relevance + Anti-Fabrication.

Coordinates:
- MultiSourceSearcher: fans out queries across all registered sources
- RelevanceFilter: scores and filters results by domain similarity
- AntiFabricationGuard: checks proposals for fabricated content

All operations fail-safe.
"""
from __future__ import annotations

import logging
from typing import Any

from backend.pipeline.literature.multi_source import MultiSourceSearcher
from backend.pipeline.literature.relevance_filter import RelevanceFilter
from backend.pipeline.safety.anti_fabrication import AntiFabricationGuard, GuardResult

logger = logging.getLogger(__name__)


class SearchIntegrationService:
    """Coordinates multi-source search, relevance filtering, and safety checks."""

    def __init__(self, embedding_provider=None, relevance_threshold: float = 0.3) -> None:
        self._searcher = MultiSourceSearcher()
        self._filter = RelevanceFilter(
            embedding_provider=embedding_provider,
            threshold=relevance_threshold,
        )
        self._guard = AntiFabricationGuard()

    def register_source(self, source) -> None:
        """Register a literature source."""
        self._searcher.register(source)

    async def search_and_filter(
        self,
        query: str,
        limit: int = 20,
        year_from: int | None = None,
        year_to: int | None = None,
    ):
        """Search all sources and filter by relevance."""
        results = await self._searcher.search(
            query, limit=limit, year_from=year_from, year_to=year_to,
        )
        # Relevance filter
        filtered = await self._filter.filter(results, query)
        return filtered

    def check_proposal(self, text: str) -> GuardResult:
        """Check proposal text for fabrication."""
        return self._guard.check_proposal(text)

    def list_sources(self) -> list[str]:
        """List registered source names."""
        return self._searcher.list_sources()

    @property
    def guard(self) -> AntiFabricationGuard:
        return self._guard
