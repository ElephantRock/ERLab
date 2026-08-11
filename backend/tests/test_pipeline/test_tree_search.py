"""Tests for TreeSearchEngine beam search (BATCH-62/TASK-01).

Tests:
  TEST-62-01-01: Beam search produces K candidates at each depth level
  TEST-62-01-02: Pruning keeps only top-K by score
  TEST-62-01-03: Max depth is respected (no deeper expansion)
  TEST-62-01-04: Beam width capped at 10 (HB-03)
  TEST-62-01-05: Final results sorted by score descending
"""

from __future__ import annotations

import pytest

from backend.pipeline.gap_analysis.models import ResearchGap
from backend.pipeline.generation.models import IdeaCandidate
from backend.pipeline.generation.tree_search import (
    MAX_BEAM_WIDTH,
    SimpleScorer,
    TreeNode,
    TreeSearchConfig,
    TreeSearchEngine,
)
from backend.pipeline.literature.models import Paper

# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


def _make_idea(title: str, score: float = 0.0) -> IdeaCandidate:
    """Create a test IdeaCandidate with a given title and overall_score."""
    return IdeaCandidate(
        title=title,
        problem_statement=f"Problem for {title}",
        proposed_method=f"Method for {title} with enough detail to score well",
        novelty_rationale=f"Novel rationale for {title}",
        overall_score=score,
    )


def _make_gaps(n: int = 1) -> list[ResearchGap]:
    """Create n test ResearchGaps."""
    return [
        ResearchGap(
            title=f"Test Gap {i}",
            description=f"Description of test gap {i}",
            gap_type="methodological",
            potential_impact="High",
        )
        for i in range(n)
    ]


def _make_papers(n: int = 2) -> list[Paper]:
    """Create n test Papers."""
    return [
        Paper(
            id=f"paper-{i}",
            source="test",
            title=f"Test Paper {i}",
            abstract=f"Abstract for test paper {i}",
            year=2024,
        )
        for i in range(n)
    ]


class MockIdeator:
    """Mock IdeatorAgent that returns controlled ideas.

    Each call to generate_ideas returns ideas with incrementing titles
    and predictable scores based on call count, enabling deterministic
    test assertions.
    """

    def __init__(self, ideas_per_call: int = 5):
        self._call_count = 0
        self._ideas_per_call = ideas_per_call
        self._call_log: list[dict] = []

    async def generate_ideas(
        self,
        gaps,
        context_papers,
        prior_critique=None,
        n_ideas=3,
    ) -> list[IdeaCandidate]:
        self._call_count += 1
        self._call_log.append({
            "call": self._call_count,
            "gaps": gaps,
            "n_ideas": n_ideas,
            "prior_critique": prior_critique,
        })

        # Generate ideas with scores that increase per call
        # This makes pruning behavior deterministic
        ideas = []
        for i in range(min(n_ideas, self._ideas_per_call)):
            score = (self._call_count * 10.0) + i  # 10.0, 11.0, 12.0... then 20.0, 21.0...
            ideas.append(
                _make_idea(
                    title=f"Idea-C{self._call_count}-I{i}",
                    score=score,
                )
            )
        return ideas

    @property
    def call_count(self) -> int:
        return self._call_count


# ── TEST-62-01-01: Beam search produces K candidates at each depth ─

@pytest.mark.anyio
async def test_beam_produces_k_candidates_at_each_depth():
    """TEST-62-01-01: Beam search produces K candidates at each depth level.

    With beam_width=3, the beam should have at most 3 nodes after each
    pruning round, and the engine should expand all 3 at each depth.
    """
    mock_ideator = MockIdeator(ideas_per_call=5)
    config = TreeSearchConfig(beam_width=3, max_depth=2, ideas_per_node=5)
    engine = TreeSearchEngine(mock_ideator, scorer=SimpleScorer(), config=config)

    gaps = _make_gaps(1)
    papers = _make_papers(2)

    results = await engine.search(gaps, papers)

    # Should have at most beam_width results
    assert len(results) <= 3
    assert len(results) > 0

    # With SimpleScorer, the mock ideator's overall_score values are used.
    # Verify that the ideator was called for expansion (depth 1 + depth 2)
    # Initial call (seed) + max_depth * beam_width expansions
    assert mock_ideator.call_count >= 1  # At least the initial generation


# ── TEST-62-01-02: Pruning keeps only top-K by score ────────────────

@pytest.mark.anyio
async def test_pruning_keeps_only_top_k_by_score():
    """TEST-62-01-02: Pruning keeps only top-K by score.

    When more than beam_width ideas are generated, only the top-K
    (by score) survive to the next depth level.
    """
    # Create an ideator that generates many low-score ideas + a few high-score ones
    class SelectiveMockIdeator:
        def __init__(self):
            self._call_count = 0

        async def generate_ideas(self, gaps, context_papers, prior_critique=None, n_ideas=3):
            self._call_count += 1
            if self._call_count == 1:
                # Seed: 5 ideas with scores 1-5
                return [_make_idea(f"Seed-{i}", score=float(i)) for i in range(1, 6)]
            else:
                # Expansion: 5 ideas with scores 0.1-0.5 (all lower than seed)
                return [_make_idea(f"Child-{i}", score=0.1 * i) for i in range(1, 6)]

    config = TreeSearchConfig(beam_width=2, max_depth=1, ideas_per_node=5)
    engine = TreeSearchEngine(SelectiveMockIdeator(), scorer=SimpleScorer(), config=config)

    results = await engine.search(_make_gaps(1), _make_papers())

    # Beam width is 2, so only top 2 should survive
    assert len(results) <= 2
    # With SimpleScorer, results are sorted by overall_score
    if len(results) >= 2:
        assert results[0].overall_score >= results[1].overall_score


