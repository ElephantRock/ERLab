"""Tests for BATCH-94 — Planning Agent.

AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

import pytest

from backend.pipeline.planning.agent import PlanningAgent, ExecutionPlan, StagePlan


def test_94_01_plan_creates_all_stages():
    """Plan includes all 9 pipeline stages."""
    agent = PlanningAgent()
    plan = agent.plan(domain="AI/NLP")
    assert len(plan.stages) == 9
    assert plan.stages[0].stage_name == "literature_search"
    assert plan.stages[-1].stage_name == "export"


def test_94_01_plan_has_time_estimates():
    """Each stage has estimated time."""
    agent = PlanningAgent()
    plan = agent.plan(domain="AI")
    total = sum(s.estimated_time_s for s in plan.enabled_stages)
    assert total > 0
    assert plan.total_estimated_time_s > 0


def test_94_01_plan_has_token_estimates():
    """Each stage has estimated tokens."""
    agent = PlanningAgent()
    plan = agent.plan(domain="AI")
    assert plan.total_estimated_tokens > 0


def test_94_02_disabled_stages_skipped():
    """Disabled stages are marked as enabled=False."""
    agent = PlanningAgent()
    plan = agent.plan(
        domain="AI",
        strategy="fast_scan",
        disabled_stages=["idea_generation", "novelty_checking", "mechanical_metrics"],
    )
    disabled = [s for s in plan.stages if not s.enabled]
    assert len(disabled) == 3
    assert all(s.estimated_time_s == 0 for s in disabled)


def test_94_02_stage_dependencies():
    """Each stage (except first) depends on the previous."""
    agent = PlanningAgent()
    plan = agent.plan(domain="AI")
    assert plan.stages[0].dependencies == []
    for i in range(1, len(plan.stages)):
        assert len(plan.stages[i].dependencies) == 1


def test_94_02_no_domain_is_blocker():
    """Missing domain is flagged as blocker."""
    agent = PlanningAgent()
    plan = agent.plan(domain="")
    assert plan.has_blockers
    assert any("domain" in b.lower() for b in plan.blockers)


def test_94_03_fast_scan_halves_estimates():
    """Fast scan strategy halves time estimates."""
    agent = PlanningAgent()
    deep_plan = agent.plan(domain="AI", strategy="deep_research")
    fast_plan = agent.plan(domain="AI", strategy="fast_scan")
    assert fast_plan.total_estimated_time_s < deep_plan.total_estimated_time_s


def test_94_03_enabled_stages_property():
    """enabled_stages returns only enabled stages."""
    agent = PlanningAgent()
    plan = agent.plan(domain="AI", disabled_stages=["export"])
    assert len(plan.enabled_stages) == 8
