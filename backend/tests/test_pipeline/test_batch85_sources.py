"""Tests for BATCH-85 — More Search Engines.

TASK-01: Three new sources (9 tests)
TASK-02: MultiSourceSearcher (5 tests)

AIV v5.3 — T1, T2, T5. Use asyncio.run() not @pytest.mark.asyncio.
"""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.pipeline.literature.pubmed_source import PubMedSource
from backend.pipeline.literature.crossref_source import CrossRefSource
from backend.pipeline.literature.multi_source import MultiSourceSearcher
from backend.pipeline.literature.models import Paper, SearchResult, Author


def _make_paper(title, doi="", year=2024, source="test"):
    return Paper(id=f"{source}:{title[:20]}", title=title, abstract="test", year=year, authors=[], doi=doi, url="", source=source, citation_count=0, venue="")

def _make_result(title, doi="", score=1.0, source="test"):
    return SearchResult(paper=_make_paper(title, doi, source=source), relevance_score=score, source=source)


# ══════════════════════════════════════════════════════════
# TASK-01: Source tests
# ══════════════════════════════════════════════════════════

def test_85_01_01_pubmed_source_name():
    """PubMedSource has correct source_name."""
    source = PubMedSource()
    assert source.source_name == "pubmed"


def test_85_01_02_pubmed_search_handles_failure():
    """PubMed search returns empty list on network failure."""
    source = PubMedSource()
    with patch.object(source._client, "get", side_effect=Exception("network error")):
        results = asyncio.run(source.search("test query"))
        assert results == []


def test_85_01_03_pubmed_get_paper_handles_failure():
    """PubMed get_paper returns None on failure."""
    source = PubMedSource()
    with patch.object(source._client, "get", side_effect=Exception("error")):
        result = asyncio.run(source.get_paper("12345"))
        assert result is None


def test_85_01_04_crossref_source_name():
    """CrossRefSource has correct source_name."""
    source = CrossRefSource()
    assert source.source_name == "crossref"


def test_85_01_05_crossref_search_handles_failure():
    """CrossRef search returns empty list on failure."""
    source = CrossRefSource()
    with patch.object(source._client, "get", side_effect=Exception("error")):
        results = asyncio.run(source.search("test query"))
        assert results == []


def test_85_01_06_crossref_get_paper_handles_failure():
    """CrossRef get_paper returns None on failure."""
    source = CrossRefSource()
    with patch.object(source._client, "get", side_effect=Exception("error")):
        result = asyncio.run(source.get_paper("10.1234/test"))
        assert result is None


def test_85_01_07_semantic_scholar_source_exists():
    """SemanticScholarSource exists and is importable."""
    from backend.pipeline.literature.semantic_scholar import SemanticScholarSource
    source = SemanticScholarSource()
    assert source.source_name == "semantic_scholar"


def test_85_01_08_pubmed_no_key_required():
    """PubMedSource works without API key."""
    source = PubMedSource(api_key=None)
    assert source._api_key is None


def test_85_01_09_crossref_mailto_optional():
    """CrossRefSource works without mailto."""
    source = CrossRefSource(mailto="")
    assert source._mailto == ""


# ══════════════════════════════════════════════════════════
# TASK-02: MultiSourceSearcher
# ══════════════════════════════════════════════════════════

def test_85_02_01_register_and_list_sources():
    """Sources can be registered and listed."""
    searcher = MultiSourceSearcher()
    mock = MagicMock()
    mock.source_name = "mock_source"
    searcher.register(mock)
    assert "mock_source" in searcher.list_sources()


def test_85_02_02_deduplicate_by_doi():
    """Dedup removes papers with same DOI."""
    r1 = _make_result("Paper A", doi="10.1234/a", score=0.9)
    r2 = _make_result("Paper A (duplicate)", doi="10.1234/a", score=0.7)
    merged = MultiSourceSearcher._deduplicate([r1, r2])
    assert len(merged) == 1
    assert merged[0].paper.title == "Paper A"  # Higher score kept


def test_85_02_03_deduplicate_by_title():
    """Dedup removes papers with same title (case-insensitive)."""
    r1 = _make_result("Sparse Attention Mechanisms", score=0.8)
    r2 = _make_result("sparse attention mechanisms", score=0.6)
    merged = MultiSourceSearcher._deduplicate([r1, r2])
    assert len(merged) == 1


def test_85_02_04_empty_sources_returns_empty():
    """No sources registered returns empty results."""
    searcher = MultiSourceSearcher()
    results = asyncio.run(searcher.search("test"))
    assert results == []


def test_85_02_05_source_failure_independent():
    """One source failing doesn't affect others (HB-01)."""
    good_source = MagicMock()
    good_source.source_name = "good"
    good_source.search = AsyncMock(return_value=[_make_result("Good Paper")])

    bad_source = MagicMock()
    bad_source.source_name = "bad"
    bad_source.search = AsyncMock(side_effect=Exception("Source crashed"))

    searcher = MultiSourceSearcher([good_source, bad_source])
    results = asyncio.run(searcher.search("test"))
    assert len(results) == 1
    assert results[0].paper.title == "Good Paper"
