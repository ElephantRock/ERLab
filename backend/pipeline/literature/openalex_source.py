"""OpenAlex API client."""

import logging

import httpx

from backend.pipeline.literature.base import AcademicSearchSource
from backend.pipeline.literature.models import Author, Paper, SearchResult

logger = logging.getLogger(__name__)

API_BASE = "https://api.openalex.org"


class OpenAlexSource(AcademicSearchSource):
    def __init__(self, email: str | None = None):
        params = {}
        if email:
            params["mailto"] = email
        self._client = httpx.AsyncClient(base_url=API_BASE, params=params, timeout=30.0)

    @property
    def source_name(self) -> str:
        return "openalex"

    async def search(
        self,
        query: str,
        limit: int = 20,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[SearchResult]:
        params = {"search": query, "per_page": min(limit, 50)}
        if year_from or year_to:
            year_filter = f"publication_year:{year_from or 2000}-{year_to or 2030}"
            params["filter"] = year_filter

        try:
            response = await self._client.get("/works", params=params)  # type: ignore[arg-type]
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            logger.warning("OpenAlex search failed: %s", e)
            return []

        results = []
        for item in data.get("results", []):
            paper = self._parse_work(item)
            if paper:
                results.append(
                    SearchResult(
                        paper=paper,
                        relevance_score=item.get("relevance_score"),
                        source=self.source_name,
                    )
                )
        return results

    async def get_paper(self, paper_id: str) -> Paper | None:
        try:
            response = await self._client.get(f"/works/{paper_id}")
            response.raise_for_status()
            return self._parse_work(response.json())
        except httpx.HTTPError as e:
            logger.warning("OpenAlex get_paper failed: %s", e)
            return None

    async def get_citations(self, paper_id: str, limit: int = 50) -> list[Paper]:
        try:
            response = await self._client.get(
                "/works",
                params={"filter": f"cites:{paper_id}", "per_page": limit},
            )
            response.raise_for_status()
            return [
                p for item in response.json().get("results", []) if (p := self._parse_work(item))
            ]
        except httpx.HTTPError as e:
            logger.warning("OpenAlex citations failed: %s", e)
            return []

    async def get_references(self, paper_id: str, limit: int = 50) -> list[Paper]:
        try:
            response = await self._client.get(
                "/works",
                params={"filter": f"cited_by:{paper_id}", "per_page": limit},
            )
            response.raise_for_status()
            return [
                p for item in response.json().get("results", []) if (p := self._parse_work(item))
            ]
        except httpx.HTTPError as e:
            logger.warning("OpenAlex references failed: %s", e)
            return []

    def _parse_work(self, data: dict) -> Paper | None:
        if not data or not data.get("title"):
            return None

        authorships = data.get("authorships", []) or []
        doi_url = data.get("doi") or ""

        return Paper(
            id=data.get("id", "").split("/")[-1] if data.get("id") else "",
            source=self.source_name,
            title=data["title"],
            abstract=self._reconstruct_abstract(data.get("abstract_inverted_index")),
            authors=[
                Author(name=a.get("author", {}).get("display_name", "Unknown")) for a in authorships
            ],
            year=data.get("publication_year"),
            venue=((data.get("primary_location") or {}).get("source") or {}).get("display_name"),
            citation_count=data.get("cited_by_count"),
            url=data.get("id"),
            doi=doi_url.replace("https://doi.org/", "") if doi_url else None,
            keywords=[kw.get("display_name", "") for kw in (data.get("keywords") or []) if kw],
        )

    @staticmethod
    def _reconstruct_abstract(inverted_index: dict | None) -> str | None:
        if not inverted_index:
            return None
        word_positions: list[tuple[int, str]] = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort()
        return " ".join(w for _, w in word_positions)
