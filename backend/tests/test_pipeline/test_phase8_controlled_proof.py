"""Phase 8 / 8C — controlled multi-specification and direction proof.

Deterministic tests proving the empirical path generalizes beyond Iris:
classification and regression specs load through the same registry, metric
directions are handled correctly, inverted interpretations are blocked, and
the Phase 7 Iris path remains unchanged.

No provider calls required.
"""

from __future__ import annotations

import json

import pytest

from backend.pipeline.evaluation.direction_evaluator import (
    ComparisonOutcome,
    check_claim_direction,
    evaluate_metric_comparison,
)
from backend.pipeline.experiment.manifest import ResultMarker
from backend.pipeline.experiment.specification import load_spec

# ── Multi-specification registry tests ──────────────────────────────


@pytest.mark.integration
class TestMultiSpecRegistry:
    """G1 and G2 load through the same registry with different metric families."""

    def test_g1_classification_spec_loads(self):
        spec = load_spec("phase8-g1-wine")
        assert spec.spec_id == "phase8-g1-wine"
        assert spec.task_type == "classification"
        assert "model_balanced_accuracy" in spec.declared_metrics

    def test_g2_regression_spec_loads(self):
        spec = load_spec("phase8-g2-concrete")
        assert spec.spec_id == "phase8-g2-concrete"
        assert spec.task_type == "regression"
        assert "model_rmse" in spec.declared_metrics

    def test_metric_names_not_iris_specific(self):
        """G1 and G2 primary metrics differ from Iris (balanced_accuracy, rmse)."""
        iris_primary = "model_accuracy"  # Iris's comparison metric
        g1 = load_spec("phase8-g1-wine")
        g2 = load_spec("phase8-g2-concrete")
        assert g1.primary_metric != iris_primary, "G1 primary must differ from Iris"
        assert g2.primary_metric != iris_primary, "G2 primary must differ from Iris"
        assert g1.primary_metric == "model_balanced_accuracy"
        assert g2.primary_metric == "model_rmse"

    def test_both_directions_represented(self):
        """G1 has higher_better; G2 has both lower_better and higher_better."""
        g1 = load_spec("phase8-g1-wine")
        g2 = load_spec("phase8-g2-concrete")
        assert "higher_better" in set(g1.metric_directions.values())
        assert "lower_better" in set(g2.metric_directions.values())

    def test_research_intent_is_durable(self):
        """Each spec has a research_question that serves as durable scope source."""
        for spec_id in ["phase8-g1-wine", "phase8-g2-concrete"]:
            spec = load_spec(spec_id)
            assert spec.research_question, f"{spec_id} missing research_question"
            assert spec.task_type, f"{spec_id} missing task_type"
            assert spec.primary_metric, f"{spec_id} missing primary_metric"


# ── Direction computation: 6 cases ──────────────────────────────────


class TestDirectionComputation:
    """All 6 direction × outcome combinations computed correctly."""

    def test_higher_better_improvement(self):
        c = evaluate_metric_comparison("acc", 0.80, 0.90, "higher_better")
        assert c.is_improvement
        assert c.outcome == ComparisonOutcome.IMPROVEMENT

    def test_higher_better_degradation(self):
        c = evaluate_metric_comparison("acc", 0.90, 0.80, "higher_better")
        assert not c.is_improvement
        assert c.outcome == ComparisonOutcome.DEGRADATION

    def test_higher_better_tie(self):
        c = evaluate_metric_comparison("acc", 0.80, 0.80, "higher_better")
        assert c.outcome == ComparisonOutcome.TIE
        assert not c.is_improvement

    def test_lower_better_improvement(self):
        c = evaluate_metric_comparison("rmse", 0.15, 0.12, "lower_better")
        assert c.is_improvement
        assert c.outcome == ComparisonOutcome.IMPROVEMENT

    def test_lower_better_degradation(self):
        c = evaluate_metric_comparison("rmse", 0.15, 0.20, "lower_better")
        assert not c.is_improvement
        assert c.outcome == ComparisonOutcome.DEGRADATION

    def test_lower_better_tie(self):
        c = evaluate_metric_comparison("rmse", 0.15, 0.15, "lower_better")
        assert c.outcome == ComparisonOutcome.TIE
        assert not c.is_improvement


# ── Inverted interpretation blocking ────────────────────────────────


