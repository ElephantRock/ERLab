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


def test_81_01_04_justifications_present(mock_provider):
    """Each dimension has a text justification."""
    evaluator = ProposalEvaluator(provider=mock_provider)
    result = asyncio.run(evaluator.evaluate("Test proposal"))
    for dim in DIMENSIONS:
        ds = getattr(result, dim)
        assert ds.justification  # Non-empty


def test_81_01_05_overall_calculated(mock_provider):
    """Overall score is calculated from dimensions."""
    evaluator = ProposalEvaluator(provider=mock_provider)
    result = asyncio.run(evaluator.evaluate("Test proposal"))
    assert 0.0 < result.overall <= 1.0


def test_81_01_06_no_provider_returns_default():
    """Without provider, returns default (empty) evaluation (HB-03)."""
    evaluator = ProposalEvaluator(provider=None)
    result = asyncio.run(evaluator.evaluate("Test proposal"))
    assert isinstance(result, ProposalEvaluation)
    assert result.overall == 0.0


def test_81_01_07_timeout_returns_default():
    """LLM timeout returns default evaluation (HB-03)."""
    provider = AsyncMock()
    provider.complete = AsyncMock(side_effect=TimeoutError("timeout"))
    evaluator = ProposalEvaluator(provider=provider)
    result = asyncio.run(evaluator.evaluate("Test"))
    assert result.overall == 0.0


def test_81_01_08_parse_response():
    """_parse_response correctly extracts all 5 dimensions."""
    text = (
        "NOVELTY_SCORE: 0.9\nNOVELTY_JUSTIFICATION: Very new.\n"
        "FEASIBILITY_SCORE: 0.7\nFEASIBILITY_JUSTIFICATION: Achievable.\n"
        "COMPLETENESS_SCORE: 0.8\nCOMPLETENESS_JUSTIFICATION: Complete.\n"
        "RIGOR_SCORE: 0.6\nRIGOR_JUSTIFICATION: Some gaps.\n"
        "CLARITY_SCORE: 0.95\nCLARITY_JUSTIFICATION: Clear.\n"
        "OVERALL_SCORE: 0.79\n"
    )
    result = ProposalEvaluator._parse_response(text)
    assert result.novelty.score == 0.9
    assert result.clarity.score == 0.95
    assert result.overall == 0.79


def test_81_01_09_serialization_round_trip():
    """ProposalEvaluation.to_dict() → from_dict() round-trips."""
    original = ProposalEvaluation(
        novelty=DimensionScore(0.9, "Very novel"),
        feasibility=DimensionScore(0.7, "Achievable"),
        completeness=DimensionScore(0.8, "Complete"),
        rigor=DimensionScore(0.6, "Some gaps"),
        clarity=DimensionScore(0.95, "Clear"),
        overall=0.79,
    )
    data = original.to_dict()
    restored = ProposalEvaluation.from_dict(data)
    assert restored.novelty.score == 0.9
    assert restored.novelty.justification == "Very novel"
    assert restored.overall == 0.79


# ══════════════════════════════════════════════════════════
# TASK-02: Storage + Data Model
# ══════════════════════════════════════════════════════════

def test_81_02_01_to_dict_json_serializable():
    """Evaluation to_dict is JSON-serializable."""
    import json
    evaluation = ProposalEvaluation(
        novelty=DimensionScore(0.85, "Novel"),
        overall=0.75,
    )
    json_str = json.dumps(evaluation.to_dict())
    assert "novelty" in json_str


def test_81_02_02_dimension_score_clamped():
    """DimensionScore clamps to [0, 1]."""
    ds_high = DimensionScore(score=2.0)
    assert ds_high.score == 1.0
    ds_neg = DimensionScore(score=-1.0)
    assert ds_neg.score == 0.0


def test_81_02_03_from_dict_handles_missing():
    """from_dict handles missing/empty fields gracefully."""
    result = ProposalEvaluation.from_dict({})
    assert result.novelty.score == 0.0
    assert result.overall == 0.0


def test_81_02_04_dimensions_constant():
    """DIMENSIONS constant has exactly 5 entries."""
    assert len(DIMENSIONS) == 5
    assert "novelty" in DIMENSIONS
    assert "feasibility" in DIMENSIONS
    assert "completeness" in DIMENSIONS
    assert "rigor" in DIMENSIONS
    assert "clarity" in DIMENSIONS


def test_81_02_05_empty_proposal_text():
    """Empty proposal text returns default evaluation."""
    evaluator = ProposalEvaluator(provider=AsyncMock())
    result = asyncio.run(evaluator.evaluate(""))
    assert result.overall == 0.0
