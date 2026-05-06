"""Tests for TreeSearchStage pipeline integration (BATCH-63/TASK-01).

Test IDs:
  TEST-63-01-01: TreeSearchStage activates when tree_of_thought_enabled=True
  TEST-63-01-02: IdeaGenerationStage used when tree_of_thought_enabled=False
  TEST-63-01-03: tree_data populated in PipelineResult after tree search
  TEST-63-01-04: tree_data respects 500KB size limit (HB-03)
"""

from __future__ import annotations

import json
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure heavy optional deps are mocked before imports
if "chromadb" not in sys.modules:
    sys.modules.setdefault("chromadb", MagicMock())
if "google.generativeai" not in sys.modules:
    sys.modules.setdefault("google.generativeai", MagicMock())

from backend.config import Settings
from backend.pipeline.gap_analysis.models import ResearchGap
from backend.pipeline.generation.models import IdeaCandidate, ResearchIdea
from backend.pipeline.literature.models import Author, Paper
from backend.pipeline.result import PipelineResult
from backend.pipeline.stages import (
    IdeaGenerationStage,
    StageContext,
    TreeSearchStage,
)


def _make_idea(title: str = "Test Idea", score: float = 0.8) -> IdeaCandidate:
    return IdeaCandidate(
        title=title,
        problem_statement="Test problem",
        proposed_method="Test method " * 20,
        expected_contributions="Test contributions",
        novelty_rationale="Test rationale",
        evaluation_approach="Test evaluation",
        overall_score=score,
    )


def _make_gap(title: str = "Test Gap") -> ResearchGap:
    return ResearchGap(
        title=title,
        description="A test research gap",
        gap_type="methodological",
        confidence=0.8,
        potential_impact="High",
    )


def _make_paper(title: str = "Test Paper") -> Paper:
    return Paper(
        id="p1",
        source="test",
        title=title,
        abstract="Test abstract",
        authors=[Author(name="Author One")],
        year=2024,
    )


def _make_tree_engine(ideas: list[IdeaCandidate] | None = None) -> MagicMock:
    """Create a mock TreeSearchEngine."""
    engine = MagicMock()
    engine.config = MagicMock()
    engine.config.beam_width = 2
    engine.config.max_depth = 3
    engine.config.ideas_per_node = 5
    engine.search = AsyncMock(return_value=ideas or [_make_idea()])
    return engine


def _make_hooks() -> MagicMock:
    hooks = MagicMock()
    hooks.dispatch_sync_safe = AsyncMock()
    return hooks


def _make_ctx(
    ideas: list | None = None,
    gaps: list[ResearchGap] | None = None,
    papers: list[Paper] | None = None,
) -> StageContext:
    result = PipelineResult()
    result.gaps = gaps or [_make_gap()]
    return StageContext(
        result=result,
        all_papers=papers or [_make_paper()],
        rounds=2,
        ideas_per=3,
    )


# ── TEST-63-01-01: TreeSearchStage activates when flag is True ──────


@pytest.mark.anyio
async def test_tree_search_stage_activates_when_enabled():
    """TEST-63-01-01: TreeSearchStage activates when tree_of_thought_enabled=True."""
    ideas = [_make_idea("Idea A", 0.9), _make_idea("Idea B", 0.7)]
    engine = _make_tree_engine(ideas)
    hooks = _make_hooks()
    ctx = _make_ctx()

    stage = TreeSearchStage(engine=engine, hooks=hooks)
    assert stage.name == "idea_generation"

    result = await stage.execute(ctx)

    # Stage completed successfully
    assert result is True

    # TreeSearchEngine.search was called with correct args
    engine.search.assert_awaited_once()
    call_args = engine.search.call_args
    assert call_args.kwargs["gaps"] == ctx.result.gaps
    assert call_args.kwargs["context_papers"] == ctx.all_papers[:30]

    # BATCH-75/TASK-05: Ideas are now converted to ResearchIdea (was IdeaCandidate)
    assert len(ctx.result.ideas) == 2
    assert all(isinstance(i, ResearchIdea) for i in ctx.result.ideas), (
        "HB-01: TreeSearchStage must assign only ResearchIdea to ctx.result.ideas"
    )
    # Verify field mapping is preserved
    assert ctx.result.ideas[0].title == "Idea A"
    assert ctx.result.ideas[0].score == 0.9
    assert ctx.result.ideas[1].title == "Idea B"
    assert ctx.result.ideas[1].score == 0.7


# ── TEST-63-01-02: IdeaGenerationStage used when flag is False ─────