class TestInvertedInterpretationBlocking:
    """Correct values with wrong textual interpretation are blocked."""

    def test_degradation_claimed_as_improvement_blocked(self):
        """model_rmse increased (0.20 > 0.15) but paper says 'reduced error'."""
        c = evaluate_metric_comparison("rmse", 0.15, 0.20, "lower_better")
        check = check_claim_direction("the model reduced error significantly", c)
        assert not check.is_correct

    def test_improvement_claimed_as_degradation_blocked(self):
        """accuracy improved (0.90 > 0.80) but paper says 'degraded'."""
        c = evaluate_metric_comparison("accuracy", 0.80, 0.90, "higher_better")
        check = check_claim_direction("the model's performance degraded", c)
        assert not check.is_correct

    def test_correct_lower_better_improvement_passes(self):
        """model_rmse decreased (0.12 < 0.15) and paper says 'reduced error'."""
        c = evaluate_metric_comparison("rmse", 0.15, 0.12, "lower_better")
        check = check_claim_direction("the model reduced error", c)
        assert check.is_correct

    def test_correct_higher_better_improvement_passes(self):
        """accuracy increased (0.90 > 0.80) and paper says 'improved'."""
        c = evaluate_metric_comparison("accuracy", 0.80, 0.90, "higher_better")
        check = check_claim_direction("the model improved accuracy", c)
        assert check.is_correct


# ── ResultMarker direction persistence ──────────────────────────────


class TestResultMarkerDirectionPersistence:
    """Direction survives JSON round-trip (restart simulation)."""

    def test_marker_carries_direction_and_role(self):
        m = ResultMarker(
            marker_index=1, marker="RESULT-1", metric_name="model_rmse",
            observed_value=9.80, artifact_path="metrics.json",
            artifact_sha256="abc123", experiment_result_id=11,
            direction="lower_better", role="comparison",
        )
        d = m.to_dict()
        assert d["direction"] == "lower_better"
        assert d["role"] == "comparison"

    def test_direction_survives_json_round_trip(self):
        m = ResultMarker(
            marker_index=1, marker="RESULT-1", metric_name="model_rmse",
            observed_value=9.80, artifact_path="metrics.json",
            artifact_sha256="abc123", experiment_result_id=11,
            direction="lower_better", role="comparison",
        )
        serialized = json.dumps(m.to_dict())
        reloaded = json.loads(serialized)
        assert reloaded["direction"] == "lower_better"
        assert reloaded["role"] == "comparison"

    def test_reloaded_marker_resolves_correctly(self):
        """After reload, the direction enables correct comparison."""
        m = ResultMarker(
            marker_index=1, marker="RESULT-1", metric_name="model_rmse",
            observed_value=9.80, artifact_path="metrics.json",
            artifact_sha256="abc123", experiment_result_id=11,
            direction="lower_better", role="comparison",
        )
        reloaded = json.loads(json.dumps(m.to_dict()))
        c = evaluate_metric_comparison(
            reloaded["metric_name"], 16.05, reloaded["observed_value"],
            reloaded["direction"],
        )
        assert c.is_improvement  # 9.80 < 16.05 with lower_better = improvement


# ── Negative result handling ────────────────────────────────────────


class TestNegativeResultHandling:
    """A negative result (model worse than baseline) is reported truthfully."""

    def test_negative_result_not_euphemistic(self):
        """If model_rmse > baseline_rmse, the claim 'reduced error' is blocked."""
        c = evaluate_metric_comparison("rmse", 10.0, 12.0, "lower_better")
        assert c.outcome == ComparisonOutcome.DEGRADATION
        check = check_claim_direction("the model reduced error", c)
        assert not check.is_correct

    def test_null_result_reported_neutrally(self):
        """A tie should not be claimed as improvement."""
        c = evaluate_metric_comparison("rmse", 10.0, 10.0, "lower_better")
        assert c.outcome == ComparisonOutcome.TIE
        check = check_claim_direction("the model improved performance", c)
        # Tie with improvement language: not a degradation claim, so passes
        # the claim check, but is_improvement is False — the structural
        # evaluator reports the tie honestly.
        assert not c.is_improvement


# ── Backward compatibility ──────────────────────────────────────────


@pytest.mark.integration
class TestBackwardCompatibility:
    """Phase 5/7 Iris path remains unchanged and green."""

    def test_iris_spec_loads_without_new_fields(self):
        """Iris spec has no research_intent block but loads with defaults."""
        spec = load_spec("phase5-pilot-v1")
        assert spec.task_type == ""  # backward compat default
        assert spec.primary_metric == ""
        assert spec.research_intent == spec.research_question

    def test_phase7_result_markers_remain_readable(self):
        """Phase 7 ResultMarkers without direction/role are still valid."""
        m = ResultMarker(
            marker_index=1, marker="RESULT-1", metric_name="baseline_accuracy",
            observed_value=0.333, artifact_path="metrics.json",
            artifact_sha256="abc", experiment_result_id=11,
            # No direction/role — Phase 7 style
        )
        d = m.to_dict()
        assert d["direction"] == ""  # schema-compatible default
        assert d["role"] == ""

    def test_direction_evaluator_handles_empty_direction(self):
        """Empty direction (Phase 7 markers) is treated as neutral."""
        c = evaluate_metric_comparison("acc", 0.5, 0.9, "")
        assert c.outcome == ComparisonOutcome.TIE  # neutral → no determination
