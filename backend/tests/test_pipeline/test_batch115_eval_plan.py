"""BATCH-115: Evaluation Plan Generator tests.

Validates that the EvaluationPlanGenerator produces structured plans
with datasets, baselines, metrics, and ablation experiments.
"""
import asyncio
import json
import pytest

from backend.pipeline.evaluation.plan_generator import (
    EvaluationPlanGenerator,
    EvaluationPlan,
    DatasetRecommendation,
    BaselineMethod,
    MetricTarget,
    AblationExperiment,
)


# ── TEST-115-01-01: Class exists ──────────────────────────────────

def test_115_01_01_class_exists():
    """EvaluationPlanGenerator can be imported."""
    gen = EvaluationPlanGenerator()
    assert gen is not None


# ── TEST-115-01-02: Template mode produces plan ───────────────────

def test_115_01_02_template_produces_plan():
    """Template mode produces a non-empty evaluation plan."""
    gen = EvaluationPlanGenerator()
    idea = {"id": 1, "title": "Neuro-Symbolic Graph Reasoning", "proposed_method": "Hybrid GoT+NSR"}
    plan = asyncio.run(gen.generate(idea))
    assert isinstance(plan, EvaluationPlan)
    assert len(plan.datasets) > 0, "Plan must have datasets"


# ── TEST-115-01-03: Plan includes datasets ────────────────────────

def test_115_01_03_datasets_section():
    """Plan includes datasets with name, size, availability."""
    gen = EvaluationPlanGenerator()
    plan = asyncio.run(gen.generate({"id": 1, "title": "Test"}))
    assert len(plan.datasets) >= 2, f"Expected ≥2 datasets, got {len(plan.datasets)}"
    for ds in plan.datasets:
        assert ds.name, "Dataset must have a name"
        assert ds.size, "Dataset must have a size"


# ── TEST-115-01-04: Plan includes baselines ───────────────────────

def test_115_01_04_baselines_section():
    """Plan includes baselines with name, citation, description."""
    gen = EvaluationPlanGenerator()
    plan = asyncio.run(gen.generate({"id": 1, "title": "Test"}))
    assert len(plan.baselines) >= 2, f"Expected ≥2 baselines, got {len(plan.baselines)}"
    for bl in plan.baselines:
        assert bl.name, "Baseline must have a name"
        assert bl.citation, "Baseline must have a citation"


# ── TEST-115-01-05: Plan includes metrics with targets ────────────

def test_115_01_05_metrics_with_targets():
    """Plan includes metrics with numeric targets > 0."""
    gen = EvaluationPlanGenerator()
    plan = asyncio.run(gen.generate({"id": 1, "title": "Test"}))
    assert len(plan.metrics) >= 3, f"Expected ≥3 metrics, got {len(plan.metrics)}"
    # At least one metric should have target > 0
    has_positive_target = any(m.target > 0 for m in plan.metrics)
    assert has_positive_target, "At least one metric must have target > 0"


# ── TEST-115-01-06: Plan includes ablation experiments ────────────

def test_115_01_06_ablation_experiments():
    """Plan includes at least 2 ablation experiments."""
    gen = EvaluationPlanGenerator()
    plan = asyncio.run(gen.generate({"id": 1, "title": "Test"}))
    assert len(plan.ablations) >= 2, f"Expected ≥2 ablations, got {len(plan.ablations)}"
    for abl in plan.ablations:
        assert abl.name, "Ablation must have a name"
        assert abl.what_to_remove, "Ablation must specify what to remove"


# ── TEST-115-01-07: Generator handles empty input (HB-01) ─────────

def test_115_01_07_empty_input():
    """Generator handles empty input without crashing (HB-01)."""
    gen = EvaluationPlanGenerator()
    plan = asyncio.run(gen.generate({}))
    assert isinstance(plan, EvaluationPlan)
    # Should return template plan even with empty input
    assert len(plan.datasets) > 0, "Template should always produce datasets"
