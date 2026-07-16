"""Semantic Scholar API client."""

import asyncio
import logging
import random

import httpx

from backend.pipeline.literature.base import AcademicSearchSource
from backend.pipeline.literature.contracts import (
    AttemptObserver,
    SourceQueryPlan,
    SourceSearchOutcome,
    canonical_plan_json,
)
from backend.pipeline.literature.models import Author, Paper, SearchResult
from backend.pipeline.literature.result_accounting import reconcile_source_results

logger = logging.getLogger(__name__)

DEFAULT_API_BASE = "https://api.semanticscholar.org/graph/v1"
SEARCH_FIELDS = "title,abstract,year,authors,citationCount,url,externalIds,venue,fieldsOfStudy"


def _get_api_base() -> str:
    """Read Semantic Scholar API base URL from settings, falling back to default."""
    try:
        from backend.config import get_settings
        return get_settings().semantic_scholar_api_url
    except Exception:
        return DEFAULT_API_BASE


class SemanticScholarSource(AcademicSearchSource):
    def __init__(self, api_key: str | None = None, api_base: str | None = None):
        base = api_base or _get_api_base()
        self._headers = {"x-api-key": api_key} if api_key else {}
        self._client = httpx.AsyncClient(
            base_url=base,
            headers=self._headers,
            timeout=30.0,
        )

    @property
    def source_name(self) -> str:
        return "semantic_scholar"

    def build_query_plan(
        self,
        query: str,
        limit: int = 20,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> SourceQueryPlan:
        """Build a deterministic Semantic Scholar query plan. Pure — no network access."""
        params = {"query": query, "limit": min(limit, 100)}
        if year_from or year_to:
            params["year"] = f"{year_from or ''}-{year_to or ''}"
        return SourceQueryPlan(
            source="semantic_scholar",
            schema_version="source_query_v1",
            translated_query=canonical_plan_json("semantic_scholar", params),
            request_parameters=params,
        )

    async def execute_query_plan(
        self,
        plan: SourceQueryPlan,
        *,
        retry_max_retries: int = 5,
        retry_base_delay: float = 2.0,
        retry_max_delay: float = 30.0,
        attempt_observer: AttemptObserver | None = None,
    ) -> SourceSearchOutcome:
        """Execute the Semantic Scholar query plan with retries and structured failures."""
        # Reconstruct httpx params from the plan — one source of truth.
        rp = dict(plan.request_parameters)
        params = {
            "query": rp["query"],
            "limit": rp["limit"],
            "fields": SEARCH_FIELDS,
        }
        if "year" in rp:
            params["year"] = rp["year"]

        attempts_made = 0
        total_backoff = 0.0
        for attempt in range(retry_max_retries + 1):
            try:
                if attempt_observer is not None:
                    await attempt_observer.attempt_started()
                attempts_made += 1
                response = await self._client.get(
                    "/paper/search", params=params
                )  # type: ignore[arg-type]
                response.raise_for_status()
                data = response.json()
                break
            except httpx.HTTPStatusError as e:
                code = e.response.status_code
                if code != 429 or attempt >= retry_max_retries:
                    if code == 429:
                        cat, fc = "rate_limit", "http_429"
                    elif code == 401:
                        cat, fc = "authentication", "http_401"
                    elif code == 403:
                        cat, fc = "authorization", "http_403"
                    elif 400 <= code < 500:
                        cat, fc = "provider_rejection", f"http_{code}"
                    elif 500 <= code < 600:
                        cat, fc = "provider_internal", f"http_{code}"
                    else:
                        cat, fc = "transport", f"http_{code}"
                    logger.warning("Semantic Scholar search failed: %s", e)
                    return SourceSearchOutcome(
                        results=[],
                        status="failed",
                        attempt_count=attempts_made,
                        error_detail=f"{type(e).__name__}: {e}",
                        failure_category=cat,
                        failure_code=fc,
                    )
                delay = min(
                    retry_base_delay * (2 ** attempt)
                    + random.uniform(0, 1),
                    retry_max_delay,
                )
                total_backoff += delay
                if total_backoff > 120.0:
                    logger.warning(
                        "Semantic Scholar total backoff cap exceeded:"
                        " %.1fs",
                        total_backoff,
                    )
                    return SourceSearchOutcome(
                        results=[],
                        status="failed",
                        attempt_count=attempts_made,
                        error_detail=f"Semantic Scholar rate-limited after {attempts_made} attempts",
                        failure_category="rate_limit",
                        failure_code="http_429",
                    )
                logger.warning(
                    "Semantic Scholar rate-limited (429),"
                    " retry %d/%d in %.1fs",
                    attempt + 1,
                    retry_max_retries,
                    delay,
                )
                await asyncio.sleep(delay)
            except (httpx.HTTPError, KeyError) as e:
                logger.warning("Semantic Scholar search failed: %s", e)
                return SourceSearchOutcome(
                    results=[],
                    status="failed",
                    attempt_count=attempts_made,
                    error_detail=f"{type(e).__name__}: {e}",
                    failure_category="transport",
                    failure_code="connection_error",
                )

        if not isinstance(data, dict) or "data" not in data:
            logger.warning("Semantic Scholar parse failed: malformed response")
            return SourceSearchOutcome(
                results=[],
                status="failed",
                attempt_count=attempts_made,
                error_detail="Malformed response: missing 'data' key",
                failure_category="provider_internal",
                failure_code="parse_error",
            )

        raw_items = data.get("data", [])
        raw_count = len(raw_items)

        results = []
        for item in raw_items:
            paper = self._parse_paper(item)
            if paper:
                results.append(
                    SearchResult(
                        paper=paper,
                        relevance_score=item.get("relevanceScore"),
                        source=self.source_name,
                    )
                )

        normalized_count = len(results)
        rejected_count = raw_count - normalized_count

        source_unique, accounting = reconcile_source_results(
            raw_result_count=raw_count,
            normalized_results=results,
            rejected_result_count=rejected_count,
        )
        return SourceSearchOutcome(
            results=source_unique,
            status="success",
            attempt_count=attempts_made,
            accounting=accounting,
        )

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
                Author(name=a.get("name", "Unknown"), id=a.get("authorId")) for a in authors_data
            ],
            year=data.get("year"),
            venue=data.get("venue"),
            citation_count=data.get("citationCount"),
            url=data.get("url"),
            doi=external_ids.get("DOI"),
            arxiv_id=external_ids.get("ArXiv"),
            keywords=data.get("fieldsOfStudy", []) or [],
        )
