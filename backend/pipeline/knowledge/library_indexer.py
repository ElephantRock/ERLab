"""Library indexer: indexes pipeline run results into the knowledge library.

Called after each pipeline run to add papers, gaps, and ideas
to the persistent knowledge library for future runs to query.
"""
from __future__ import annotations

import logging
from typing import Any

from backend.pipeline.knowledge.library import KnowledgeLibrary

logger = logging.getLogger(__name__)


class LibraryIndexer:
    """Indexes pipeline run results into the knowledge library.

    Usage:
        indexer = LibraryIndexer()
        count = indexer.index_run(domain="AI/NLP", run_id="run_20260506",
                                   papers=result.papers, gaps=result.gaps, ideas=result.ideas)
    """

    def __init__(self, library: KnowledgeLibrary | None = None) -> None:
        self._library = library or KnowledgeLibrary()

    def index_run(
        self,
        domain: str,
        run_id: str,
        papers: list[Any] | None = None,
        gaps: list[Any] | None = None,
        ideas: list[Any] | None = None,
    ) -> dict[str, int]:
        """Index all results from a pipeline run.

        Returns dict with counts: {"papers": N, "gaps": N, "ideas": N, "total": N}
        """
        counts = {"papers": 0, "gaps": 0, "ideas": 0, "total": 0}

        try:
            if papers:
                counts["papers"] = self._library.add_papers(papers, domain, run_id)
            if gaps:
                counts["gaps"] = self._library.add_gaps(gaps, domain, run_id)
            if ideas:
                counts["ideas"] = self._library.add_ideas(ideas, domain, run_id)
            counts["total"] = sum(v for k, v in counts.items() if k != "total")

            logger.info(
                "Indexed run %s: %d papers, %d gaps, %d ideas (%d new total)",
                run_id, counts["papers"], counts["gaps"], counts["ideas"], counts["total"],
            )
        except Exception as e:
            logger.warning("Library indexing failed for run %s: %s", run_id, e)

        return counts

    def get_existing_papers(self, domain: str, limit: int = 100) -> list[dict]:
        """Get papers previously indexed for a domain."""
        try:
            return self._library.query(domain, entry_type="paper", limit=limit)
        except Exception as e:
            logger.warning("Failed to query existing papers: %s", e)
            return []

    def get_existing_gaps(self, domain: str, limit: int = 50) -> list[dict]:
        """Get gaps previously indexed for a domain."""
        try:
            return self._library.query(domain, entry_type="gap", limit=limit)
        except Exception as e:
            logger.warning("Failed to query existing gaps: %s", e)
            return []

    @property
    def library(self) -> KnowledgeLibrary:
        return self._library
