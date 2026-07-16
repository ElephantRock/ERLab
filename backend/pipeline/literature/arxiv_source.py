"""arXiv API client."""

import asyncio
import logging
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from backend.pipeline.literature.base import AcademicSearchSource
from backend.pipeline.literature.contracts import AttemptObserver, SourceSearchOutcome
from backend.pipeline.literature.models import Author, Paper, SearchResult

logger = logging.getLogger(__name__)

ARXIV_API = "https://export.arxiv.org/api/query"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"


class ArxivSource(AcademicSearchSource):
    BACKOFF_DELAYS: list[float] = [5, 15, 30]
    MAX_RETRIES: int = 3

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=30.0)

    @property
    def source_name(self) -> str:
        return "arxiv"

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
        search_query = f'all:"{query}"'
        if year_from or year_to:
            search_query += (
                f" AND submittedDate:[{year_from or 2000}01010000 TO {year_to or 2030}12312359]"
            )

        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": min(limit, 50),
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

        attempts_made = 0
        try:
            # arXiv asks for 1 req / 3 seconds
            await asyncio.sleep(3)
            for attempt in range(self.MAX_RETRIES + 1):
                if attempt_observer is not None:
                    await attempt_observer.attempt_started()
                attempts_made += 1
                response = await self._client.get(ARXIV_API, params=params)
                if response.status_code == 429:
                    if attempt < self.MAX_RETRIES:
                        await asyncio.sleep(self.BACKOFF_DELAYS[attempt])
                        continue
                    logger.warning(
                        "arXiv rate-limited after %d retries", self.MAX_RETRIES
                    )
                    return SourceSearchOutcome(
                        results=[],
                        status="failed",
                        attempt_count=attempts_made,
                        error_detail=f"arXiv rate-limited after {attempts_made} attempts",
                    )
                response.raise_for_status()
                results = self._parse_feed(response.text)
                return SourceSearchOutcome(
                    results=results,
                    status="success",
                    attempt_count=attempts_made,
                )
        except httpx.HTTPError as e:
            logger.warning("arXiv search failed: %s", e)
            return SourceSearchOutcome(
                results=[],
                status="failed",
                attempt_count=attempts_made,
                error_detail=f"{type(e).__name__}: {e}",
            )

        return SourceSearchOutcome(
            results=[], status="failed", attempt_count=attempts_made,
            error_detail="arXiv search: unreachable fallthrough",
        )

    async def get_paper(self, paper_id: str) -> Paper | None:
        try:
            await asyncio.sleep(3)
            response = await self._client.get(
                ARXIV_API, params={"id_list": paper_id, "max_results": 1}
            )
            response.raise_for_status()
            results = self._parse_feed(response.text)
            return results[0].paper if results else None
        except httpx.HTTPError as e:
            logger.warning("arXiv get_paper failed: %s", e)
            return None

    async def get_citations(self, paper_id: str, limit: int = 50) -> list[Paper]:
        # arXiv API doesn't support citation lookup
        return []

    async def get_references(self, paper_id: str, limit: int = 50) -> list[Paper]:
        # arXiv API doesn't support reference lookup
        return []

    def _parse_feed(self, xml_text: str) -> list[SearchResult]:
        results: list[SearchResult] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return results

        for entry in root.findall(f"{ATOM_NS}entry"):
            title = self._get_text(entry, f"{ATOM_NS}title")
            if not title:
                continue

            arxiv_id_raw = self._get_text(entry, f"{ATOM_NS}id") or ""
            arxiv_id = arxiv_id_raw.split("/abs/")[-1] if "/abs/" in arxiv_id_raw else arxiv_id_raw

            abstract = self._get_text(entry, f"{ATOM_NS}summary") or ""
            abstract = abstract.strip().replace("\n", " ")

            authors = [
                Author(name=self._get_text(a, f"{ATOM_NS}name") or "Unknown")
                for a in entry.findall(f"{ATOM_NS}author")
            ]

            published = self._get_text(entry, f"{ATOM_NS}published") or ""
            year = int(published[:4]) if len(published) >= 4 else None

            categories = [
                cat.get("term", "") for cat in entry.findall(f"{ARXIV_NS}primary_category")
            ]

            paper = Paper(
                id=arxiv_id,
                source=self.source_name,
                title=title.strip(),
                abstract=abstract,
                authors=authors,
                year=year,
                url=f"https://arxiv.org/abs/{arxiv_id}",
                arxiv_id=arxiv_id,
                keywords=categories,
            )
            results.append(SearchResult(paper=paper, source=self.source_name))

        return results

    @staticmethod
    def _get_text(element: ET.Element, path: str) -> str | None:
        child = element.find(path)
        return child.text if child is not None else None
