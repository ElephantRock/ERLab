"""Tests for BATCH-81 — Multi-Dimensional Proposal Evaluation.

TASK-01: ProposalEvaluator (9 tests)
TASK-02: Storage + Frontend (5 tests)

AIV v5.3 — T1, T2, T5. Use asyncio.run() not @pytest.mark.asyncio.
"""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.pipeline.evaluation.proposal_evaluator import (
    ProposalEvaluator,
    ProposalEvaluation,
    DimensionScore,
    DIMENSIONS,
)


@pytest.fixture
def mock_provider():
    provider = AsyncMock()
    provider.complete = AsyncMock(return_value=(
        "NOVELTY_SCORE: 0.85\n"
        "NOVELTY_JUSTIFICATION: Highly novel approach using sparse attention.\n"
        "FEASIBILITY_SCORE: 0.72\n"
        "FEASIBILITY_JUSTIFICATION: Requires moderate compute but achievable.\n"
        "COMPLETENESS_SCORE: 0.80\n"
        "COMPLETENESS_JUSTIFICATION: Covers method and evaluation well.\n"
        "RIGOR_SCORE: 0.65\n"
        "RIGOR_JUSTIFICATION: Some limitations not fully addressed.\n"
        "CLARITY_SCORE: 0.90\n"
        "CLARITY_JUSTIFICATION: Well-structured and clearly written.\n"
        "OVERALL_SCORE: 0.78\n"
    ))
    return provider


# ══════════════════════════════════════════════════════════
# TASK-01: ProposalEvaluator
# ══════════════════════════════════════════════════════════

def test_81_01_01_evaluate_returns_proposal_evaluation(mock_provider):
    """evaluate() returns ProposalEvaluation with 5 dimensions."""
    evaluator = ProposalEvaluator(provider=mock_provider)
    result = asyncio.run(evaluator.evaluate("A proposal about sparse attention."))
    assert isinstance(result, ProposalEvaluation)
    assert result.overall > 0


def test_81_01_02_five_dimensions_scored(mock_provider):
    """All 5 dimensions have scores after evaluation."""
    evaluator = ProposalEvaluator(provider=mock_provider)
    result = asyncio.run(evaluator.evaluate("Test proposal text"))
    for dim in DIMENSIONS:
        ds = getattr(result, dim)
        assert isinstance(ds, DimensionScore)
        assert ds.score >= 0.0


def test_81_01_03_scores_in_range(mock_provider):
    """All scores are in [0.0, 1.0] range (HB-02)."""
    evaluator = ProposalEvaluator(provider=mock_provider)
    result = asyncio.run(evaluator.evaluate("Test proposal"))
    for dim in DIMENSIONS:
        ds = getattr(result, dim)
        assert 0.0 <= ds.score <= 1.0

