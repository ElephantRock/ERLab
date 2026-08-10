"""Tests for BATCH-RAG-08: Ablation Study Runner."""

import asyncio

import pytest

from backend.pipeline.experiment.ablation import (
    ABLATABLE_COMPONENTS,
    AblationReport,
    AblationResult,
    AblationRunner,
    AblationVariant,
)


def test_ablatable_components():
    """ABLATABLE_COMPONENTS contains key pipeline stages."""
    assert "novelty_checking" in ABLATABLE_COMPONENTS
    assert "adversarial_review" in ABLATABLE_COMPONENTS
    assert "proposal_deepening" in ABLATABLE_COMPONENTS


def test_variant_to_strategy_config():
    """AblationVariant produces correct StrategyConfig."""
    variant = AblationVariant(
        name="without_novelty",
        disabled_components=["novelty_checking"],
    )
    config = variant.to_strategy_config()
    assert "novelty_checking" in config.stages
    assert config.stages["novelty_checking"].enabled is False
    # Other stages should be enabled
    assert config.stages["gap_analysis"].enabled is True


def test_variant_baseline():
    """Baseline variant has no disabled components."""
    variant = AblationVariant(name="baseline", disabled_components=[])
    config = variant.to_strategy_config()
    # All stages enabled
    for name, stage in config.stages.items():
        assert stage.enabled is True


def test_runner_plan_ablation():
    """AblationRunner generates correct number of variants."""
    runner = AblationRunner(dry_run=True)
    variants = runner.plan_ablation("AI/NLP")
    # 1 baseline + 1 per ablatable component
    assert len(variants) == 1 + len(ABLATABLE_COMPONENTS)
    assert variants[0].name == "baseline"


def test_runner_plan_custom_components():
    """AblationRunner accepts custom component list."""
    runner = AblationRunner(dry_run=True)
    variants = runner.plan_ablation(
        "AI/NLP",
        components=["novelty_checking", "adversarial_review"],
    )
    assert len(variants) == 3  # baseline + 2


def test_runner_dry_run():
    """AblationRunner in dry_run mode produces mock results."""
    runner = AblationRunner(dry_run=True)
    report = asyncio.run(runner.run_ablation(
        "AI/NLP",
        components=["novelty_checking"],
    ))
    assert len(report.variants) == 2  # baseline + 1 ablation
    assert report.baseline_metrics["hit_rate"] > 0


def test_ablation_report_deltas():
    """AblationReport computes correct deltas."""
    report = AblationReport(
        baseline_metrics={"hit_rate": 0.85, "mrr": 0.72},
        variants=[
            AblationResult(
                variant_name="without_novelty",
                disabled_components=["novelty_checking"],
                metrics={"hit_rate": 0.80, "mrr": 0.65},
            ),
        ],
    )
    report.compute_deltas()
    assert report.deltas["without_novelty"]["hit_rate"] == pytest.approx(-0.05)
    assert report.deltas["without_novelty"]["mrr"] == pytest.approx(-0.07)


def test_ablation_report_to_dict():
    """AblationReport serializes to dict."""
    report = AblationReport(
        domain="AI/NLP",
        baseline_metrics={"hit_rate": 0.85},
        variants=[
            AblationResult(
                variant_name="baseline",
                disabled_components=[],
                metrics={"hit_rate": 0.85},
            ),
        ],
    )
    d = report.to_dict()
    assert d["domain"] == "AI/NLP"
    assert len(d["variants"]) == 1
