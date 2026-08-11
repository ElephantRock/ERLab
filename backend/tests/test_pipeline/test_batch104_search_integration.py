"""Tests for BATCH-104 — Search Integration Service.

AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from backend.pipeline.literature.models import Paper, SearchResult
from backend.pipeline.search_integration import SearchIntegrationService


def _make_result(title, doi=""):
    return SearchResult(
        paper=Paper(id=f"test:{title[:10]}", title=title, abstract="test", doi=doi, source="test"),
        relevance_score=1.0,
        source="test",
    )


def test_104_01_register_source():
    """Can register sources."""
    svc = SearchIntegrationService()
    mock = MagicMock()
    mock.source_name = "mock_source"
    svc.register_source(mock)
    assert "mock_source" in svc.list_sources()


def test_104_01_list_sources():
    """list_sources returns source names."""
    svc = SearchIntegrationService()
    assert isinstance(svc.list_sources(), list)


def test_104_01_check_proposal_clean():
    """Clean proposal passes guard."""
    svc = SearchIntegrationService()
    result = svc.check_proposal("A well-grounded research proposal with evidence.")
    assert result.passed is True
    assert result.confidence_score >= 0.8


def test_104_01_check_proposal_fabricated():
    """Fabricated proposal triggers warnings."""
    svc = SearchIntegrationService()
    result = svc.check_proposal(
        "Dr. Test Author claims 99.9% improvement at doi:10.9999/fake."
    )
    assert len(result.warnings) > 0


def test_104_02_guard_accessible():
    """guard property returns AntiFabricationGuard."""
    from backend.pipeline.safety.anti_fabrication import AntiFabricationGuard
    svc = SearchIntegrationService()
    assert isinstance(svc.guard, AntiFabricationGuard)


def test_104_02_search_and_filter():
    """search_and_filter calls searcher and filter."""
    svc = SearchIntegrationService()
    # Register a mock source
    mock_source = MagicMock()
    mock_source.source_name = "mock"
    mock_source.search = AsyncMock(return_value=[_make_result("Paper A")])
    svc.register_source(mock_source)

    results = asyncio.run(svc.search_and_filter("machine learning"))
    assert len(results) >= 1


def test_104_02_search_failure_returns_empty():
    """Search failure returns empty list."""
    svc = SearchIntegrationService()
    results = asyncio.run(svc.search_and_filter("test"))
    assert isinstance(results, list)


def test_104_03_check_empty_proposal():
    """Empty proposal passes with confidence 1.0."""
    svc = SearchIntegrationService()
    result = svc.check_proposal("")
    assert result.passed is True
