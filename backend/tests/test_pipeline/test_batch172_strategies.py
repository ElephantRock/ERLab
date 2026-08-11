"""BATCH-172 TASK-03: Strategy Preset Validation.

Verify that strategy presets correctly enable/disable
gap_reflection, idea_reflection, and evaluation stages.
"""
from __future__ import annotations

from backend.pipeline.strategies.presets import register_presets
from backend.pipeline.strategies.registry import StrategyRegistry


def _get_strategy_config(strategy_name: str):
    """Get the strategy config for a given strategy name."""
    registry = StrategyRegistry()
    register_presets(registry)
    return registry.get(strategy_name)


# ── Test 1: deep_research enables gap_reflection ────────────────────────

def test_deep_research_enables_gap_reflection():
    config = _get_strategy_config("deep_research")
    stage = config.stages.get("gap_reflection")
    assert stage is not None, "deep_research missing gap_reflection stage"
    assert stage.enabled is True


# ── Test 2: deep_research enables idea_reflection ───────────────────────

def test_deep_research_enables_idea_reflection():
    config = _get_strategy_config("deep_research")
    stage = config.stages.get("idea_reflection")
    assert stage is not None, "deep_research missing idea_reflection stage"
    assert stage.enabled is True


# ── Test 3: deep_research enables evaluation ────────────────────────────

def test_deep_research_enables_evaluation():
    config = _get_strategy_config("deep_research")
    stage = config.stages.get("evaluation")
    assert stage is not None, "deep_research missing evaluation stage"
    assert stage.enabled is True


# ── Test 4: fast_scan disables all 3 ────────────────────────────────────

def test_fast_scan_disables_all_three():
    config = _get_strategy_config("fast_scan")
    for name in ("gap_reflection", "idea_reflection", "evaluation"):
        stage = config.stages.get(name)
        assert stage is not None, f"fast_scan missing {name}"
        assert stage.enabled is False, f"fast_scan should disable {name}"


# ── Test 5: literature_review disables all 3 ────────────────────────────

def test_literature_review_disables_all_three():
    config = _get_strategy_config("literature_review")
    for name in ("gap_reflection", "idea_reflection", "evaluation"):
        stage = config.stages.get(name)
        assert stage is not None, f"literature_review missing {name}"
        assert stage.enabled is False, f"literature_review should disable {name}"


# ── Test 6: academic_proposal enables all 3 ─────────────────────────────

def test_academic_proposal_enables_all_three():
    config = _get_strategy_config("academic_proposal")
    for name in ("gap_reflection", "idea_reflection", "evaluation"):
        stage = config.stages.get(name)
        assert stage is not None, f"academic_proposal missing {name}"
        assert stage.enabled is True, f"academic_proposal should enable {name}"
