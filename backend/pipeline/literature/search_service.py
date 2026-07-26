"""Unified literature search across multiple academic APIs."""

import asyncio
import hashlib
import logging
import time
from typing import Any

from backend.config import get_settings
from backend.pipeline.literature.base import AcademicSearchSource
from backend.pipeline.literature.models import Paper, SearchResult

logger = logging.getLogger(__name__)


class SearchService:
    """Search across multiple academic sources with deduplication."""

    def __init__(
        self,
        sources: list[AcademicSearchSource] | None = None,
        search_depth: int = 1,
        embedding_provider: Any | None = None,
    ):
        if sources is None:
            sources = self._default_sources()
        self._sources: dict[str, AcademicSearchSource] = {s.source_name: s for s in sources}
        self._search_depth = max(1, search_depth)
        self._embedding_provider = embedding_provider

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
            papers = self._deduplicate(all_results)
        else:
            return [r.paper for r in all_results]

        # Relevance filtering (A-02: runs after deduplication)
        if self._embedding_provider is not None:
            try:
                from backend.pipeline.literature.relevance_filter import RelevanceFilter
                relevance_filter = RelevanceFilter(embedding_provider=self._embedding_provider)
                pre_count = len(all_results)
                filtered_results = await relevance_filter.filter(all_results, query)
                post_count = len(filtered_results)
                logger.info(
                    "Relevance filter: %d → %d papers (embedding provider active)",
                    pre_count, post_count,
                )
                return [r.paper for r in filtered_results]
            except Exception as e:
                logger.warning("Relevance filter failed: %s — returning unfiltered results", e)

        return papers

    async def search_all_with_provenance(
        self,
        query: str,
        query_key: str,
        sources: list[str] | None = None,
        limit_per_source: int = 20,
        year_from: int | None = None,
        year_to: int | None = None,
        *,
        search_query_id: int | None = None,
        db_engine: Any | None = None,
        intended_sources: list[str] | None = None,
    ) -> Any:
        """Search with provenance — returns CandidateWithDiscoveries or SearchBatchOutcome.

        P0.2.2: When ``search_query_id`` and ``db_engine`` are provided, this
        method records the full execution lifecycle for every intended source
        via ``ExecutionRecorder``. Failed, timed-out, and skipped attempts
        remain visible in the returned ``SearchBatchOutcome.executions`` even
        when no candidates are produced.

        When ``search_query_id`` is None (legacy/no-DB path), behaves exactly
        as before — returns ``list[CandidateWithDiscoveries]`` with no
        execution recording.

        Args:
            query: the logical query text
            query_key: deterministic key for this logical query
            sources: source names to search (default: all active)
            limit_per_source: max results per source
            year_from/year_to: optional date filters
            search_query_id: DB PK of the SearchQuery (governed path)
            db_engine: SQLAlchemy engine for execution recording
            intended_sources: canonical source set (defaults to active keys)

        Returns:
            ``SearchBatchOutcome`` on the governed path (with candidates +
            executions), or ``list[CandidateWithDiscoveries]`` on the legacy path.
        """
        from backend.pipeline.persistence import (
            CandidateWithDiscoveries,
            DiscoveryMetadata,
        )

        governed = search_query_id is not None and db_engine is not None

        # Determine intended and active sources.
        if intended_sources is None:
            intended_sources = sorted(self._sources.keys())
        else:
            # Normalize: lowercase, trim, deduplicate, preserve order.
            seen: set[str] = set()
            normalized: list[str] = []
            for s in intended_sources:
                ns = s.strip().lower()
                if ns and ns not in seen:
                    seen.add(ns)
                    normalized.append(ns)
            intended_sources = normalized

        if sources is None:
            sources = list(self._sources.keys())
        active = {
            name: self._sources[name]
            for name in sources
            if name in self._sources
        }

        # Assert: every active adapter must be in the intended set.
        for name in active:
            if name not in intended_sources:
                raise ValueError(
                    f"active adapter {name!r} is not in intended_sources "
                    f"{intended_sources!r} — configuration error"
                )

        if not active and not governed:
            logger.warning("No valid sources specified: %s", sources)
            from backend.pipeline.literature.contracts import SearchBatchOutcome
            return SearchBatchOutcome(candidates=[], executions=[])

        all_results: list[SearchResult] = []
        executions: list = []

        if governed:
            from backend.pipeline.literature.execution_recorder import ExecutionRecorder

            recorder = ExecutionRecorder(db_engine)

            # 1. Ensure pending execution rows for ALL intended sources.
            source_to_exec_id = recorder.ensure_pending_executions(
                search_query_id, intended_sources,  # type: ignore[arg-type]
            )

            # 2. Skip intended sources with no active adapter.
            for src in intended_sources:
                if src not in active:
                    recorder.skip_unavailable(
                        source_to_exec_id[src],
                        reason="no active adapter / source disabled",
                    )
                    from backend.pipeline.literature.contracts import AttemptOutcome
                    executions.append(AttemptOutcome(
                        execution_id=source_to_exec_id[src],
                        source=src,
                        status="skipped",
                        attempt_count=0,
                        error_detail="no active adapter",
                    ))

            # 3. Concurrently invoke active adapters through the recorder.
            async def _run_one(src_name: str, adapter: AcademicSearchSource):
                return await recorder.run_execution(
                    source_to_exec_id[src_name], src_name, adapter, query,
                    limit=limit_per_source, year_from=year_from, year_to=year_to,
                )

            outcomes = await asyncio.gather(
                *(
                    _run_one(name, adapter)
                    for name, adapter in active.items()
                ),
                return_exceptions=True,  # B-10: don't cancel other sources on failure
            )

            # P0.2.5: Attach execution identity to each source-unique result.
            # Build DiscoveryMetadata with execution_id + source_result_key.
            from backend.pipeline.literature.result_accounting import (
                build_source_result_identity,
            )

            all_discovery_routes: list = []  # list[DiscoveryMetadata]
            linkage_expectations: list = []

            for outcome in outcomes:
                # B-10: with return_exceptions=True, outcomes may contain
                # exceptions from recorder.run_execution. Skip those — the
                # recorder has already persisted the failure to the DB.
                if isinstance(outcome, Exception):
                    logger.warning(
                        "Source execution raised during gather: %s", outcome,
                    )
                    continue
                executions.append(outcome)
                all_results.extend(outcome.results)

                from backend.pipeline.literature.contracts import (
                    ExecutionLinkageExpectation,
                )
                # Build linkage expectation for this execution
                exp_count = None
                if outcome.status == "success" or outcome.status == "partial":
                    exp_count = len(outcome.results)
                linkage_expectations.append(ExecutionLinkageExpectation(
                    execution_id=outcome.execution_id,
                    search_query_id=search_query_id,  # type: ignore[arg-type]
                    source=outcome.source,
                    expected_discovery_count=exp_count,
                    accounting_status="reconciled" if exp_count is not None else "incomplete",
                ))

                # Build discovery routes for each source-unique result
                for rank, result in enumerate(outcome.results):
                    srk, method = build_source_result_identity(result)
                    all_discovery_routes.append(DiscoveryMetadata(
                        query_key=query_key,
                        source=outcome.source,
                        execution_id=outcome.execution_id,
                        source_result_key=srk,
                        source_record_id=result.paper.id,
                        source_rank=rank,
                        discovery_origin="remote_search",
                        canonicalization_method=method,
                        linkage_schema_version="linkage_v1",
                    ))

            # Also build expectations for skipped executions
            for exec_outcome in executions:
                if exec_outcome.status == "skipped":
                    linkage_expectations.append(ExecutionLinkageExpectation(
                        execution_id=exec_outcome.execution_id,
                        search_query_id=search_query_id,  # type: ignore[arg-type]
                        source=exec_outcome.source,
                        expected_discovery_count=None,
                        accounting_status="incomplete",
                    ))

            candidates = self._deduplicate_with_provenance_linkage(
                all_results, all_discovery_routes, query_key,
            )
            from backend.pipeline.literature.contracts import SearchBatchOutcome
            return SearchBatchOutcome(candidates=candidates, executions=executions)

        else:
            # Legacy path: no execution recording, bare adapter calls.
            # Adapters now return SourceSearchOutcome; unwrap for compat.
            from backend.pipeline.literature.contracts import SourceSearchOutcome

            tasks = [
                source.search(query, limit=limit_per_source, year_from=year_from, year_to=year_to)
                for source in active.values()
            ]
            outcomes_raw = await asyncio.gather(*tasks, return_exceptions=True)

            for name, result in zip(active.keys(), outcomes_raw, strict=True):
                if isinstance(result, Exception):
                    logger.warning("Search failed for %s: %s", name, result)
                elif isinstance(result, SourceSearchOutcome):
                    if result.status == "success" or result.status == "partial":
                        all_results.extend(result.results)
                    else:
                        logger.warning(
                            "Search failed for %s: %s", name, result.error_detail,
                        )
                else:
                    logger.warning(
                        "Unexpected return type from %s: %s", name, type(result),
                    )

            return self._deduplicate_with_provenance(all_results, query_key)

    @staticmethod
    def _deduplicate_with_provenance(
        results: list[SearchResult], query_key: str,
    ) -> list:
        """Deduplicate papers while preserving ALL discovery routes.

        Unlike _deduplicate which discards lower-priority sources, this
        method accumulates DiscoveryMetadata for every source that found
        the same paper. The winning Paper is chosen by source priority
        (same as _deduplicate), but ALL sources are recorded as discovery
        events.

        Returns:
            list[CandidateWithDiscoveries]
        """
        from backend.pipeline.persistence import CandidateWithDiscoveries, DiscoveryMetadata

        source_priority = {"semantic_scholar": 0, "pubmed": 1, "openalex": 2, "crossref": 3, "arxiv": 4}

        # Sort to prefer semantic_scholar data when choosing the canonical paper
        sorted_results = sorted(
            results,
            key=lambda r: source_priority.get(r.source, 99),
        )

        # Keyed accumulation: dedup_key → (winning_paper, [DiscoveryMetadata])
        by_key: dict[str, tuple] = {}

        for rank_offset, result in enumerate(sorted_results):
            paper = result.paper
            key = paper.doi if paper.doi else _title_hash(paper.title)

            disc = DiscoveryMetadata(
                query_key=query_key,
                source=result.source,
                source_record_id=paper.id,
                source_rank=rank_offset,
                discovery_origin="remote_search",
            )

            if key in by_key:
                # Paper already seen — add this discovery route
                winning_paper, discoveries = by_key[key]
                discoveries.append(disc)
            else:
                # First occurrence (highest priority source wins)
                by_key[key] = (paper, [disc])

        return [
            CandidateWithDiscoveries(paper=paper, discoveries=discoveries)
            for paper, discoveries in by_key.values()
        ]

    @staticmethod
    def _deduplicate_with_provenance_linkage(
        results: list[SearchResult],
        discovery_routes: list,
        query_key: str,
    ) -> list:
        """Deduplicate while preserving pre-built DiscoveryMetadata with linkage.

        P0.2.5: Unlike _deduplicate_with_provenance, this method receives
        pre-constructed DiscoveryMetadata objects (carrying execution_id,
        source_result_key, linkage_schema_version) and accumulates them
        without dropping linkage fields.

        The results and discovery_routes are parallel arrays — routes[i]
        is the metadata for results[i].
        """
        from backend.pipeline.persistence import CandidateWithDiscoveries

        source_priority = {"semantic_scholar": 0, "pubmed": 1, "openalex": 2, "crossref": 3, "arxiv": 4}

        # Sort by source priority but keep results paired with their routes
        paired = list(zip(results, discovery_routes, strict=True))
        paired.sort(key=lambda p: source_priority.get(p[0].source, 99))

        by_key: dict[str, tuple] = {}
        for result, route in paired:
            paper = result.paper
            key = paper.doi if getattr(paper, "doi", None) else _title_hash(paper.title)

            if key in by_key:
                winning_paper, discoveries = by_key[key]
                discoveries.append(route)
            else:
                by_key[key] = (paper, [route])

        return [
            CandidateWithDiscoveries(paper=paper, discoveries=discoveries)
            for paper, discoveries in by_key.values()
        ]

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

        # Sort to prefer semantic_scholar data when merging (A-01)
        source_priority = {"semantic_scholar": 0, "pubmed": 1, "openalex": 2, "crossref": 3, "arxiv": 4}
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

        Conditionally includes PubMed (pubmed_enabled) and CrossRef
        (crossref_enabled) alongside Semantic Scholar, OpenAlex, and arXiv.

        Source ordering (preserved from original):
        - Without S2 key: OpenAlex → arXiv (OpenAlex first to avoid rate limiting)
        - With S2 key: S2 → arXiv → OpenAlex
        - PubMed and CrossRef appended when enabled
        """
        from backend.pipeline.literature.arxiv_source import ArxivSource
        from backend.pipeline.literature.openalex_source import OpenAlexSource
        from backend.pipeline.literature.semantic_scholar import SemanticScholarSource

        settings = get_settings()
        sources: list[AcademicSearchSource] = []

        # Core sources — preserve original ordering
        if not settings.semantic_scholar_api_key:
            logger.info(
                "No S2 API key set — S2 excluded to avoid 429 rate limiting. "
                "Get a free key: https://www.semanticscholar.org/product/api#api-key"
            )
            sources.append(OpenAlexSource(email=settings.openalex_email))
            sources.append(ArxivSource())
        else:
            sources.append(
                SemanticScholarSource(api_key=settings.semantic_scholar_api_key)
            )
            sources.append(ArxivSource())
            sources.append(OpenAlexSource(email=settings.openalex_email))

        # PubMed (toggleable via config, HB-03)
        if settings.pubmed_enabled:
            from backend.pipeline.literature.pubmed_source import PubMedSource
            sources.append(PubMedSource(api_key=settings.pubmed_api_key))
            logger.debug("PubMed source enabled (api_key=%s)", "set" if settings.pubmed_api_key else "none")

        # CrossRef (toggleable via config, HB-03)
        if settings.crossref_enabled:
            from backend.pipeline.literature.crossref_source import CrossRefSource
            mailto = settings.openalex_email or ""
            sources.append(CrossRefSource(mailto=mailto))
            logger.debug("CrossRef source enabled (mailto=%s)", mailto or "<empty>")

        return sources

    async def health_check(self, timeout: float = 5.0) -> dict[str, dict[str, Any]]:
        """Check connectivity of each registered source.

        For each source, runs a trivial search with a timeout and reports
        health status and latency.

        Returns:
            Dict mapping source_name → {"healthy": bool, "latency_ms": float}.
        """
        results: dict[str, dict[str, Any]] = {}

        async def _check_one(name: str, source: AcademicSearchSource) -> None:
            try:
                start = time.monotonic()
                await asyncio.wait_for(
                    source.search("test", limit=1),
                    timeout=timeout,
                )
                elapsed_ms = (time.monotonic() - start) * 1000
                results[name] = {"healthy": True, "latency_ms": round(elapsed_ms, 2)}
            except Exception as e:
                elapsed_ms = (time.monotonic() - start) * 1000
                logger.warning("Health check failed for %s: %s", name, e)
                results[name] = {"healthy": False, "latency_ms": round(elapsed_ms, 2)}

        await asyncio.gather(
            *(_check_one(name, src) for name, src in self._sources.items()),
            return_exceptions=True,
        )
        return results


def _title_hash(title: str) -> str:
    normalized = title.lower().strip().replace(" ", "")
    return hashlib.md5(normalized.encode()).hexdigest()
