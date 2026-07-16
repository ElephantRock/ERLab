"""PubMed literature source via NCBI E-utilities API.

No API key required (graceful degradation with rate limiting).
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.pipeline.literature.base import AcademicSearchSource
from backend.pipeline.literature.contracts import AttemptObserver, SourceSearchOutcome
from backend.pipeline.literature.models import Author, Paper, SearchResult

logger = logging.getLogger(__name__)

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


class PubMedSource(AcademicSearchSource):
    """Literature source using PubMed NCBI E-utilities.

    No API key required. Rate limited to 3 req/s without key.
    With NCBI API key: 10 req/s.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=30.0)

    @property
    def source_name(self) -> str:
        return "pubmed"

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
        """Search PubMed for papers matching the query."""
        try:
            attempts_made = 0
            # Build search query with date filter
            search_term = query
            if year_from or year_to:
                y_from = year_from or 1900
                y_to = year_to or 2030
                search_term += f" AND ({y_from}:{y_to}[pdat])"

            # Step 1: ESearch to get PMIDs
            params: dict[str, Any] = {
                "db": "pubmed",
                "term": search_term,
                "retmax": min(limit, 50),
                "retmode": "json",
                "sort": "relevance",
            }
            if self._api_key:
                params["api_key"] = self._api_key

            if attempt_observer is not None:
                await attempt_observer.attempt_started()
            attempts_made += 1
            response = await self._client.get(ESEARCH_URL, params=params)
            response.raise_for_status()
            data = response.json()

            id_list = data.get("esearchresult", {}).get("idlist", [])
            if not id_list:
                return SourceSearchOutcome(results=[], status="success", attempt_count=attempts_made)

            # Step 2: EFetch to get details
            fetch_params: dict[str, Any] = {
                "db": "pubmed",
                "id": ",".join(id_list),
                "retmode": "xml",
            }
            if self._api_key:
                fetch_params["api_key"] = self._api_key

            if attempt_observer is not None:
                await attempt_observer.attempt_started()
            attempts_made += 1
            fetch_response = await self._client.get(EFETCH_URL, params=fetch_params)
            fetch_response.raise_for_status()

            # Parse XML response (simplified)
            results = self._parse_results(fetch_response.text)
            return SourceSearchOutcome(results=results[:limit], status="success", attempt_count=attempts_made)

        except Exception as e:
            logger.warning("PubMed search failed: %s", e)
            return SourceSearchOutcome(results=[], status="failed", attempt_count=attempts_made, error_detail=f"{type(e).__name__}: {e}")

    async def get_paper(self, paper_id: str) -> Paper | None:
        """Get a single paper by PMID."""
        try:
            params = {"db": "pubmed", "id": paper_id, "retmode": "xml"}
            if self._api_key:
                params["api_key"] = self._api_key
            response = await self._client.get(EFETCH_URL, params=params)
            response.raise_for_status()
            papers = self._parse_results(response.text)
            return papers[0].paper if papers else None
        except Exception as e:
            logger.warning("PubMed get_paper failed: %s", e)
            return None

    async def get_citations(self, paper_id: str, limit: int = 50) -> list[Paper]:
        """Get papers citing this paper (not available via PubMed E-utilities)."""
        return []

    async def get_references(self, paper_id: str, limit: int = 50) -> list[Paper]:
        """Get papers referenced by this paper (not available via PubMed E-utilities)."""
        return []

    def _parse_results(self, xml_text: str) -> list[SearchResult]:
        """Parse PubMed XML into SearchResult list.

        Uses simple string parsing to avoid XML dependency.
        For production, use lxml or xml.etree.
        """
        results = []
        articles = xml_text.split("<PubmedArticle>")[1:]  # Skip header

        for article_text in articles[:50]:
            title = self._extract_tag(article_text, "ArticleTitle")
            abstract = self._extract_tag(article_text, "AbstractText")
            year_str = self._extract_tag(article_text, "Year")
            pmid = self._extract_tag(article_text, "PMID")
            journal = self._extract_tag(article_text, "Title")

            if not title:
                continue

            # Extract authors
            authors = []
            author_blocks = article_text.split("<Author ")
            for block in author_blocks[1:]:
                last = self._extract_tag(block, "LastName")
                fore = self._extract_tag(block, "ForeName")
                if last:
                    authors.append(Author(name=f"{fore} {last}".strip()))

            paper = Paper(
                id=f"pubmed:{pmid or title[:20]}",
                title=title,
                abstract=abstract or "",
                year=int(year_str) if year_str and year_str.isdigit() else None,
                authors=authors,
                doi="",
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                source="pubmed",
                citation_count=None,
                venue=journal,
            )

            results.append(SearchResult(
                paper=paper,
                relevance_score=1.0,  # PubMed doesn't provide scores
                source="pubmed",
            ))

        return results

    @staticmethod
    def _extract_tag(text: str, tag: str) -> str:
        """Extract text content from an XML tag (simple parser)."""
        import re
        match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", text, re.DOTALL)
        if match:
            content = match.group(1)
            # Remove nested tags
            content = re.sub(r"<[^>]+>", "", content)
            return content.strip()
        return ""
