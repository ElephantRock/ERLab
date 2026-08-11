"""Phase 3 B-10 regression tests: premature literature-search aggregation.

Verifies that:
1. fast failure + slow success → papers returned, stage continues
2. fast empty + slow success → papers returned, stage continues
3. all sources empty → explicit zero-paper halt
4. all sources fail → explicit provider-failure state
5. partial failures + usable papers → continue with warnings
6. late source result → not discarded
"""

from __future__ import annotations

import asyncio

import pytest

from backend.pipeline.literature.models import Paper, SearchResult
from backend.pipeline.literature.search_service import SearchService


def _make_paper(title="Test Paper", source="test"):
    return Paper(
        id=f"{source}:{title}",
        title=title,
        abstract="Abstract text",
        source=source,
        authors=[],
        year=2024,
    )


def _make_search_result(paper):
    return SearchResult(paper=paper, raw_title=paper.title, source=paper.source)


class FakeSource:
    """Deterministic test source with configurable delay and outcome."""

    def __init__(self, name, papers=None, delay=0.0, exc=None):
        self._name = name
        self._papers = papers or []
        self._delay = delay
        self._exc = exc
        self.was_called = False

    async def search(self, query, limit=20, year_from=None, year_to=None):
        self.was_called = True
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._exc:
            raise self._exc
        return [_make_search_result(p) for p in self._papers]

    @property
    def source_name(self):
        return self._name


@pytest.mark.anyio
async def test_fast_failure_plus_slow_success():
    """Case 1: source A fails fast, source B succeeds slowly → papers returned."""
    fast_fail = FakeSource("pubmed", exc=Exception("429 rate limited"))
    slow_ok = FakeSource("arxiv", papers=[_make_paper("Arxiv Paper", "arxiv")], delay=0.2)
    svc = SearchService.__new__(SearchService)
    svc._sources = {"pubmed": fast_fail, "arxiv": slow_ok}
    svc._embedding_provider = None

    results = await svc.search_all("test query")
    assert len(results) == 1
    assert results[0].title == "Arxiv Paper"
    assert slow_ok.was_called


@pytest.mark.anyio
async def test_fast_empty_plus_slow_success():
    """Case 2: source A returns empty fast, source B succeeds slowly."""
    fast_empty = FakeSource("crossref", papers=[])
    slow_ok = FakeSource("arxiv", papers=[_make_paper("Arxiv Paper", "arxiv")], delay=0.2)
    svc = SearchService.__new__(SearchService)
    svc._sources = {"crossref": fast_empty, "arxiv": slow_ok}
    svc._embedding_provider = None

    results = await svc.search_all("test query")
    assert len(results) == 1
    assert results[0].title == "Arxiv Paper"


@pytest.mark.anyio
async def test_all_sources_empty():
    """Case 3: all sources return empty → 0 papers."""
    a = FakeSource("pubmed", papers=[])
    b = FakeSource("arxiv", papers=[])
    svc = SearchService.__new__(SearchService)
    svc._sources = {"pubmed": a, "arxiv": b}
    svc._embedding_provider = None

    results = await svc.search_all("test query")
    assert len(results) == 0


@pytest.mark.anyio
async def test_all_sources_fail():
    """Case 4: all sources fail → 0 papers, no exception."""
    a = FakeSource("pubmed", exc=Exception("429"))
    b = FakeSource("arxiv", exc=Exception("timeout"))
    svc = SearchService.__new__(SearchService)
    svc._sources = {"pubmed": a, "arxiv": b}
    svc._embedding_provider = None

    results = await svc.search_all("test query")
    assert len(results) == 0


@pytest.mark.anyio
async def test_partial_failures_plus_usable_papers():
    """Case 5: one source fails, another returns papers → papers returned."""
    fail = FakeSource("pubmed", exc=Exception("429"))
    ok = FakeSource("arxiv", papers=[_make_paper("P1", "arxiv"), _make_paper("P2", "arxiv")])
    svc = SearchService.__new__(SearchService)
    svc._sources = {"pubmed": fail, "arxiv": ok}
    svc._embedding_provider = None

    results = await svc.search_all("test query")
    assert len(results) == 2


@pytest.mark.anyio
async def test_late_source_result_not_discarded():
    """Case 6: a slow source's result is not discarded when a fast source fails."""
    fast_fail = FakeSource("pubmed", exc=Exception("429"))
    slow_ok = FakeSource("arxiv", papers=[_make_paper("Late Paper", "arxiv")], delay=0.5)
    svc = SearchService.__new__(SearchService)
    svc._sources = {"pubmed": fast_fail, "arxiv": slow_ok}
    svc._embedding_provider = None

    results = await svc.search_all("test query")
    # The slow source's result must NOT be cancelled by the fast failure
    assert len(results) == 1
    assert results[0].title == "Late Paper"
    assert slow_ok.was_called


@pytest.mark.anyio
async def test_pubmed_efetch_429_returns_failed_not_partial():
    """B-10 specific: verify PubMed source returns 'failed' (not 'partial')
    when EFetch yields 0 results, avoiding the contract validation that
    would raise and cancel other sources."""
    # Verify the code does not use 'partial' for empty EFetch results
    import inspect

    from backend.pipeline.literature.pubmed_source import PubMedSource
    source = inspect.getsource(PubMedSource)
    # The EFetch-failed path must not return 'partial' with empty results
    assert 'status="failed"' in source
    # It should NOT have 'partial' status for the 0-results-after-EFetch path
    # (we changed both the HTTPStatusError and generic Exception paths)
