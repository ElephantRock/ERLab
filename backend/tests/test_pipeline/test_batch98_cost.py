"""Tests for BATCH-98 — Cost Tracker.

AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

from backend.pipeline.monitoring.cost_tracker import CostTracker, TokenUsage


def test_98_01_record_and_report():
    """Recording usage generates report."""
    tracker = CostTracker()
    tracker.record(TokenUsage(model="gpt-4o", input_tokens=1000, output_tokens=500, stage="gap_analysis"))
    report = tracker.report()
    assert report.total_input_tokens == 1000
    assert report.total_output_tokens == 500
    assert report.total_cost_usd > 0


def test_98_01_ollama_is_free():
    """Ollama model has zero cost."""
    tracker = CostTracker()
    tracker.record(TokenUsage(model="ollama", input_tokens=10000, output_tokens=5000))
    report = tracker.report()
    assert report.total_cost_usd == 0.0


def test_98_01_aggregates_by_stage():
    """Multiple usages aggregate by stage."""
    tracker = CostTracker()
    tracker.record(TokenUsage(model="gpt-4o", input_tokens=1000, output_tokens=500, stage="gap_analysis"))
    tracker.record(TokenUsage(model="gpt-4o", input_tokens=2000, output_tokens=1000, stage="synthesis"))
    report = tracker.report()
    assert "gap_analysis" in report.by_stage
    assert "synthesis" in report.by_stage
    assert report.by_stage["gap_analysis"]["input"] == 1000


def test_98_01_aggregates_by_model():
    """Multiple models aggregate separately."""
    tracker = CostTracker()
    tracker.record(TokenUsage(model="gpt-4o", input_tokens=1000, output_tokens=500))
    tracker.record(TokenUsage(model="claude-3-sonnet", input_tokens=2000, output_tokens=1000))
    report = tracker.report()
    assert "gpt-4o" in report.by_model
    assert "claude-3-sonnet" in report.by_model


def test_98_02_total_tokens():
    """total_tokens is sum of input + output."""
    tracker = CostTracker()
    tracker.record(TokenUsage(model="gpt-4o", input_tokens=300, output_tokens=200))
    report = tracker.report()
    assert report.total_tokens == 500


def test_98_02_usage_count():
    """usage_count reflects recordings."""
    tracker = CostTracker()
    assert tracker.usage_count == 0
    tracker.record(TokenUsage(model="gpt-4o"))
    assert tracker.usage_count == 1


def test_98_02_unknown_model_uses_default():
    """Unknown model uses default pricing."""
    tracker = CostTracker()
    tracker.record(TokenUsage(model="custom-model", input_tokens=1000, output_tokens=500))
    report = tracker.report()
    assert report.total_cost_usd > 0  # Default pricing applied


def test_98_02_empty_report():
    """Empty tracker produces zero report."""
    tracker = CostTracker()
    report = tracker.report()
    assert report.total_tokens == 0
    assert report.total_cost_usd == 0.0
