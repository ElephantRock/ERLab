"""Unified literature search across multiple academic APIs."""

import asyncio
import hashlib
import logging

from backend.config import get_settings
from backend.pipeline.literature.base import AcademicSearchSource
from backend.pipeline.literature.models import Paper, SearchResult

logger = logging.getLogger(__name__)


class SearchService:
    """Search across multiple academic sources with deduplication."""

    def __init__(self, sources: list[AcademicSearchSource] | None = None, search_depth: int = 1):
        if sources is None:
            sources = self._default_sources()
        self._sources: dict[str, AcademicSearchSource] = {s.source_name: s for s in sources}
        self._search_depth = max(1, search_depth)

    async def search_all(
        self,
        query: str,
        sources: list[str] | None = None,
        limit_per_source: int = 20,
        year_from: int | None = None,
        year_to: int | None = None,
        deduplicate: bool = True,
    ) -> list[Paper]:
        """Search specified sources concurrently, deduplicate, and return unified results."""
        if sources is None:
            sources = list(self._sources.keys())

        active = {name: self._sources[name] for name in sources if name in self._sources}
        if not active:
            logger.warning("No valid sources specified: %s", sources)
            return []

        # Concurrent search
        tasks = [
            source.search(query, limit=limit_per_source, year_from=year_from, year_to=year_to)
            for source in active.values()
        ]
        results_per_source = await asyncio.gather(*tasks, return_exceptions=True)

        all_results: list[SearchResult] = []
        for name, result in zip(active.keys(), results_per_source, strict=True):
            if isinstance(result, Exception):
                logger.warning("Search failed for %s: %s", name, result)
            else:
                all_results.extend(result)  # type: ignore[arg-type]

        if deduplicate:
            return self._deduplicate(all_results)
        return [r.paper for r in all_results]

    async def get_citations(self, paper: Paper, limit: int = 50) -> list[Paper]:
        """Get citations from the paper's source."""
        source = self._sources.get(paper.source)
        if not source:
            return []
        return await source.get_citations(paper.id, limit=limit)

    async def search_recursive(
        self,
        query: str,
        max_depth: int | None = None,
        limit_per_source: int = 20,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[Paper]:
        """Recursive search: use initial results to generate follow-up queries.

        At each depth level, extracts key terms from found papers and
        uses them as additional search queries.
        """
        depth = max_depth or self._search_depth
        all_papers = await self.search_all(
            query, limit_per_source=limit_per_source,
            year_from=year_from, year_to=year_to,
        )

        if depth <= 1 or not all_papers:
            return all_papers

        # Extract key terms from top papers for follow-up queries
        seen_titles = {p.title.lower().strip() for p in all_papers}

        for level in range(1, depth):
            followup_queries = self._extract_followup_queries(all_papers, query)
            # Fire all follow-up queries concurrently
            followup_results = await asyncio.gather(
                *(
                    self.search_all(
                        fq, limit_per_source=min(limit_per_source, 10),
                        year_from=year_from, year_to=year_to,
                    )
                    for fq in followup_queries[:3]
                ),
                return_exceptions=True,
            )
            for result in followup_results:
                if isinstance(result, Exception):
                    logger.warning("Recursive search failed: %s", result)
                    continue
                for p in result:
                    if p.title.lower().strip() not in seen_titles:
                        all_papers.append(p)
                        seen_titles.add(p.title.lower().strip())

        logger.info(
            "Recursive search (depth=%d): %d total papers",
            depth, len(all_papers),
        )
        return all_papers

    @staticmethod
    def _extract_followup_queries(papers: list[Paper], original_query: str) -> list[str]:
        """Extract follow-up search queries from paper titles and venues."""
        queries = []
        for p in papers[:5]:
            if p.title and len(p.title) > 20:
                # Use first half of title as a follow-up query
                words = p.title.split()
                if len(words) > 4:
                    subquery = " ".join(words[:len(words)//2])
                    queries.append(subquery)
        return queries

    async def get_references(self, paper: Paper, limit: int = 50) -> list[Paper]:
        """Get references from the paper's source."""
        source = self._sources.get(paper.source)
        if not source:
            return []
        return await source.get_references(paper.id, limit=limit)

    @staticmethod
    def _deduplicate(results: list[SearchResult]) -> list[Paper]:
        """Deduplicate papers by DOI or title hash, preferring Semantic Scholar data."""
        seen: list[Paper] = []  # type: ignore[assignment]
        dedup_keys: set[str] = set()

        # Sort to prefer semantic_scholar data when merging
        source_priority = {"semantic_scholar": 0, "arxiv": 1, "openalex": 2}
        sorted_results = sorted(
            results,
            key=lambda r: source_priority.get(r.source, 99),
        )

        for result in sorted_results:
            paper = result.paper
            key = paper.doi if paper.doi else _title_hash(paper.title)
            if key in dedup_keys:
                continue
            dedup_keys.add(key)
            seen.append(paper)  # type: ignore[arg-type]

        return seen  # type: ignore[return-value]

    @staticmethod
    def _default_sources() -> list[AcademicSearchSource]:
        """Create default sources from settings.

        When no Semantic Scholar API key is set, OpenAlex is placed first
        to avoid severe rate limiting (Fix #11b).
        """
        from backend.pipeline.literature.arxiv_source import ArxivSource
        from backend.pipeline.literature.openalex_source import OpenAlexSource
        from backend.pipeline.literature.semantic_scholar import SemanticScholarSource

        settings = get_settings()

        if not settings.semantic_scholar_api_key:
            logger.info(
                "No S2 API key set — using OpenAlex + arXiv only. "
                "S2 excluded to avoid 429 rate limiting. Get a free key: "
                "https://www.semanticscholar.org/product/api#api-key"
            )
            return [
                OpenAlexSource(email=settings.openalex_email),
                ArxivSource(),
            ]

        return [
            SemanticScholarSource(api_key=settings.semantic_scholar_api_key),
            ArxivSource(),
            OpenAlexSource(email=settings.openalex_email),
        ]


def _title_hash(title: str) -> str:
    normalized = title.lower().strip().replace(" ", "")
    return hashlib.md5(normalized.encode()).hexdigest()
