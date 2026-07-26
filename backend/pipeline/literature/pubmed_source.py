"""PubMed literature source via NCBI E-utilities API.

No API key required (graceful degradation with rate limiting).
"""
from __future__ import annotations

import logging
from typing import Any

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

    def build_query_plan(
        self,
        query: str,
        limit: int = 20,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> SourceQueryPlan:
        """Build a deterministic PubMed query plan. Pure — no network access."""
        search_term = query
        if year_from or year_to:
            search_term = f"{query} AND ({year_from or 1900}:{year_to or 2030}[pdat])"
        params = {
            "term": search_term,
            "retmax": min(limit, 50),
            "workflow": ["esearch", "efetch"],
        }
        return SourceQueryPlan(
            source="pubmed",
            schema_version="source_query_v1",
            translated_query=canonical_plan_json("pubmed", params),
            request_parameters=params,
        )

    async def execute_query_plan(
        self,
        plan: SourceQueryPlan,
        *,
        attempt_observer: AttemptObserver | None = None,
    ) -> SourceSearchOutcome:
        """Execute the PubMed query plan: ESearch then EFetch.

        Reconstructs search_term and retmax from ``plan.request_parameters``
        (one source of truth). Calls the observer before EACH outbound
        request. Returns a ``SourceSearchOutcome`` with structured failures.
        """
        rp = dict(plan.request_parameters)
        search_term = rp["term"]
        retmax = rp["retmax"]

        attempts_made = 0
        try:
            # Step 1: ESearch to get PMIDs
            esearch_params: dict[str, Any] = {
                "db": "pubmed",
                "term": search_term,
                "retmax": retmax,
                "retmode": "json",
                "sort": "relevance",
            }
            if self._api_key:
                esearch_params["api_key"] = self._api_key

            if attempt_observer is not None:
                await attempt_observer.attempt_started()
            attempts_made += 1
            response = await self._client.get(ESEARCH_URL, params=esearch_params)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            code = e.response.status_code if hasattr(e, "response") else 0
            if code == 401:
                cat, fc = "authentication", "http_401"
            elif code == 403:
                cat, fc = "authorization", "http_403"
            elif code == 429:
                cat, fc = "rate_limit", "http_429"
            elif 400 <= code < 500:
                cat, fc = "provider_rejection", f"http_{code}"
            elif 500 <= code < 600:
                cat, fc = "provider_internal", f"http_{code}"
            else:
                cat, fc = "transport", "http_status_error"
            logger.warning("PubMed search failed (HTTP %s): %s", code, e)
            # ESearch failure / pre-attempt failure: no accounting.
            return SourceSearchOutcome(
                results=[],
                status="failed",
                attempt_count=attempts_made,
                error_detail=f"HTTPStatusError {code}",
                failure_category=cat,
                failure_code=fc,
            )
        except Exception as e:
            logger.warning("PubMed search failed: %s", e)
            # ESearch failure / pre-attempt failure: no accounting.
            return SourceSearchOutcome(
                results=[],
                status="failed",
                attempt_count=attempts_made,
                error_detail=f"{type(e).__name__}: {e}",
                failure_category="transport",
                failure_code="connection_error",
            )

        # ESearch succeeded: the PMID list is the known raw candidate population.
        id_list = data.get("esearchresult", {}).get("idlist", [])
        raw_count = len(id_list)

        if not id_list:
            from backend.pipeline.literature.contracts import SourceResultAccounting
            acct = SourceResultAccounting(
                schema_version="accounting_v1",
                raw_result_count=0, normalized_result_count=0,
                rejected_result_count=0, source_unique_count=0,
            )
            return SourceSearchOutcome(
                results=[], status="success", attempt_count=attempts_made,
                accounting=acct,
            )

        # Step 2: EFetch to get details.
        # EFetch failures here are PARTIAL (ESearch already succeeded), so
        # they are handled separately from the ESearch failure paths above and
        # carry accounting against the known PMID population.
        fetch_params: dict[str, Any] = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "xml",
        }
        if self._api_key:
            fetch_params["api_key"] = self._api_key

        try:
            if attempt_observer is not None:
                await attempt_observer.attempt_started()
            attempts_made += 1
            fetch_response = await self._client.get(EFETCH_URL, params=fetch_params)
            fetch_response.raise_for_status()
        except httpx.HTTPStatusError as e:
            code = e.response.status_code if hasattr(e, "response") else 0
            if code == 401:
                cat, fc = "authentication", "http_401"
            elif code == 403:
                cat, fc = "authorization", "http_403"
            elif code == 429:
                cat, fc = "rate_limit", "http_429"
            elif 400 <= code < 500:
                cat, fc = "provider_rejection", f"http_{code}"
            elif 500 <= code < 600:
                cat, fc = "provider_internal", f"http_{code}"
            else:
                cat, fc = "transport", "http_status_error"
            logger.warning(
                "PubMed EFetch failed after ESearch (HTTP %s): %s", code, e
            )
            # All PMIDs rejected: EFetch yielded no normalized articles.
            source_unique, accounting = reconcile_source_results(
                raw_result_count=raw_count,
                normalized_results=[],
                rejected_result_count=raw_count,
            )
            error_detail = (
                f"EFetch HTTPStatusError {code} after ESearch returned "
                f"{raw_count} PMID(s)"
            )
            # B-10: EFetch yielded 0 results — this is 'failed', not 'partial'.
            # The 'partial' status requires non-empty results (contracts.py:325).
            # Returning 'partial' with empty results triggers validate_outcome
            # to raise, which propagates through gather(return_exceptions=False)
            # and cancels other in-flight source tasks (arXiv, OpenAlex).
            return SourceSearchOutcome(
                results=source_unique,
                status="failed",
                attempt_count=attempts_made,
                error_detail=error_detail,
                failure_category=cat,
                failure_code=fc,
                accounting=accounting,
            )
        except Exception as e:
            logger.warning(
                "PubMed EFetch failed after ESearch: %s", e
            )
            # All PMIDs rejected: EFetch yielded no normalized articles.
            source_unique, accounting = reconcile_source_results(
                raw_result_count=raw_count,
                normalized_results=[],
                rejected_result_count=raw_count,
            )
            error_detail = (
                f"EFetch {type(e).__name__}: {e} after ESearch returned "
                f"{raw_count} PMID(s)"
            )
            return SourceSearchOutcome(
                results=source_unique,
                status="failed",
                attempt_count=attempts_made,
                error_detail=error_detail,
                failure_category="transport",
                failure_code="connection_error",
                accounting=accounting,
            )

        # Both ESearch and EFetch succeeded: parse and reconcile.
        results = self._parse_results(fetch_response.text)
        normalized_count = len(results)
        rejected_count = raw_count - normalized_count

        source_unique, accounting = reconcile_source_results(
            raw_result_count=raw_count,
            normalized_results=results,
            rejected_result_count=rejected_count,
        )

        if rejected_count > 0:
            # Some PMIDs did not yield a normalized article from EFetch.
            return SourceSearchOutcome(
                results=source_unique[:retmax],
                status="partial",
                attempt_count=attempts_made,
                error_detail=(
                    f"incomplete EFetch: {rejected_count} of {raw_count} "
                    f"PMID(s) did not produce a normalized article"
                ),
                failure_category="response_parse",
                failure_code="incomplete_efetch",
                accounting=accounting,
            )

        return SourceSearchOutcome(
            results=source_unique[:retmax],
            status="success",
            attempt_count=attempts_made,
            accounting=accounting,
        )

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
