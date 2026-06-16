"""BATCH-116: PipelineEvaluator Integration + Gold Standards tests.

Validates gold standard gap lists, orchestrator wiring, and keyword overlap.
"""
import asyncio
import logging
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.pipeline.verification.gold_standards import GOLD_STANDARD_GAPS, get_gold_gaps
from backend.pipeline.verification.pipeline_evaluator import PipelineEvaluator


# ── TEST-116-01-01: Gold standards for 3+ domains ──────────────────

def test_116_01_01_gold_standards_3_domains():
    """Gold standards exist for 3+ domains."""
    assert len(GOLD_STANDARD_GAPS) >= 3, \
        f"Expected ≥3 domains, got {len(GOLD_STANDARD_GAPS)}: {list(GOLD_STANDARD_GAPS.keys())}"


# ── TEST-116-01-02: AI/NLP has 5+ gaps ─────────────────────────────

def test_116_01_02_ai_nlp_5plus_gaps():
    """AI/NLP gold standard has at least 5 gaps."""
    assert "AI/NLP" in GOLD_STANDARD_GAPS
    assert len(GOLD_STANDARD_GAPS["AI/NLP"]) >= 5, \
        f"Expected ≥5 AI/NLP gaps, got {len(GOLD_STANDARD_GAPS['AI/NLP'])}"


# ── TEST-116-01-03: _evaluate_pipeline exists on orchestrator ──────

def test_116_01_03_evaluate_pipeline_exists():
    """evaluate_pipeline method exists on ResultProcessor (used by orchestrator)."""
    from backend.pipeline.orchestrator.result_processor import ResultProcessor
    assert hasattr(ResultProcessor, 'evaluate_pipeline'), \
        "ResultProcessor must have evaluate_pipeline method"


# ── TEST-116-01-04: Evaluation produces quality score ──────────────

def test_116_01_04_quality_score_range():
    """PipelineEvaluator produces a quality score between 0 and 1."""
    evaluator = PipelineEvaluator(known_gaps=["test gap one", "test gap two"])
    report = evaluator.evaluate(
        detected_gaps=[{"title": "test gap one variation", "gap_type": "empirical"}],
        generated_ideas=[{"title": "Idea 1", "novelty_score": 0.8}],
    )
    assert 0.0 <= report.pipeline_quality_score <= 1.0, \
        f"Quality score {report.pipeline_quality_score} outside [0, 1]"


# ── TEST-116-01-05: Non-blocking on failure (HB-01) ───────────────

def test_116_01_05_non_blocking():
    """Evaluation does not crash on malformed input."""
    evaluator = PipelineEvaluator(known_gaps=["a"])
    # Pass completely empty/missing fields
    report = evaluator.evaluate(detected_gaps=[], generated_ideas=[])
    assert report.pipeline_quality_score >= 0.0


# ── TEST-116-01-06: Report stored in result ────────────────────────

def test_116_01_06_report_in_result():
    """PipelineResult has quality_report field."""
    from backend.pipeline.result import PipelineResult
    result = PipelineResult()
    assert hasattr(result, 'quality_report'), \
        "PipelineResult must have quality_report field"
    result.quality_report = {"pipeline_quality_score": 0.75}
    assert result.quality_report["pipeline_quality_score"] == 0.75


# ── TEST-116-01-07: Keyword overlap computes correctly ────────────

def test_116_01_07_keyword_overlap():
    """Keyword overlap computes correctly."""
    evaluator = PipelineEvaluator()
    # "a b c" vs "b c d" → overlap = {b, c} = 2, denominator = {b, c, d} = 3 → 2/3
    overlap = evaluator._keyword_overlap("a b c", "b c d")
    assert abs(overlap - 2/3) < 0.01, f"Expected ~0.667, got {overlap}"
