"""Regression tests for SearchService.search_all outcome unwrapping.

Source adapters return ``SourceSearchOutcome`` (not a bare list). The
legacy provenance path already unwrapped it; ``search_all`` did not and
crashed with ``TypeError: 'SourceSearchOutcome' object is not iterable``,
taking down GET /literature/search, the CLI, the retrieval benchmark,
search_recursive, and the literature tool with it.
"""

import pytest

from backend.pipeline.literature.models import Paper, SearchResult
from backend.pipeline.literature.search_service import SearchService


def _sr(title: str) -> SearchResult:
    return SearchResult(paper=Paper(id=title, title=title, source="arxiv"), source="arxiv")


class _FakeSource:
    """Duck-typed AcademicSearchSource returning a canned value."""

    def __init__(self, name: str, return_value):
        self.source_name = name
        self._return_value = return_value

    async def search(self, query, limit=20, year_from=None, year_to=None):
        if isinstance(self._return_value, Exception):
            raise self._return_value
        return self._return_value

    async def get_citations(self, paper_id, limit=50):
        return []

    async def get_references(self, paper_id, limit=50):
        return []


def _outcome(status: str, results: list[SearchResult], error_detail=None):
    from backend.pipeline.literature.contracts import SourceSearchOutcome

    return SourceSearchOutcome(
        results=results,
        status=status,
        attempt_count=1 if status in ("success", "partial", "timeout") else 0,
        error_detail=error_detail,
    )


def _service(*sources) -> SearchService:
    return SearchService(sources=list(sources), embedding_provider=None)


class TestSearchAllUnwrapsOutcomes:
    @pytest.mark.asyncio
    async def test_success_outcome_unwrapped(self):
        svc = _service(_FakeSource("arxiv", _outcome("success", [_sr("Paper A"), _sr("Paper B")])))
        papers = await svc.search_all("query")
        assert [p.title for p in papers] == ["Paper A", "Paper B"]

    @pytest.mark.asyncio
    async def test_partial_outcome_results_kept(self):
        svc = _service(
            _FakeSource("arxiv", _outcome("partial", [_sr("Kept")], error_detail="rate limited"))
        )
        papers = await svc.search_all("query")
        assert [p.title for p in papers] == ["Kept"]

    @pytest.mark.asyncio
    async def test_failed_outcome_contributes_nothing_and_does_not_crash(self):
        svc = _service(_FakeSource("arxiv", _outcome("failed", [], error_detail="boom")))
        assert await svc.search_all("query") == []

    @pytest.mark.asyncio
    async def test_raising_source_skipped_not_fatal(self):
        svc = _service(
            _FakeSource("openalex", _outcome("success", [_sr("From OpenAlex")])),
            _FakeSource("arxiv", RuntimeError("network down")),
        )
        papers = await svc.search_all("query")
        assert [p.title for p in papers] == ["From OpenAlex"]

    @pytest.mark.asyncio
    async def test_bare_list_return_is_skipped_loudly_not_fatal(self):
        svc = _service(
            _FakeSource("openalex", _outcome("success", [_sr("Good")])),
            _FakeSource("legacy", [_sr("Bare list")]),  # invalid adapter return
        )
        papers = await svc.search_all("query")
        assert [p.title for p in papers] == ["Good"]

    @pytest.mark.asyncio
    async def test_mixed_sources_deduplicated(self):
        dup = "Shared Title"
        svc = _service(
            _FakeSource("openalex", _outcome("success", [_sr(dup), _sr("Unique")])),
            _FakeSource("arxiv", _outcome("success", [_sr(dup)])),
        )
        papers = await svc.search_all("query")
        titles = sorted(p.title for p in papers)
        assert titles == ["Shared Title", "Unique"]