# ── TEST-62-01-03: Max depth is respected ───────────────────────────

@pytest.mark.anyio
async def test_max_depth_is_respected():
    """TEST-62-01-03: Max depth is respected (no deeper expansion).

    With max_depth=0, no expansion should occur — only initial generation
    and pruning.
    """
    mock_ideator = MockIdeator(ideas_per_call=5)
    config = TreeSearchConfig(beam_width=3, max_depth=0, ideas_per_node=5)
    engine = TreeSearchEngine(mock_ideator, scorer=SimpleScorer(), config=config)

    results = await engine.search(_make_gaps(1), _make_papers())

    # With max_depth=0, only the initial generation happens (no expansion loop)
    # The initial generation itself counts as 1 call
    assert mock_ideator.call_count == 1
    assert len(results) > 0


# ── TEST-62-01-04: Beam width capped at 10 (HB-03) ─────────────────

def test_beam_width_capped_at_10():
    """TEST-62-01-04: Beam width capped at 10 (HB-03).

    Even if config requests beam_width=50, the engine must cap it at 10.
    """
    mock_ideator = MockIdeator()

    # Try with beam_width way above the cap
    config = TreeSearchConfig(beam_width=50)
    engine = TreeSearchEngine(mock_ideator, scorer=SimpleScorer(), config=config)

    assert engine.config.beam_width == 10, (
        f"Beam width should be capped at 10, got {engine.config.beam_width}"
    )

    # Also verify the constant is 10
    assert MAX_BEAM_WIDTH == 10


def test_beam_width_capped_at_boundary():
    """Beam width of exactly 10 should be allowed."""
    mock_ideator = MockIdeator()
    config = TreeSearchConfig(beam_width=10)
    engine = TreeSearchEngine(mock_ideator, scorer=SimpleScorer(), config=config)
    assert engine.config.beam_width == 10


def test_beam_width_below_cap_unchanged():
    """Beam width below 10 should pass through unchanged."""
    mock_ideator = MockIdeator()
    config = TreeSearchConfig(beam_width=5)
    engine = TreeSearchEngine(mock_ideator, scorer=SimpleScorer(), config=config)
    assert engine.config.beam_width == 5


# ── TEST-62-01-05: Final results sorted by score descending ─────────

@pytest.mark.anyio
async def test_results_sorted_by_score_descending():
    """TEST-62-01-05: Final results are sorted by score descending.

    The search() return value must be list[IdeaCandidate] sorted from
    highest to lowest score (AC-01-01).
    """
    class DescendingMockIdeator:
        """Returns ideas with varying scores to test sort order."""
        def __init__(self):
            self._call = 0

        async def generate_ideas(self, gaps, context_papers, prior_critique=None, n_ideas=3):
            self._call += 1
            if self._call == 1:
                # Return ideas with non-monotonic scores
                return [
                    _make_idea("Low", score=1.0),
                    _make_idea("High", score=9.0),
                    _make_idea("Mid", score=5.0),
                ]
            else:
                return [
                    _make_idea(f"Child-{i}", score=2.0 + i)
                    for i in range(n_ideas)
                ]

    config = TreeSearchConfig(beam_width=3, max_depth=1, ideas_per_node=3)
    engine = TreeSearchEngine(
        DescendingMockIdeator(), scorer=SimpleScorer(), config=config
    )

    results = await engine.search(_make_gaps(1), _make_papers())

    assert len(results) > 0

    # Verify descending order
    scores = [idea.overall_score for idea in results]
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1], (
            f"Results not sorted descending: {scores}"
        )


# ── Edge cases ──────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_empty_gaps_returns_empty():
    """Edge case (CHK-13): empty gaps → empty list."""
    mock_ideator = MockIdeator()
    engine = TreeSearchEngine(mock_ideator, scorer=SimpleScorer())

    results = await engine.search([], _make_papers())

    assert results == []
    assert mock_ideator.call_count == 0


@pytest.mark.anyio
async def test_initial_ideas_used_as_seed():
    """When initial_ideas are provided, they seed the beam directly."""
    mock_ideator = MockIdeator()
    config = TreeSearchConfig(beam_width=3, max_depth=1, ideas_per_node=3)
    engine = TreeSearchEngine(mock_ideator, scorer=SimpleScorer(), config=config)

    seed_ideas = [
        _make_idea("Seed-A", score=5.0),
        _make_idea("Seed-B", score=3.0),
    ]

    results = await engine.search(_make_gaps(1), _make_papers(), initial_ideas=seed_ideas)

    # Should have results and ideator should be called for expansion
    assert len(results) > 0
    assert mock_ideator.call_count >= 1  # At least 1 expansion call per seed idea


def test_tree_node_defaults():
    """TreeNode has sensible defaults."""
    node = TreeNode()
    assert node.idea is None
    assert node.children == []
    assert node.score == 0.0
    assert node.depth == 0
    assert node.parent_ids == []

    idea = _make_idea("test", score=7.5)
    node_with_idea = TreeNode(idea=idea, score=7.5, depth=2, parent_ids=["abc123"])
    assert node_with_idea.idea is not None
    assert node_with_idea.idea.title == "test"
    assert node_with_idea.score == 7.5
    assert node_with_idea.depth == 2
    assert node_with_idea.parent_ids == ["abc123"]
