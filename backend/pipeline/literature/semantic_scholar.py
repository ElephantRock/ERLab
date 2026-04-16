"""Semantic Scholar API client."""

import asyncio
import logging

import httpx

from backend.pipeline.literature.base import AcademicSearchSource
from backend.pipeline.literature.models import Author, Paper, SearchResult

logger = logging.getLogger(__name__)

API_BASE = "https://api.semanticscholar.org/graph/v1"
SEARCH_FIELDS = "title,abstract,year,authors,citationCount,url,externalIds,venue,fieldsOfStudy"


class SemanticScholarSource(AcademicSearchSource):
    def __init__(self, api_key: str | None = None):
        self._headers = {"x-api-key": api_key} if api_key else {}
        self._client = httpx.AsyncClient(
            base_url=API_BASE,
            headers=self._headers,
            timeout=30.0,
        )

    @property
    def source_name(self) -> str:
        return "semantic_scholar"

    async def search(
        self,
        query: str,
        limit: int = 20,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[SearchResult]:
        params = {"query": query, "limit": min(limit, 100), "fields": SEARCH_FIELDS}
        if year_from or year_to:
            year_range = f"{year_from or ''}-{year_to or ''}"
            params["year"] = year_range

        try:
            response = await self._client.get("/paper/search", params=params)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, KeyError) as e:
            logger.warning("Semantic Scholar search failed: %s", e)
            return []

        results = []
        for item in data.get("data", []):
            paper = self._parse_paper(item)
            if paper:
                results.append(SearchResult(
                    paper=paper,
                    relevance_score=item.get("relevanceScore"),
                    source=self.source_name,
                ))
        return results

    async def get_paper(self, paper_id: str) -> Paper | None:
        try:
            response = await self._client.get(
                f"/paper/{paper_id}",
                params={"fields": SEARCH_FIELDS},
            )
            response.raise_for_status()
            return self._parse_paper(response.json())
        except httpx.HTTPError as e:
            logger.warning("Semantic Scholar get_paper failed: %s", e)
            return None

    async def get_citations(self, paper_id: str, limit: int = 50) -> list[Paper]:
        try:
            response = await self._client.get(
                f"/paper/{paper_id}/citations",
                params={"fields": SEARCH_FIELDS, "limit": limit},
            )
            response.raise_for_status()
            papers = []
            for item in response.json().get("data", []):
                paper = self._parse_paper(item.get("citingPaper", {}))
                if paper:
                    papers.append(paper)
            return papers
        except httpx.HTTPError as e:
            logger.warning("Semantic Scholar citations failed: %s", e)
            return []

    async def get_references(self, paper_id: str, limit: int = 50) -> list[Paper]:
        try:
            response = await self._client.get(
                f"/paper/{paper_id}/references",
                params={"fields": SEARCH_FIELDS, "limit": limit},
            )
            response.raise_for_status()
            papers = []
            for item in response.json().get("data", []):
                paper = self._parse_paper(item.get("citedPaper", {}))
                if paper:
                    papers.append(paper)
            return papers
        except httpx.HTTPError as e:
            logger.warning("Semantic Scholar references failed: %s", e)
            return []

    def _parse_paper(self, data: dict) -> Paper | None:
        if not data or not data.get("title"):
            return None

        external_ids = data.get("externalIds", {}) or {}
        authors_data = data.get("authors", []) or []

        return Paper(
            id=data.get("paperId", ""),
            source=self.source_name,
            title=data["title"],
            abstract=data.get("abstract"),
            authors=[
                Author(name=a.get("name", "Unknown"), id=a.get("authorId"))
                for a in authors_data
            ],
            year=data.get("year"),
            venue=data.get("venue"),
            citation_count=data.get("citationCount"),
            url=data.get("url"),
            doi=external_ids.get("DOI"),
            arxiv_id=external_ids.get("ArXiv"),
            keywords=data.get("fieldsOfStudy", []) or [],
        )
