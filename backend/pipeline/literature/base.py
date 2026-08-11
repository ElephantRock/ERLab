"""Abstract base class for academic search sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.pipeline.literature.contracts import (
    AttemptObserver,
    SourceQueryPlan,
    SourceSearchOutcome,
)
from backend.pipeline.literature.models import Paper


class AcademicSearchSource(ABC):
    """Interface for academic paper search APIs.

    P0.2.3: Query planning (``build_query_plan``) is separated from execution
    (``execute_query_plan``) so the recorder can persist the exact plan before
    the adapter issues its first request. The legacy ``search()`` method is
    retained as a compatibility wrapper.
    """

    @abstractmethod
    def build_query_plan(
        self,
        query: str,
        limit: int = 20,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> SourceQueryPlan:
        """Build a deterministic provider-level query plan.

        Pure: performs no network access. The returned plan's
        ``translated_query`` is the canonical JSON persisted by the recorder.
        ``request_parameters`` MUST exclude secrets.
        """
        ...

    @abstractmethod
    async def execute_query_plan(
        self,
        plan: SourceQueryPlan,
        *,
        attempt_observer: AttemptObserver | None = None,
    ) -> SourceSearchOutcome:
        """Execute exactly the supplied plan.

        Must call ``attempt_observer.attempt_started()`` immediately before
        EVERY outbound provider request. Must return a ``SourceSearchOutcome``
        with a truthful status, the actual outbound attempt count, and
        structured ``failure_category``/``failure_code`` on non-success.
        """
        ...

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
        """Compatibility wrapper: build plan then execute it."""
        plan = self.build_query_plan(query, limit=limit, year_from=year_from, year_to=year_to)
        return await self.execute_query_plan(plan, attempt_observer=attempt_observer)

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
