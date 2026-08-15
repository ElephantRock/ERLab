"""EAD-2: Checked-in empirical capability tests.

Tests the v1 calibration/selective-classification entrypoint against
real registered datasets (iris, wine_quality) and verifies it rejects
regression datasets (concrete_strength). Also tests determinism and
the EAD-1 → EAD-2 binding (SpecDesigner with the production capability).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ENTRYPOINT = REPO_ROOT / "experiments" / "tabular_calibration_selective_v1" / "analysis.py"
IRIS_CSV = REPO_ROOT / "data" / "datasets" / "iris" / "iris_raw.csv"
WINE_CSV = REPO_ROOT / "data" / "datasets" / "wine_quality" / "wine_processed.csv"
CONCRETE_CSV = REPO_ROOT / "data" / "datasets" / "concrete_strength" / "concrete_raw.csv"


def _run_entrypoint(input_csv: Path, output_dir: Path) -> tuple[int, dict | None]:
    """Run the entrypoint and return (exit_code, metrics_dict or None)."""
    result = subprocess.run(
        [sys.executable, str(ENTRYPOINT),
         "--input", str(input_csv),
         "--output", str(output_dir)],
        capture_output=True, text=True, timeout=300,
    )
    metrics_path = output_dir / "metrics.json"
    metrics = None
    if metrics_path.exists():
        with open(metrics_path) as f:
            metrics = json.load(f)
    return result.returncode, metrics


# ── Execution tests ─────────────────────────────────────────────────────────


class TestEntrypointExecution:
    def test_iris_executes_successfully(self, tmp_path):
        rc, metrics = _run_entrypoint(IRIS_CSV, tmp_path)
        assert rc == 0, f"Iris execution failed with exit {rc}"
        assert metrics is not None
        assert "metrics" in metrics
        assert "baseline_accuracy" in metrics["metrics"]

    def test_wine_executes_successfully(self, tmp_path):
        rc, metrics = _run_entrypoint(WINE_CSV, tmp_path)
        assert rc == 0, f"Wine execution failed with exit {rc}"
        assert metrics is not None
        assert "baseline_accuracy" in metrics["metrics"]

    def test_concrete_rejected_as_regression(self, tmp_path):
        rc, _ = _run_entrypoint(CONCRETE_CSV, tmp_path)
        assert rc != 0, "Concrete should be rejected as regression"

    def test_all_metrics_finite(self, tmp_path):
        import math
        rc, metrics = _run_entrypoint(IRIS_CSV, tmp_path)
        assert rc == 0
        for name, val in metrics["metrics"].items():
            assert isinstance(val, (int, float)), f"{name} not numeric"
            assert math.isfinite(val), f"{name} not finite: {val}"

    def test_all_conditions_represented(self, tmp_path):
        rc, metrics = _run_entrypoint(IRIS_CSV, tmp_path)
        assert rc == 0
        severities = [0.0, 0.25, 0.5, 0.75]
        cal_methods = ["uncalibrated", "sigmoid", "isotonic"]
        for sev in severities:
            for method in cal_methods:
                sev_label = str(sev).replace(".", "_")
                key = f"{sev_label}_{method}_accuracy"
                assert key in metrics["metrics"], f"missing {key}"

    def test_all_calibration_conditions_present(self, tmp_path):
        rc, metrics = _run_entrypoint(WINE_CSV, tmp_path)
        assert rc == 0
        # 4 severities × 3 methods × 3 metrics + baseline = 37
        assert len(metrics["metrics"]) == 37

    def test_no_synthetic_data_substituted(self, tmp_path):
        """Metrics must reflect the real registered dataset, not synthetic."""
        rc, metrics = _run_entrypoint(IRIS_CSV, tmp_path)
        assert rc == 0
        # Iris baseline accuracy should be ~0.333 (3-class majority)
        baseline = metrics["metrics"]["baseline_accuracy"]
        assert abs(baseline - 0.333333) < 0.01, (
            f"Iris baseline should be ~1/3, got {baseline}"
        )

    def test_artifacts_written(self, tmp_path):
        rc, _ = _run_entrypoint(IRIS_CSV, tmp_path)
        assert rc == 0
        assert (tmp_path / "metrics.json").exists()
        assert (tmp_path / "condition_metrics.json").exists()
        assert (tmp_path / "predictions.csv").exists()


# ── Determinism tests ──────────────────────────────────────────────────────


class TestDeterminism:
    def test_repeated_execution_identical_metrics(self, tmp_path):
        dir1 = tmp_path / "run1"
        dir2 = tmp_path / "run2"
        dir1.mkdir()
        dir2.mkdir()
        rc1, m1 = _run_entrypoint(IRIS_CSV, dir1)
        rc2, m2 = _run_entrypoint(IRIS_CSV, dir2)
        assert rc1 == 0 and rc2 == 0
        assert m1["metrics"] == m2["metrics"], (
            "Repeated execution must produce identical metrics"
        )

    def test_wine_deterministic(self, tmp_path):
        dir1 = tmp_path / "w1"
        dir2 = tmp_path / "w2"
        dir1.mkdir()
        dir2.mkdir()
        rc1, m1 = _run_entrypoint(WINE_CSV, dir1)
        rc2, m2 = _run_entrypoint(WINE_CSV, dir2)
        assert rc1 == 0 and rc2 == 0
        assert m1["metrics"] == m2["metrics"]


# ── EAD-1 → EAD-2 binding ──────────────────────────────────────────────────


class TestEad1Ead2Binding:
    def test_designer_produces_specs_for_production_capability(self):
        """SpecDesigner with the v1 capability → 2 valid specs."""
        from backend.pipeline.experiment.spec_designer import (
            TABULAR_CALIBRATION_SELECTIVE_V1,
            IdeaInputs,
            SpecDesigner,
        )

        idea = IdeaInputs(
            requested_metrics=["baseline_accuracy", "0_0_uncalibrated_accuracy"],
        )
        result = SpecDesigner().design(
            research_question=(
                "How does post-hoc probability calibration affect"
                " selective classification performance under"
                " covariate shift?"
            ),
            idea=idea,
            capability=TABULAR_CALIBRATION_SELECTIVE_V1,
            min_datasets=2,
        )
        assert result.status == "success"
        assert len(result.specs) == 2

        dataset_names = {s.dataset_name for s in result.specs}
        assert dataset_names == {"iris", "wine_quality"}

        for spec in result.specs:
            assert spec.analysis_entrypoint == (
                "experiments/tabular_calibration_selective_v1/analysis.py"
            )
            assert spec.comparison_method == "logistic_regression"
            assert spec.baseline_method == "majority_class"
            assert "baseline_accuracy" in spec.declared_metrics

    def test_production_specs_pass_parse_validation(self):
        """Round-trip: designer output → serialize → _parse_spec → match."""
        from backend.pipeline.experiment.spec_designer import (
            TABULAR_CALIBRATION_SELECTIVE_V1,
            IdeaInputs,
            SpecDesigner,
        )
        from backend.pipeline.experiment.specification import _parse_spec

        result = SpecDesigner().design(
            research_question="test",
            idea=IdeaInputs(requested_metrics=["baseline_accuracy"]),
            capability=TABULAR_CALIBRATION_SELECTIVE_V1,
        )
        assert result.status == "success"
        for spec in result.specs:
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
            assert re_spec.dataset_name == spec.dataset_name
