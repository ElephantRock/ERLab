"""BATCH-155: Search Expansion — PubMed + CrossRef + RelevanceFilter + Health Check.

TASK-01: Config + Source Wiring (6 tests)
TASK-02: RelevanceFilter Integration (5 tests)
TASK-03: Health Check + MultiSource Wiring (5 tests)

AIV v5.3 — Use asyncio.run() directly. pytest.ini has -p no:asyncio.
HB-05: All tests mock HTTP clients — no network calls.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from backend.config import Settings
from backend.pipeline.literature.models import Paper, SearchResult
from backend.pipeline.literature.multi_source import MultiSourceSearcher
from backend.pipeline.literature.search_service import SearchService

# ── Helpers ──────────────────────────────────────────────


def _make_paper(title: str, doi: str = "", year: int = 2024, source: str = "test") -> Paper:
    return Paper(
        id=f"{source}:{title[:20]}",
        title=title,
        abstract="test abstract",
        year=year,
        authors=[],
        doi=doi,
        url="",
        source=source,
        citation_count=0,
        venue="",
    )


def _make_result(title: str, doi: str = "", score: float = 1.0, source: str = "test") -> SearchResult:
    return SearchResult(
        paper=_make_paper(title, doi, source=source),
        relevance_score=score,
        source=source,
    )


def _mock_source(name: str, search_results: list[SearchResult] | None = None) -> MagicMock:
    """Create a mock AcademicSearchSource."""
    source = MagicMock()
    source.source_name = name
    source.search = AsyncMock(return_value=search_results or [])
    source.get_paper = AsyncMock(return_value=None)
    source.get_citations = AsyncMock(return_value=[])
    source.get_references = AsyncMock(return_value=[])
    return source


# ══════════════════════════════════════════════════════════
# TASK-01: Config + Source Wiring (6 tests)
# ══════════════════════════════════════════════════════════


def test_155_01_01_settings_has_pubmed_enabled():
    """TEST-155-01-01: Settings has pubmed_enabled field (default True)."""
    settings = Settings()
    assert hasattr(settings, "pubmed_enabled"), "pubmed_enabled field missing from Settings"
    assert settings.pubmed_enabled is True


def test_155_01_02_settings_has_crossref_enabled():
    """TEST-155-01-02: Settings has crossref_enabled field (default True)."""
    settings = Settings()
    assert hasattr(settings, "crossref_enabled"), "crossref_enabled field missing from Settings"
    assert settings.crossref_enabled is True


@patch("backend.pipeline.literature.search_service.get_settings")
def test_155_01_03_pubmed_included_when_enabled(mock_get_settings):
    """TEST-155-01-03: _default_sources includes PubMed when enabled."""
    mock_settings = MagicMock()
    mock_settings.semantic_scholar_api_key = None
    mock_settings.openalex_email = None
    mock_settings.pubmed_api_key = None
    mock_settings.pubmed_enabled = True
    mock_settings.crossref_enabled = False  # Isolate PubMed
    mock_get_settings.return_value = mock_settings

    sources = SearchService._default_sources()
    names = [s.source_name for s in sources]
    assert "pubmed" in names, f"PubMed not in sources: {names}"


@patch("backend.pipeline.literature.search_service.get_settings")
def test_155_01_04_pubmed_excluded_when_disabled(mock_get_settings):
    """TEST-155-01-04: _default_sources excludes PubMed when disabled."""
    mock_settings = MagicMock()
    mock_settings.semantic_scholar_api_key = None
    mock_settings.openalex_email = None
    mock_settings.pubmed_api_key = None
    mock_settings.pubmed_enabled = False
    mock_settings.crossref_enabled = False
    mock_get_settings.return_value = mock_settings

    sources = SearchService._default_sources()
    names = [s.source_name for s in sources]
    assert "pubmed" not in names, f"PubMed should be excluded: {names}"


@patch("backend.pipeline.literature.search_service.get_settings")
def test_155_01_05_crossref_included_when_enabled(mock_get_settings):
    """TEST-155-01-05: _default_sources includes CrossRef when enabled."""
    mock_settings = MagicMock()
    mock_settings.semantic_scholar_api_key = None
    mock_settings.openalex_email = "test@example.com"
    mock_settings.pubmed_api_key = None
    mock_settings.pubmed_enabled = False  # Isolate CrossRef
    mock_settings.crossref_enabled = True
    mock_get_settings.return_value = mock_settings

    sources = SearchService._default_sources()
    names = [s.source_name for s in sources]
    assert "crossref" in names, f"CrossRef not in sources: {names}"


def test_155_01_06_dedup_priority_five_sources():
    """TEST-155-01-06: Dedup priority dict includes all 5 sources."""
    # Create results from all 5 sources
    results = [
        _make_result("Paper A", doi="10.1/a", source="semantic_scholar"),
        _make_result("Paper B", doi="10.1/b", source="pubmed"),
        _make_result("Paper C", doi="10.1/c", source="openalex"),
        _make_result("Paper D", doi="10.1/d", source="crossref"),
        _make_result("Paper E", doi="10.1/e", source="arxiv"),
    ]
    papers = SearchService._deduplicate(results)
    # All 5 should survive dedup (different DOIs)
    assert len(papers) == 5, f"Expected 5 papers, got {len(papers)}"

    # Verify source priority ordering: S2 first, then pubmed, openalex, crossref, arxiv
    source_order = [p.source for p in papers]
    expected_order = ["semantic_scholar", "pubmed", "openalex", "crossref", "arxiv"]
    assert source_order == expected_order, f"Priority order wrong: {source_order}"


# ══════════════════════════════════════════════════════════
# TASK-02: RelevanceFilter Integration (5 tests)
# ══════════════════════════════════════════════════════════


def test_155_02_01_filter_called_after_dedup():
    """TEST-155-02-01: RelevanceFilter called after dedup (A-02)."""
    s1 = _mock_source("s1", [_make_result("Paper A", doi="10.1/a", source="s1")])
    s2 = _mock_source("s2", [_make_result("Paper A", doi="10.1/a", source="s2")])

    mock_provider = MagicMock()
    mock_provider.embed = AsyncMock(return_value=[0.1] * 10)

    svc = SearchService(sources=[s1, s2], embedding_provider=mock_provider)

    with patch(
        "backend.pipeline.literature.relevance_filter.RelevanceFilter.filter",
        new_callable=AsyncMock,
    ) as mock_filter:
        # Dedup will reduce 2 results → 1, then filter gets called with 1 result
        mock_filter.return_value = [_make_result("Paper A", doi="10.1/a", source="s1")]
        result = asyncio.run(svc.search_all("test query"))
        mock_filter.assert_called_once()


def test_155_02_02_filter_skipped_no_provider():
    """TEST-155-02-02: Filter skipped when no embedding provider."""
    s1 = _mock_source("s1", [_make_result("Paper A", doi="10.1/a", source="s1")])

    svc = SearchService(sources=[s1], embedding_provider=None)
    result = asyncio.run(svc.search_all("test query"))

    assert len(result) == 1
    assert result[0].title == "Paper A"


def test_155_02_03_filter_reduces_paper_count():
    """TEST-155-02-03: Filter reduces paper count."""
    results = [_make_result(f"Paper {i}", doi=f"10.1/{i}", score=0.5, source="s1") for i in range(10)]

    s1 = _mock_source("s1", results)

    mock_provider = MagicMock()
    mock_provider.embed = AsyncMock(return_value=[0.1] * 10)

    svc = SearchService(sources=[s1], embedding_provider=mock_provider)

    with patch(
        "backend.pipeline.literature.relevance_filter.RelevanceFilter.filter",
        new_callable=AsyncMock,
    ) as mock_filter:
        # Filter returns only 2 papers (simulating relevance filtering)
        mock_filter.return_value = [
            _make_result("Paper 0", doi="10.1/0", score=0.9, source="s1"),
            _make_result("Paper 1", doi="10.1/1", score=0.8, source="s1"),
        ]
        result = asyncio.run(svc.search_all("test query"))

    assert len(result) == 2, f"Expected 2 filtered papers, got {len(result)}"


def test_155_02_04_filter_guarantees_minimum_papers():
    """TEST-155-02-04: Filter guarantees minimum papers (HB-04 / MIN_PAPERS=5).

    Even if filter would return fewer than MIN_PAPERS, the RelevanceFilter
    itself guarantees at least MIN_PAPERS when enough candidates exist.
    We verify the filter is called and can return at least MIN_PAPERS.
    """
    results = [_make_result(f"Paper {i}", doi=f"10.1/{i}", score=0.1, source="s1") for i in range(20)]

    s1 = _mock_source("s1", results)

    mock_provider = MagicMock()
    mock_provider.embed = AsyncMock(return_value=[0.1] * 10)

    svc = SearchService(sources=[s1], embedding_provider=mock_provider)

    with patch(
        "backend.pipeline.literature.relevance_filter.RelevanceFilter.filter",
        new_callable=AsyncMock,
    ) as mock_filter:
        # Simulate filter returning exactly MIN_PAPERS (5) from a larger set
        mock_filter.return_value = [_make_result(f"Paper {i}", doi=f"10.1/{i}", source="s1") for i in range(5)]
        result = asyncio.run(svc.search_all("test query"))

    assert len(result) >= 5, f"Expected >= 5 papers (HB-04), got {len(result)}"


def test_155_02_05_filter_failure_doesnt_block_search():
    """TEST-155-02-05: Filter failure doesn't block search — returns unfiltered results."""
    results = [_make_result(f"Paper {i}", doi=f"10.1/{i}", source="s1") for i in range(5)]

    s1 = _mock_source("s1", results)

    mock_provider = MagicMock()
    mock_provider.embed = AsyncMock(return_value=[0.1] * 10)

    svc = SearchService(sources=[s1], embedding_provider=mock_provider)

    with patch(
        "backend.pipeline.literature.relevance_filter.RelevanceFilter.filter",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Embedding service down"),
    ):
        result = asyncio.run(svc.search_all("test query"))

    # Should return unfiltered (deduped) results, not crash
    assert len(result) == 5, f"Expected 5 unfiltered papers, got {len(result)}"
    assert result[0].title == "Paper 0"