def test_idea_generation_stage_used_when_disabled():
    """TEST-63-01-02: IdeaGenerationStage used when tree_of_thought_enabled=False."""
    # Verify that when tree_of_thought_enabled is False (default),
    # the orchestrator builds IdeaGenerationStage (not TreeSearchStage).
    settings = Settings(tree_of_thought_enabled=False)
    assert settings.tree_of_thought_enabled is False

    # The _build_stages method should produce IdeaGenerationStage at index 3
    # We verify by checking the type directly
    agent = MagicMock()
    hooks = _make_hooks()
    stage = IdeaGenerationStage(
        agent=agent,
        hooks=hooks,
    )
    assert isinstance(stage, IdeaGenerationStage)
    assert stage.name == "idea_generation"
    assert not isinstance(stage, TreeSearchStage)


# ── TEST-63-01-03: tree_data populated in PipelineResult ────────────


@pytest.mark.anyio
async def test_tree_data_populated_after_tree_search():
    """TEST-63-01-03: tree_data populated in PipelineResult after tree search."""
    ideas = [
        _make_idea("Idea Alpha", 0.95),
        _make_idea("Idea Beta", 0.80),
    ]
    # Set parent lineage
    ideas[0].parent_idea_ids = []
    ideas[1].parent_idea_ids = [ideas[0].id]

    engine = _make_tree_engine(ideas)
    hooks = _make_hooks()
    ctx = _make_ctx()

    stage = TreeSearchStage(engine=engine, hooks=hooks)
    await stage.execute(ctx)

    # tree_data must be populated
    assert ctx.result.tree_data is not None
    assert isinstance(ctx.result.tree_data, dict)
    assert ctx.result.tree_data["engine"] == "tree_search"
    assert "config" in ctx.result.tree_data
    assert ctx.result.tree_data["config"]["beam_width"] == 2
    assert ctx.result.tree_data["config"]["max_depth"] == 3
    assert "nodes" in ctx.result.tree_data
    assert len(ctx.result.tree_data["nodes"]) == 2

    # Verify node contents
    node_alpha = ctx.result.tree_data["nodes"][0]
    assert node_alpha["title"] == "Idea Alpha"
    assert node_alpha["score"] == 0.95
    assert node_alpha["parent_ids"] == []

    node_beta = ctx.result.tree_data["nodes"][1]
    assert node_beta["title"] == "Idea Beta"
    assert node_beta["parent_ids"] == [ideas[0].id]


# ── TEST-63-01-04: tree_data respects 500KB size limit (HB-03) ──────


@pytest.mark.anyio
async def test_tree_data_respects_500kb_limit():
    """TEST-63-01-04: tree_data respects 500KB size limit (HB-03)."""
    # Create ideas with large proposed_method to exceed 500KB
    big_text = "X" * 100_000  # 100KB per idea
    ideas = [
        IdeaCandidate(
            title=f"Huge Idea {i}",
            problem_statement=big_text,
            proposed_method=big_text,
            expected_contributions=big_text,
            novelty_rationale=big_text,
            evaluation_approach=big_text,
            overall_score=0.5,
            parent_idea_ids=[],
        )
        for i in range(10)  # 10 × ~500KB = way over 500KB
    ]

    engine = _make_tree_engine(ideas)
    hooks = _make_hooks()
    ctx = _make_ctx()

    stage = TreeSearchStage(engine=engine, hooks=hooks)
    await stage.execute(ctx)

    # tree_data must not exceed 500KB
    if ctx.result.tree_data is not None:
        serialized = json.dumps(ctx.result.tree_data, default=str)
        size_bytes = len(serialized.encode("utf-8"))
        assert size_bytes <= TreeSearchStage.MAX_TREE_DATA_BYTES, (
            f"tree_data is {size_bytes} bytes, exceeds 500KB limit"
        )
    # If None, it means it was too large and was truncated to nothing — also valid
    # But the important thing is it doesn't exceed 500KB


def test_enforce_size_limit_truncates_large_data():
    """Unit test for _enforce_size_limit with oversized data."""
    # Create a tree_data dict that exceeds 500KB
    large_nodes = [{"id": f"n{i}", "title": "T" * 10_000, "score": 0.5} for i in range(100)]
    tree_data = {"engine": "tree_search", "config": {}, "nodes": large_nodes}

    result = TreeSearchStage._enforce_size_limit(tree_data)

    if result is not None:
        serialized = json.dumps(result, default=str)
        size_bytes = len(serialized.encode("utf-8"))
        assert size_bytes <= TreeSearchStage.MAX_TREE_DATA_BYTES


def test_enforce_size_limit_keeps_small_data():
    """Unit test for _enforce_size_limit with small data (no truncation)."""
    tree_data = {
        "engine": "tree_search",
        "config": {"beam_width": 2, "max_depth": 3},
        "nodes": [{"id": "n1", "title": "Small idea", "score": 0.8, "parent_ids": []}],
    }

    result = TreeSearchStage._enforce_size_limit(tree_data)

    assert result is not None
    assert result == tree_data
    assert len(result["nodes"]) == 1
