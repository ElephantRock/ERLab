"""Tests for the Idea Recombination Operator (BATCH-62/TASK-02).

Required tests:
  TEST-62-02-01  Recombination produces exactly 1 child (HB-02)
  TEST-62-02-02  Child has parent_idea_ids with both parent IDs (HB-02)
  TEST-62-02-03  Recombination delegates to provider.complete(), not directly
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from backend.pipeline.generation.models import IdeaCandidate
from backend.pipeline.generation.recombination import IdeaRecombinator


def _make_parent(suffix: str, idea_id: str) -> IdeaCandidate:
    return IdeaCandidate(
        id=idea_id,
        title=f"Parent Idea {suffix}",
        problem_statement=f"Problem for idea {suffix}",
        proposed_method=f"Method for idea {suffix}",
        expected_contributions=f"Contributions for idea {suffix}",
    )


_CHILD_JSON = json.dumps(
    {
        "title": "Hybrid combined approach",
        "problem_statement": "Broader problem scope addressing both parent gaps",
        "proposed_method": "Hybrid method combining both parent methodologies",
        "expected_contributions": "Novel contributions beyond either parent",
        "novelty_rationale": "First combination of these approaches",
        "evaluation_approach": "Benchmark evaluation with ablation studies",
    }
)


@pytest.fixture()
def mock_provider():
    """AsyncMock provider whose ``complete()`` returns controlled JSON."""
    provider = AsyncMock()
    provider.complete.return_value = _CHILD_JSON
    return provider


@pytest.fixture()
def parent_a() -> IdeaCandidate:
    return _make_parent("A", "pa-001")


@pytest.fixture()
def parent_b() -> IdeaCandidate:
    return _make_parent("B", "pb-002")


# ── TEST-62-02-01: exactly 1 child produced (HB-02) ────────────────────────


@pytest.mark.anyio
async def test_recombine_produces_exactly_one_child(
    mock_provider, parent_a, parent_b
):
    """HB-02: recombine() returns a single IdeaCandidate, not a list."""
    recombinator = IdeaRecombinator(provider=mock_provider)
    child = await recombinator.recombine(parent_a, parent_b)

    assert isinstance(child, IdeaCandidate)


# ── TEST-62-02-02: child has parent_idea_ids with both parent IDs (HB-02) ──


@pytest.mark.anyio
async def test_recombine_child_has_parent_lineage(
    mock_provider, parent_a, parent_b
):
    """HB-02: child.parent_idea_ids contains both parent IDs."""
    recombinator = IdeaRecombinator(provider=mock_provider)
    child = await recombinator.recombine(parent_a, parent_b)

    assert child.parent_idea_ids is not None
    assert parent_a.id in child.parent_idea_ids
    assert parent_b.id in child.parent_idea_ids
    assert len(child.parent_idea_ids) == 2


# ── TEST-62-02-03: delegates to provider.complete() ────────────────────────


@pytest.mark.anyio
async def test_recombine_delegates_to_provider_complete(
    mock_provider, parent_a, parent_b
):
    """AC-02-03: recombine delegates generation to provider.complete()."""
    recombinator = IdeaRecombinator(provider=mock_provider)
    await recombinator.recombine(parent_a, parent_b)

    mock_provider.complete.assert_awaited_once()
    call_args = mock_provider.complete.call_args
    messages = call_args.kwargs.get("messages") or call_args[0][0]
    # Verify the prompt includes both parent titles
    user_msg = messages[-1]["content"]
    assert parent_a.title in user_msg
    assert parent_b.title in user_msg
