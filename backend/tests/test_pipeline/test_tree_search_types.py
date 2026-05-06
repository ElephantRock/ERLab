"""Tests for IdeaCandidate → ResearchIdea conversion in TreeSearchStage (BATCH-75/TASK-01).

Test IDs:
  TEST-75-01-01: _convert_to_research_ideas maps all 9 IdeaCandidate fields to ResearchIdea
  TEST-75-01-02: _convert_to_research_ideas handles empty optional fields
  TEST-75-01-03: _convert_to_research_ideas preserves overall_score → score
  TEST-75-01-04: TreeSearchStage.execute() raises AssertionError if ideas are not ResearchIdea
  TEST-75-01-05: _convert_to_research_ideas maps parent_idea_ids → source_gap_ids
  TEST-75-01-06: _build_tree_data works with ResearchIdea (no .id field)
  TEST-75-01-07: _build_tree_data uses source_gap_ids as parent refs for ResearchIdea
"""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure heavy optional deps are mocked before imports
if "chromadb" not in sys.modules:
    sys.modules.setdefault("chromadb", MagicMock())
if "google.generativeai" not in sys.modules:
    sys.modules.setdefault("google.generativeai", MagicMock())

from backend.pipeline.generation.models import IdeaCandidate, ResearchIdea
from backend.pipeline.gap_analysis.models import ResearchGap
from backend.pipeline.literature.models import Author, Paper
from backend.pipeline.result import PipelineResult
from backend.pipeline.stages import StageContext, TreeSearchStage


# ── Helpers ──────────────────────────────────────────────────────────