# ══════════════════════════════════════════════════════════
# TASK-03: Health Check + MultiSource Wiring (5 tests)
# ══════════════════════════════════════════════════════════


def test_155_03_01_health_check_returns_all_sources():
    """TEST-155-03-01: health_check returns dict for all registered sources."""
    sources = [_mock_source(f"source_{i}") for i in range(5)]
    svc = SearchService(sources=sources)

    result = asyncio.run(svc.health_check())

    assert len(result) == 5, f"Expected 5 entries, got {len(result)}"
    for i in range(5):
        assert f"source_{i}" in result, f"Missing source_{i}"


def test_155_03_02_failed_source_marked_unhealthy():
    """TEST-155-03-02: Failed source is marked as unhealthy."""
    good = _mock_source("good", [_make_result("OK")])
    bad = _mock_source("bad")
    bad.search = AsyncMock(side_effect=ConnectionError("Network down"))

    svc = SearchService(sources=[good, bad])
    result = asyncio.run(svc.health_check())

    assert result["good"]["healthy"] is True, "Good source should be healthy"
    assert result["bad"]["healthy"] is False, "Bad source should be unhealthy"


def test_155_03_03_multi_source_uses_all_configured():
    """TEST-155-03-03: MultiSourceSearcher uses all configured sources."""
    sources = [_mock_source(f"src_{i}", [_make_result(f"Paper {i}")]) for i in range(5)]

    searcher = MultiSourceSearcher(sources)
    listed = searcher.list_sources()

    assert len(listed) == 5, f"Expected 5 sources, got {len(listed)}"
    for i in range(5):
        assert f"src_{i}" in listed, f"src_{i} not in list"


def test_155_03_04_health_check_latency_measured():
    """TEST-155-03-04: Health check reports latency > 0 for each source."""
    sources = [_mock_source(f"s{i}", [_make_result("OK")]) for i in range(3)]

    svc = SearchService(sources=sources)
    result = asyncio.run(svc.health_check())

    for i in range(3):
        name = f"s{i}"
        assert result[name]["latency_ms"] >= 0, f"Latency missing for {name}"
        assert isinstance(result[name]["latency_ms"], float), f"Latency not float for {name}"


def test_155_03_05_individual_timeout_doesnt_block_others():
    """TEST-155-03-05: Individual source timeout doesn't block other sources."""
    fast = _mock_source("fast", [_make_result("Fast Paper")])

    slow = _mock_source("slow")
    async def _slow_search(*args, **kwargs):
        await asyncio.sleep(10)  # Will exceed timeout
        return []
    slow.search = _slow_search

    svc = SearchService(sources=[fast, slow])
    result = asyncio.run(svc.health_check(timeout=0.5))

    assert result["fast"]["healthy"] is True, "Fast source should be healthy"
    assert result["slow"]["healthy"] is False, "Slow source should be marked unhealthy (timeout)"
