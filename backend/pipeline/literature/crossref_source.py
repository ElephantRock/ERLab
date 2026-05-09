"""CrossRef literature source for DOI-based metadata.

No API key required (polite pool with mailto parameter).
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.pipeline.literature.base import AcademicSearchSource
from backend.pipeline.literature.models import Author, Paper, SearchResult

logger = logging.getLogger(__name__)

DEFAULT_API_BASE = "https://api.crossref.org"


def _get_api_base() -> str:
    """Read CrossRef API base URL from settings, falling back to default."""
    try:
        from backend.config import get_settings
        return get_settings().crossref_api_url
    except Exception:
        return DEFAULT_API_BASE


class CrossRefSource(AcademicSearchSource):
    """Literature source using CrossRef API.

    No API key required. Use mailto parameter for polite pool (faster).
    """

    def __init__(self, mailto: str = "", api_base: str | None = None) -> None:
        self._mailto = mailto
        base = api_base or _get_api_base()
        user_agent = (
            f"ElephantRock/1.0 (mailto:{mailto or 'noreply@example.com'})"
        )
        self._client = httpx.AsyncClient(
            base_url=base,
            timeout=30.0,
            headers={"User-Agent": user_agent},
        )

    @property
    def source_name(self) -> str:
        return "crossref"

    async def search(
        self,
        query: str,
        limit: int = 20,
        year_from: int | None = None,
        year_to: int | None = None,
        **kwargs: Any,
    ) -> list[SearchResult]:
        """Search CrossRef for papers matching the query."""
        try:
            params: dict[str, Any] = {
                "query": query,
                "rows": min(limit, 50),
                "sort": "relevance",
                "select": "DOI,title,author,published-print,published-online,abstract,container-title,is-referenced-by-count",
            }
            if year_from:
                params["filter"] = f"from-pub-date:{year_from}"
                if year_to:
                    params["filter"] += f",until-pub-date:{year_to}"

            response = await self._client.get("/works", params=params)
            response.raise_for_status()
            data = response.json()

            items = data.get("message", {}).get("items", [])
            results = []

            for item in items[:limit]:
                title_list = item.get("title", [])
                title = title_list[0] if title_list else ""
                if not title:
                    continue

                abstract = item.get("abstract", "")
                # CrossRef abstracts may contain HTML tags
                import re
                abstract = re.sub(r"<[^>]+>", "", abstract) if abstract else ""

                # Extract year
                date_parts = (
                    item.get("published-print", {}).get("date-parts", [[]])
                    or item.get("published-online", {}).get("date-parts", [[]])
                )
                year = date_parts[0][0] if date_parts and date_parts[0] else None

                # Extract authors
                authors = []
                for author in item.get("author", []):
                    given = author.get("given", "")
                    family = author.get("family", "")
                    if family:
                        authors.append(Author(name=f"{given} {family}".strip()))

                doi = item.get("DOI", "")
                venue = ""
                container = item.get("container-title", [])
                if container:
                    venue = container[0]

                citations = item.get("is-referenced-by-count", 0)

                paper = Paper(
                    id=f"crossref:{doi or title[:20]}",
                    title=title,
                    abstract=abstract[:2000],
                    year=year,
                    authors=authors,
                    doi=doi,
                    url=f"https://doi.org/{doi}" if doi else "",
                    source="crossref",
                    citation_count=citations,
                    venue=venue,
                )

                results.append(SearchResult(
                    paper=paper,
                    relevance_score=1.0,
                    source="crossref",
                ))

            return results

        except Exception as e:
            logger.warning("CrossRef search failed: %s", e)
            return []

    async def get_paper(self, paper_id: str) -> Paper | None:
        """Get a single paper by DOI."""
        try:
            response = await self._client.get(f"/works/{paper_id}")
            response.raise_for_status()
            data = response.json()
            item = data.get("message", {})

            title_list = item.get("title", [])
            title = title_list[0] if title_list else ""
            if not title:
                return None

            return Paper(
                id=f"crossref:{paper_id}",
                title=title,
                abstract="",
                year=None,
                authors=[],
                doi=paper_id,
                url=f"https://doi.org/{paper_id}",
                source="crossref",
                citation_count=item.get("is-referenced-by-count", 0),
                venue="",
            )
        except Exception as e:
            logger.warning("CrossRef get_paper failed: %s", e)
            return None

    async def get_citations(self, paper_id: str, limit: int = 50) -> list[Paper]:
        """Get papers citing this paper (stub)."""
        return []

    async def get_references(self, paper_id: str, limit: int = 50) -> list[Paper]:
        """Get papers referenced by this paper (stub)."""
        return []
