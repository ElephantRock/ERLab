"""Tests for BATCH-99 — Run Comparison.

AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

from backend.pipeline.comparison import RunComparator, RunComparison


def _make_run(id, papers=10, gaps=3, ideas=2, duration=120, strategy="deep_research"):
    return {
        "id": id, "paper_count": papers, "gap_count": gaps,
        "idea_count": ideas, "duration_seconds": duration,
        "strategy": strategy, "domain": "AI/NLP",
    }


def test_99_01_compare_two_runs():
    """Comparator returns RunComparison."""
    comp = RunComparator()
    result = comp.compare(_make_run("run-1"), _make_run("run-2"))
    assert isinstance(result, RunComparison)
    assert result.run_a_id == "run-1"
    assert result.run_b_id == "run-2"


def test_99_01_paper_delta():
    """Paper delta is computed correctly."""
    comp = RunComparator()
    result = comp.compare(_make_run("a", papers=10), _make_run("b", papers=15))
    assert result.paper_delta == 5


def test_99_01_negative_delta():
    """Negative delta when second run has fewer."""
    comp = RunComparator()
    result = comp.compare(_make_run("a", gaps=5), _make_run("b", gaps=2))
    assert result.gap_delta == -3


def test_99_01_duration_delta():
    """Duration delta computed correctly."""
    comp = RunComparator()
    result = comp.compare(_make_run("a", duration=120), _make_run("b", duration=60))
    assert result.duration_delta == -60.0


def test_99_02_summary_dict():
    """summary() returns structured dict."""
    comp = RunComparator()
    result = comp.compare(_make_run("a"), _make_run("b"))
    s = result.summary()
    assert "papers" in s
    assert "gaps" in s
    assert "ideas" in s
    assert s["papers"]["delta"] == 0


def test_99_02_different_strategies():
    """Different strategies are captured."""
    comp = RunComparator()
    result = comp.compare(
        _make_run("a", strategy="deep_research"),
        _make_run("b", strategy="fast_scan"),
    )
    assert result.strategy_a == "deep_research"
    assert result.strategy_b == "fast_scan"


def test_99_02_missing_fields_default():
    """Missing fields default to 0/empty."""
    comp = RunComparator()
    result = comp.compare({}, {})
    assert result.papers_a == 0
    assert result.papers_b == 0
    assert result.strategy_a == ""


def test_99_02_idea_delta():
    """Idea delta computed correctly."""
    comp = RunComparator()
    result = comp.compare(_make_run("a", ideas=2), _make_run("b", ideas=5))
    assert result.idea_delta == 3
