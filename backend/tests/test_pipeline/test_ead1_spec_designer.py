"""EAD-1: Spec designer tests.

Tests the deterministic compilation from research idea + registered
datasets + supported capability → validated ExperimentSpec objects.

Positive proofs: design succeeds with ≥2 compatible datasets.
Negative proofs: insufficient datasets, wrong task, unsupported metrics,
malformed metadata, hash mismatch — all fail closed with diagnostics.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.pipeline.experiment.dataset_registry import (
    list_registered_datasets,
    load_dataset_metadata,
)
from backend.pipeline.experiment.spec_designer import (
    IdeaInputs,
    SpecDesigner,
    SupportedCapability,
)
from backend.pipeline.experiment.specification import (
    ExperimentSpec,
)

# ── Fixture capability for Case 1 ────────────────────────────────────────────

CALIBRATION_CAPABILITY = SupportedCapability(
    task_type="classification",
    supported_metrics={
        "accuracy": "higher_better",
        "baseline_accuracy": "higher_better",
        "model_accuracy": "higher_better",
    },
    baseline_method="majority_class",
    comparison_method="logistic_regression",
    analysis_entrypoint="experiments/calibration_selective/analysis.py",
    analysis_method_description=(
        "logistic regression with post-hoc temperature scaling"
        " vs majority-class baseline"
    ),
    model_family="logistic_regression",
    allowed_hyperparameters={"calibration_method": "temperature_scaling"},
)

REGRESSION_CAPABILITY = SupportedCapability(
    task_type="regression",
    supported_metrics={"rmse": "lower_better", "r2": "higher_better"},
    baseline_method="training_mean",
    comparison_method="linear_regression",
    analysis_entrypoint="experiments/regression_baseline/analysis.py",
    analysis_method_description="linear regression vs training mean",
)

FROZEN_QUESTION = (
    "How does post-hoc probability calibration affect selective"
    " classification performance under covariate shift in tabular"
    " classification?"
)


# ── Dataset metadata reader tests ────────────────────────────────────────────


class TestDatasetMetadata:
    def test_iris_is_classification(self):
        meta = load_dataset_metadata("iris")
        assert meta.is_classification
        assert meta.target == "species"
        assert len(meta.classes) == 3

    def test_wine_is_classification(self):
        meta = load_dataset_metadata("wine_quality")
        assert meta.is_classification

    def test_concrete_is_regression(self):
        meta = load_dataset_metadata("concrete_strength")
        assert not meta.is_classification
        assert meta.task_type == "regression"

    def test_nonexistent_dataset_raises(self):
        with pytest.raises(FileNotFoundError):
            load_dataset_metadata("nonexistent_dataset")

    def test_list_registered_datasets(self):
        names = list_registered_datasets()
        assert "iris" in names
        assert "wine_quality" in names
        assert "concrete_strength" in names


# ── Positive design proofs ──────────────────────────────────────────────────


class TestSpecDesignSuccess:
    def test_designs_specs_for_two_classification_datasets(self):
        """Case 1: iris + wine_quality → 2 specs."""
        idea = IdeaInputs(
            proposed_method="temperature scaling after logistic regression",
            evaluation_approach="accuracy and calibration metrics",
            requested_metrics=["accuracy", "baseline_accuracy", "model_accuracy"],
        )
        designer = SpecDesigner()
        result = designer.design(
            research_question=FROZEN_QUESTION,
            idea=idea,
            capability=CALIBRATION_CAPABILITY,
            min_datasets=2,
        )
        assert result.status == "success"
        assert len(result.specs) >= 2
        for spec in result.specs:
            assert isinstance(spec, ExperimentSpec)
            assert spec.task_type == "classification"
            assert spec.analysis_entrypoint == CALIBRATION_CAPABILITY.analysis_entrypoint

    def test_specs_have_governed_identity(self):
        """Each spec has spec_id, declared_metrics, research_question."""
        idea = IdeaInputs(
            requested_metrics=["accuracy"],
        )
        result = SpecDesigner().design(
            research_question=FROZEN_QUESTION,
            idea=idea,
            capability=CALIBRATION_CAPABILITY,
        )
        assert result.status == "success"
        for spec in result.specs:
            assert spec.spec_id.startswith("auto-classification-")
            assert "accuracy" in spec.declared_metrics
            assert spec.research_question == FROZEN_QUESTION

    def test_specs_pass_parse_validation(self):
        """All designer output passes _parse_spec when re-serialized."""
        from backend.pipeline.experiment.specification import _parse_spec

        result = SpecDesigner().design(
            research_question=FROZEN_QUESTION,
            idea=IdeaInputs(requested_metrics=["accuracy"]),
            capability=CALIBRATION_CAPABILITY,
        )
        assert result.status == "success"
        for spec in result.specs:
            # Re-serialize and re-parse — must survive round-trip.
            raw = {
                "experiment_spec_id": spec.spec_id,
                "description": spec.description,
                "dataset": {
                    "name": spec.dataset_name,
                    "version": spec.dataset_version,
                    "raw_filename": spec.dataset_raw_filename,
                    "raw_sha256": spec.dataset_raw_sha256,
                },
                "split": {
                    "method": spec.split_method,
                    "train_fraction": spec.train_fraction,
                    "test_fraction": spec.test_fraction,
                    "random_seed": spec.random_seed,
                },
                "analysis": {
                    "entrypoint": spec.analysis_entrypoint,
                    "method": spec.analysis_method,
                    "declared_metrics": spec.declared_metrics,
                },
                "metrics": {
                    k: {"direction": v}
                    for k, v in spec.metric_directions.items()
                },
                "research_intent": {
                    "task_type": spec.task_type,
                    "target_name": spec.target_name,
                    "baseline_method": spec.baseline_method,
                    "comparison_method": spec.comparison_method,
                    "primary_metric": spec.primary_metric,
                },
            }
            re_spec = _parse_spec(raw)
            assert re_spec.spec_id == spec.spec_id


# ── Negative proofs ─────────────────────────────────────────────────────────


class TestSpecDesignFailures:
    def test_insufficient_datasets_for_regression(self):
        """Two regression datasets exist (concrete, airfoil). Need 3 →
        fail. (C3-2 registered airfoil; the pre-C3 world had only
        concrete, and this test demanded min_datasets=2.)"""
        idea = IdeaInputs(requested_metrics=["rmse"])
        result = SpecDesigner().design(
            research_question="regression question",
            idea=idea,
            capability=REGRESSION_CAPABILITY,
            min_datasets=3,
        )
        assert result.status == "insufficient_compatible_datasets"
        assert len(result.specs) == 0
        assert any("2 compatible" in d for d in result.diagnostics)

    def test_unsupported_metric_rejected(self):
        """Idea requests metrics not in capability → fail."""
        idea = IdeaInputs(requested_metrics=["f1_score", "auc_roc"])
        result = SpecDesigner().design(
            research_question=FROZEN_QUESTION,
            idea=idea,
            capability=CALIBRATION_CAPABILITY,
        )
        assert result.status == "unsupported_metric"
        assert len(result.specs) == 0

    def test_empty_metric_request_fails(self):
        """No requested metrics → fail (can't pick from empty set)."""
        idea = IdeaInputs(requested_metrics=[])
        result = SpecDesigner().design(
            research_question=FROZEN_QUESTION,
            idea=idea,
            capability=CALIBRATION_CAPABILITY,
        )
        assert result.status == "unsupported_metric"

    def test_unsupported_requested_metric_ignored_with_diag(self):
        """Unknown metrics are ignored, not fatal, if some match."""
        idea = IdeaInputs(
            requested_metrics=["accuracy", "f1_score", "auc"],
        )
        result = SpecDesigner().design(
            research_question=FROZEN_QUESTION,
            idea=idea,
            capability=CALIBRATION_CAPABILITY,
        )
        assert result.status == "success"
        assert "accuracy" in result.specs[0].declared_metrics
        assert "f1_score" not in result.specs[0].declared_metrics

    def test_min_datasets_one_succeeds_for_regression(self):
        """With min_datasets=1, design succeeds and compiles every
        compatible regression dataset (concrete + airfoil since
        C3-2)."""
        idea = IdeaInputs(requested_metrics=["rmse"])
        result = SpecDesigner().design(
            research_question="regression",
            idea=idea,
            capability=REGRESSION_CAPABILITY,
            min_datasets=1,
        )
        assert result.status == "success"
        assert len(result.specs) == 2

    def test_diagnostics_explain_incompatibility(self):
        """Concrete is excluded from classification design with reason."""
        idea = IdeaInputs(requested_metrics=["accuracy"])
        result = SpecDesigner().design(
            research_question=FROZEN_QUESTION,
            idea=idea,
            capability=CALIBRATION_CAPABILITY,
        )
        assert result.status == "success"
        concrete_diag = [
            d for d in result.diagnostics if "concrete" in d.lower()
        ]
        assert len(concrete_diag) >= 1
        assert "regression" in concrete_diag[0].lower()


# ── Capability isolation tests ──────────────────────────────────────────────


class TestCapabilityContract:
    def test_specs_use_only_capability_fields(self):
        """Spec fields come from the capability, not from free text."""
        idea = IdeaInputs(
            proposed_method="some arbitrary custom method name",
            evaluation_approach="custom novel metric",
            requested_metrics=["accuracy"],
        )
        result = SpecDesigner().design(
            research_question=FROZEN_QUESTION,
            idea=idea,
            capability=CALIBRATION_CAPABILITY,
        )
        assert result.status == "success"
        for spec in result.specs:
            assert spec.comparison_method == "logistic_regression"
            assert spec.baseline_method == "majority_class"
            assert spec.analysis_entrypoint == (
                CALIBRATION_CAPABILITY.analysis_entrypoint
            )

    def test_capability_hyperparameters_in_spec(self):
        result = SpecDesigner().design(
            research_question=FROZEN_QUESTION,
            idea=IdeaInputs(requested_metrics=["accuracy"]),
            capability=CALIBRATION_CAPABILITY,
        )
        assert result.status == "success"
        for spec in result.specs:
            assert "calibration_method" in spec.hyperparameters
