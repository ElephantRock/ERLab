"""Tests for BATCH-102 — Knowledge Integration Service.

AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

import os
import tempfile

import pytest

from backend.pipeline.literature.models import Paper


def _make_paper(title, abstract="Abstract", doi="10.1/a"):
    return Paper(id=f"test:{title[:10]}", title=title, abstract=abstract, doi=doi, source="test")

from backend.pipeline.knowledge.integration import KnowledgeIntegrationService


@pytest.fixture
def svc():
    tmpdir_obj = tempfile.TemporaryDirectory()
    tmpdir = tmpdir_obj.name
    service = KnowledgeIntegrationService(
        library_dir=tmpdir,
        error_db_path=os.path.join(tmpdir, "errors.db"),
    )
    yield service
    service.close()
    service._library.close()
    tmpdir_obj.cleanup()


def test_102_01_index_papers(svc):
    """index_run_results counts papers."""
    papers = [_make_paper("Paper A")]
    counts = svc.index_run_results("AI", papers=papers, run_id="run-1")
    assert counts["papers"] == 1


def test_102_01_index_gaps(svc):
    """index_run_results counts gaps."""
    from types import SimpleNamespace
    gaps = [SimpleNamespace(title="Gap A", description="Desc", name="Gap A")]
    counts = svc.index_run_results("AI", gaps=gaps)
    assert counts["gaps"] == 1


def test_102_01_index_ideas(svc):
    """index_run_results counts ideas."""
    from types import SimpleNamespace
    ideas = [SimpleNamespace(title="Idea A", description="Desc", score=0.9)]
    counts = svc.index_run_results("AI", ideas=ideas)
    assert counts["ideas"] == 1


def test_102_02_query_existing_knowledge(svc):
    """query_existing_knowledge returns counts."""
    result = svc.query_existing_knowledge("AI")
    assert "existing_papers" in result
    assert "existing_gaps" in result
    assert "has_knowledge" in result


def test_102_02_query_after_indexing(svc):
    """After indexing, query shows knowledge exists."""
    papers = [_make_paper("Test Paper")]
    svc.index_run_results("Bio", papers=papers)
    result = svc.query_existing_knowledge("Bio")
    assert result["existing_papers"] >= 1
    assert result["has_knowledge"] is True


def test_102_03_record_failure(svc):
    """record_failure stores error."""
    svc.record_failure("synthesis", "Proposal too short", "Generate more detail", "test input")
    failures = svc.get_past_failures(stage="synthesis")
    assert len(failures) == 1


def test_102_03_get_all_failures(svc):
    """get_past_failures without stage returns all."""
    svc.record_failure("gap_analysis", "Gaps too generic")
    svc.record_failure("synthesis", "Proposal too short")
    failures = svc.get_past_failures()
    assert len(failures) >= 2


def test_102_03_index_fails_safe(svc):
    """Indexing with None inputs doesn't crash."""
    counts = svc.index_run_results("AI", papers=None, gaps=None, ideas=None)
    assert counts["papers"] == 0
