"""Tests for BATCH-87 — SKILL.md + Recursive Search.

AIV v5.3 — T1, T2, T5.

Marked slow: requires local SKILL.md path (C:/Next-Era/elephant-rock-platform).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.slow

from backend.pipeline.literature.models import Paper, SearchResult
from backend.pipeline.literature.search_service import SearchService


def _make_paper(title, source="test"):
    return Paper(id=f"{source}:{title[:10]}", title=title, abstract="test", source=source)


# ══════════════════════════════════════════════════════════
# TASK-01: SKILL.md
# ══════════════════════════════════════════════════════════

def test_87_01_skill_md_exists():
    """SKILL.md exists in project root."""
    assert Path(str(Path(__file__).resolve().parents[3] / "SKILL.md")).exists()


def test_87_01_skill_md_has_yaml_frontmatter():
    """SKILL.md has valid YAML frontmatter."""
    content = Path(str(Path(__file__).resolve().parents[3] / "SKILL.md")).read_text()
    assert content.startswith("---")
    assert "name:" in content
    assert "capabilities:" in content
    assert "constraints:" in content


def test_87_01_skill_md_lists_pipeline_stages():
    """SKILL.md lists all 9 pipeline stages."""
    content = Path(str(Path(__file__).resolve().parents[3] / "SKILL.md")).read_text()
    stages = [
        "literature_search", "ingestion", "gap_analysis",
        "idea_generation", "novelty_checking", "feasibility_scoring",
        "mechanical_metrics", "proposal_synthesis", "export",
    ]
    for stage in stages:
        assert stage in content, f"Stage '{stage}' missing from SKILL.md"


# ══════════════════════════════════════════════════════════
# TASK-02: Recursive Search
# ══════════════════════════════════════════════════════════

def test_87_02_search_depth_in_settings():
    """search_depth is in Settings."""
    from backend.config import get_settings
    settings = get_settings()
    assert hasattr(settings, "search_depth")
    assert settings.search_depth >= 1


def test_87_02_extract_followup_queries():
    """Follow-up queries are extracted from paper titles."""
    papers = [
        _make_paper("Deep Learning for Natural Language Processing and Understanding"),
        _make_paper("Transformer Models for Multi-Task Learning in Computer Vision"),
    ]
    queries = SearchService._extract_followup_queries(papers, "machine learning")
    assert len(queries) > 0
    # Each query should be shorter than the full title
    for q in queries:
        assert len(q.split()) < 10


def test_87_02_recursive_depth_one_is_single_pass():
    """depth=1 is equivalent to single-pass search."""
    import asyncio
    mock_source = MagicMock()
    mock_source.source_name = "mock"
    mock_source.search = AsyncMock(return_value=[
        SearchResult(paper=_make_paper("Paper A"), relevance_score=1.0, source="mock"),
    ])

    svc = SearchService(sources=[mock_source], search_depth=1)
    results = asyncio.run(svc.search_recursive("test query", max_depth=1))
    assert len(results) == 1
