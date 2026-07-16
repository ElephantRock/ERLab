"""Abstract base class for academic search sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.pipeline.literature.contracts import AttemptObserver, SourceSearchOutcome
from backend.pipeline.literature.models import Paper, SearchResult


class AcademicSearchSource(ABC):
    """Interface for academic paper search APIs."""

    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int = 20,
        year_from: int | None = None,
        year_to: int | None = None,
        *,
        attempt_observer: AttemptObserver | None = None,
        **kwargs: Any,
    ) -> SourceSearchOutcome:
        """Search for papers matching the query.

        Must call ``attempt_observer.attempt_started()`` immediately before
        EVERY outbound provider request (initial, retry, pagination, or
        follow-up). Must return a ``SourceSearchOutcome`` with a truthful
        status and the actual outbound attempt count.
        """
        ...

    @abstractmethod
    async def get_paper(self, paper_id: str) -> Paper | None:
        """Retrieve a single paper by its source-specific ID."""
        ...

    @abstractmethod
    async def get_citations(self, paper_id: str, limit: int = 50) -> list[Paper]:
        """Get papers that cite the given paper."""
        ...

    @abstractmethod
    async def get_references(self, paper_id: str, limit: int = 50) -> list[Paper]:
        """Get papers referenced by the given paper."""
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        ...