def _make_idea(
    title: str = "Test Idea",
    score: float = 0.8,
    parent_idea_ids: list[str] | None = None,
    expected_contributions: str = "Contributions",
    novelty_rationale: str = "Rationale",
    evaluation_approach: str = "Approach",
) -> IdeaCandidate:
    return IdeaCandidate(
        title=title,
        problem_statement="Test problem",
        proposed_method="Test method " * 20,
        expected_contributions=expected_contributions,
        novelty_rationale=novelty_rationale,
        evaluation_approach=evaluation_approach,
        overall_score=score,
        parent_idea_ids=parent_idea_ids,
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


# ── TEST-75-01-01: Full field mapping ────────────────────────────────


def test_convert_to_research_ideas_maps_all_fields():
    """TEST-75-01-01: _convert_to_research_ideas maps all 9 IdeaCandidate fields to ResearchIdea."""
    candidate = _make_idea(
        title="AI/NLP Research Idea",
        score=0.85,
        parent_idea_ids=["parent1"],
        expected_contributions="Contributions text",
        novelty_rationale="Novelty text",
        evaluation_approach="Evaluation text",
    )

    result_list = TreeSearchStage._convert_to_research_ideas([candidate])

    assert len(result_list) == 1
    result = result_list[0]

    # AC-01-01: Output is ResearchIdea
    assert isinstance(result, ResearchIdea)

    # Verify all field mappings
    assert result.title == "AI/NLP Research Idea"
    assert result.problem_statement == "Test problem"
    assert result.proposed_method == candidate.proposed_method
    assert result.expected_contributions == "Contributions text"
    assert result.novelty_rationale == "Novelty text"
    assert result.evaluation_approach == "Evaluation text"
    assert result.domain == "AI/NLP"
    assert result.round_generated == 1
    assert result.supporting_papers == []


# ── TEST-75-01-02: Empty optional fields ─────────────────────────────


def test_convert_to_research_ideas_handles_empty_optionals():
    """TEST-75-01-02: _convert_to_research_ideas handles IdeaCandidate with empty optional fields."""
    candidate = IdeaCandidate(
        title="Minimal Idea",
        problem_statement="Problem",
        proposed_method="Method",
        expected_contributions="",
        novelty_rationale="",
        evaluation_approach="",
        overall_score=0.5,
        parent_idea_ids=None,
    )

    result_list = TreeSearchStage._convert_to_research_ideas([candidate])

    assert len(result_list) == 1
    result = result_list[0]

    assert isinstance(result, ResearchIdea)
    assert result.source_gap_ids == [], f"Expected empty list, got {result.source_gap_ids}"
    assert result.expected_contributions == ""
    assert result.novelty_rationale == ""
    assert result.evaluation_approach == ""


# ── TEST-75-01-03: Score preservation ────────────────────────────────


def test_convert_preserves_score():
    """TEST-75-01-03: _convert_to_research_ideas preserves overall_score → score."""
    candidate = _make_idea(title="Scored Idea", score=0.85)

    result_list = TreeSearchStage._convert_to_research_ideas([candidate])

    result = result_list[0]
    assert result.score == 0.85, f"Expected score 0.85, got {result.score}"


# ── TEST-75-01-04: isinstance assertion (HB-01) ─────────────────────


@pytest.mark.anyio
async def test_execute_raises_assertion_on_non_research_idea():
    """TEST-75-01-04: TreeSearchStage.execute() raises AssertionError if ideas are not ResearchIdea.

    This tests the HB-01 guard. We monkeypatch _convert_to_research_ideas to
    return raw IdeaCandidate objects, simulating a broken conversion.
    """
    raw_candidates = [_make_idea("Bare Candidate")]
    engine = _make_tree_engine(raw_candidates)
    hooks = _make_hooks()
    ctx = _make_ctx()

    stage = TreeSearchStage(engine=engine, hooks=hooks)

    # Monkeypatch the conversion to return raw IdeaCandidate (bypass conversion)
    stage._convert_to_research_ideas = lambda candidates: candidates  # type: ignore[assignment]

    with pytest.raises(AssertionError, match="HB-01"):
        await stage.execute(ctx)


# ── TEST-75-01-05: parent_idea_ids → source_gap_ids mapping ──────────


def test_convert_maps_parent_ids_to_source_gap_ids():
    """TEST-75-01-05: _convert_to_research_ideas maps parent_idea_ids → source_gap_ids."""
    candidate = _make_idea(
        title="Child Idea",
        parent_idea_ids=["id1", "id2"],
    )

    result_list = TreeSearchStage._convert_to_research_ideas([candidate])

    result = result_list[0]
    assert result.source_gap_ids == ["id1", "id2"], (
        f"Expected ['id1', 'id2'], got {result.source_gap_ids}"
    )


# ── TEST-75-01-06: _build_tree_data with ResearchIdea (no .id) ───────


def test_build_tree_data_works_with_research_idea():
    """TEST-75-01-06: _build_tree_data works with ResearchIdea (no .id field).

    After TASK-01 conversion, _build_tree_data receives ResearchIdea objects
    which lack the .id field present on IdeaCandidate. The getattr guard
    must prevent AttributeError.
    """
    research_ideas = [
        ResearchIdea(
            title="Research Idea Alpha",
            problem_statement="Problem",
            proposed_method="Method " * 20,
            expected_contributions="Contrib",
            novelty_rationale="Novel",
            evaluation_approach="Eval",
            domain="AI/NLP",
            round_generated=1,
            score=0.92,
            source_gap_ids=["gap-1"],
        ),
        ResearchIdea(
            title="Research Idea Beta",
            problem_statement="Problem 2",
            proposed_method="Method 2 " * 20,
            expected_contributions="Contrib 2",
            novelty_rationale="Novel 2",
            evaluation_approach="Eval 2",
            domain="AI/NLP",
            round_generated=1,
            score=0.78,
            source_gap_ids=["gap-2"],
        ),
    ]

    engine = _make_tree_engine([])
    hooks = _make_hooks()
    stage = TreeSearchStage(engine=engine, hooks=hooks)

    # Must not raise AttributeError
    tree_data = stage._build_tree_data(research_ideas)

    assert isinstance(tree_data, dict)
    assert tree_data["engine"] == "tree_search"
    assert len(tree_data["nodes"]) == 2

    # Nodes must have valid IDs (fallback to title[:60])
    node_alpha = tree_data["nodes"][0]
    assert "id" in node_alpha
    assert node_alpha["id"]  # non-empty
    assert node_alpha["title"] == "Research Idea Alpha"
    assert node_alpha["score"] == 0.92

    node_beta = tree_data["nodes"][1]
    assert "id" in node_beta
    assert node_beta["id"]  # non-empty
    assert node_beta["score"] == 0.78


# ── TEST-75-01-07: _build_tree_data uses source_gap_ids for parent refs ─


def test_build_tree_data_uses_source_gap_ids_as_parent_refs():
    """TEST-75-01-07: _build_tree_data uses source_gap_ids as parent refs for ResearchIdea.

    After conversion, ResearchIdea has no parent_idea_ids. The getattr guard
    falls back to source_gap_ids for parent references, preserving tree structure.
    """
    research_ideas = [
        ResearchIdea(
            title="Root Idea",
            problem_statement="Problem",
            proposed_method="Method " * 20,
            expected_contributions="Contrib",
            novelty_rationale="Novel",
            evaluation_approach="Eval",
            domain="AI/NLP",
            round_generated=1,
            score=0.90,
            source_gap_ids=[],
        ),
        ResearchIdea(
            title="Child Idea",
            problem_statement="Problem 2",
            proposed_method="Method 2 " * 20,
            expected_contributions="Contrib 2",
            novelty_rationale="Novel 2",
            evaluation_approach="Eval 2",
            domain="AI/NLP",
            round_generated=1,
            score=0.75,
            source_gap_ids=["gap-alpha", "gap-beta"],
        ),
    ]

    engine = _make_tree_engine([])
    hooks = _make_hooks()
    stage = TreeSearchStage(engine=engine, hooks=hooks)

    tree_data = stage._build_tree_data(research_ideas)

    nodes = tree_data["nodes"]
    assert len(nodes) == 2

    # Root idea has no parent refs
    assert nodes[0]["parent_ids"] == []

    # Child idea uses source_gap_ids as parent refs
    assert nodes[1]["parent_ids"] == ["gap-alpha", "gap-beta"], (
        f"Expected ['gap-alpha', 'gap-beta'], got {nodes[1]['parent_ids']}"
    )
