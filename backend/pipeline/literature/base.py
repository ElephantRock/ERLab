"""Abstract base class for academic search sources."""

from abc import ABC, abstractmethod

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
    ) -> list[SearchResult]:
        """Search for papers matching the query."""
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
    def source_name(self) -> str: ...
