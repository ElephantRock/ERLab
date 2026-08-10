"""Knowledge integration service: wires library + error learning into pipeline.

Provides:
- Post-run indexing of papers/gaps/ideas into KnowledgeLibrary
- Pre-run queries of existing knowledge for a domain
- Error recording when quality checks fail

All operations are fail-safe (HB-01).
"""
from __future__ import annotations

import logging
from typing import Any

from backend.pipeline.knowledge.error_store import ErrorKnowledgeStore, FailureEntry
from backend.pipeline.knowledge.library import KnowledgeLibrary
from backend.pipeline.knowledge.library_indexer import LibraryIndexer

logger = logging.getLogger(__name__)


class KnowledgeIntegrationService:
    """Centralized knowledge integration for the pipeline.

    Manages:
    - KnowledgeLibrary: persistent storage of papers/gaps/ideas per domain
    - LibraryIndexer: indexes pipeline run results
    - ErrorKnowledgeStore: records quality failures for cross-run learning
    """

    def __init__(
        self,
        library_dir: str = "./data/knowledge",
        error_db_path: str = "./data/error_knowledge.db",
    ) -> None:
        self._library = KnowledgeLibrary(db_path=f"{library_dir}/library.db")
        self._indexer = LibraryIndexer(self._library)
        self._error_store = ErrorKnowledgeStore(db_path=error_db_path)

    def index_run_results(
        self,
        domain: str,
        papers: list[Any] | None = None,
        gaps: list[Any] | None = None,
        ideas: list[Any] | None = None,
        run_id: str = "",
    ) -> dict:
        """Index pipeline run results into the knowledge library.

        Returns counts of indexed items.
        """
        try:
            counts = {"papers": 0, "gaps": 0, "ideas": 0}

            if papers:
                counts["papers"] = self._library.add_papers(papers, domain, run_id)

            if gaps:
                counts["gaps"] = self._library.add_gaps(gaps, domain, run_id)

            if ideas:
                counts["ideas"] = self._library.add_ideas(ideas, domain, run_id)

            logger.info(
                "Knowledge integration: indexed %d papers, %d gaps, %d ideas for '%s'",
                counts["papers"], counts["gaps"], counts["ideas"], domain,
            )
            return counts

        except Exception as e:
            logger.warning("Knowledge indexing failed: %s", e)
            return {"papers": 0, "gaps": 0, "ideas": 0, "error": str(e)}

    def query_existing_knowledge(self, domain: str) -> dict:
        """Query existing knowledge for a domain before starting a new run."""
        try:
            papers = self._indexer.get_existing_papers(domain)
            gaps = self._indexer.get_existing_gaps(domain)
            return {
                "existing_papers": len(papers),
                "existing_gaps": len(gaps),
                "has_knowledge": len(papers) > 0 or len(gaps) > 0,
            }
        except Exception as e:
            logger.warning("Knowledge query failed: %s", e)
            return {"existing_papers": 0, "existing_gaps": 0, "has_knowledge": False}

    def record_failure(
        self,
        stage: str,
        reason: str,
        suggestion: str = "",
        input_content: str = "",
    ) -> None:
        """Record a quality failure for cross-run learning."""
        try:
            entry = FailureEntry(
                stage=stage,
                input_hash=ErrorKnowledgeStore.hash_input(input_content or reason),
                reason=reason,
                suggestion=suggestion,
            )
            self._error_store.record(entry)
        except Exception as e:
            logger.warning("Error recording failed: %s", e)

    def get_past_failures(self, stage: str | None = None) -> list[dict]:
        """Get past failures for learning."""
        try:
            return self._error_store.query(stage=stage, limit=20)
        except Exception as e:
            logger.warning("Error query failed: %s", e)
            return []

    def close(self) -> None:
        self._error_store.close()
