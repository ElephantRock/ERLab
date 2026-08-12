"""EAD-3a: Direct ExperimentSpec execution path tests.

Verifies that ``execute_experiment_spec(spec, ...)`` produces identical
results to ``execute_experiment(spec_id, ...)`` for the same registered
spec, and that an in-memory (non-registered) spec can execute directly
without requiring a file in ``data/datasets/``.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from backend.pipeline.experiment.empirical_runner import (
    execute_experiment,
    execute_experiment_spec,
)
from backend.pipeline.experiment.specification import (
    ExperimentSpec,
    load_spec,
)


def _run(coro):
    return asyncio.run(coro)


# ── Legacy equivalence ─────────────────────────────────────────────────────


class TestLegacyEquivalence:
    def test_legacy_path_still_works(self, tmp_path):
        """execute_experiment(spec_id) → load_spec → execute."""
        manifest, stdout, stderr, exit_code, elapsed = _run(
            execute_experiment("phase5-pilot-v1", tmp_path, 120.0)
        )
        assert exit_code == 0
        assert manifest.status == "succeeded"
        assert "baseline_accuracy" in manifest.results
        assert "model_accuracy" in manifest.results

    def test_direct_spec_path_works(self, tmp_path):
        """execute_experiment_spec(spec) → direct execution."""
        spec = load_spec("phase5-pilot-v1")
        manifest, _, _, exit_code, _ = _run(
            execute_experiment_spec(spec, tmp_path, 120.0)
        )
        assert exit_code == 0
        assert manifest.status == "succeeded"

    def test_results_are_identical(self, tmp_path):
        """Legacy and direct paths must produce the same metrics."""
        dir1 = tmp_path / "legacy"
        dir2 = tmp_path / "direct"

        spec = load_spec("phase5-pilot-v1")
        m1, _, _, _, _ = _run(execute_experiment("phase5-pilot-v1", dir1, 120.0))
        m2, _, _, _, _ = _run(execute_experiment_spec(spec, dir2, 120.0))

        assert m1.results == m2.results, (
            "Legacy and direct paths must produce identical results"
        )
        assert m1.dataset.name == m2.dataset.name
        assert m1.analysis.entrypoint == m2.analysis.entrypoint
        assert m1.experiment_spec_id == m2.experiment_spec_id

    def test_manifest_contract_unchanged(self, tmp_path):
        """Manifest schema fields are the same in both paths."""
        dir1 = tmp_path / "legacy"
        dir2 = tmp_path / "direct"

        spec = load_spec("phase5-pilot-v1")
        m1, _, _, _, _ = _run(execute_experiment("phase5-pilot-v1", dir1, 120.0))
        m2, _, _, _, _ = _run(execute_experiment_spec(spec, dir2, 120.0))

        assert m1.schema_version == m2.schema_version
        assert m1.split.method == m2.split.method
        assert m1.split.train_fraction == m2.split.train_fraction
        assert m1.environment.python_version == m2.environment.python_version


# ── Non-registered spec execution ──────────────────────────────────────────


class TestNonRegisteredSpecExecution:
    def test_in_memory_spec_executes_without_registration(self, tmp_path):
        """An ExperimentSpec built in memory (not registered in
        data/datasets/) must execute through execute_experiment_spec
        without needing load_spec().
        """
        # Load the spec, then "unregister" it by building a new object
        # with the same fields. This proves no file lookup occurs.
        original = load_spec("phase5-pilot-v1")
        spec = ExperimentSpec(
            spec_id=original.spec_id,
            description=original.description,
            dataset_name=original.dataset_name,
            dataset_version=original.dataset_version,
            dataset_raw_filename=original.dataset_raw_filename,
            dataset_raw_sha256=original.dataset_raw_sha256,
            split_method=original.split_method,
            train_fraction=original.train_fraction,
            test_fraction=original.test_fraction,
            random_seed=original.random_seed,
            analysis_entrypoint=original.analysis_entrypoint,
            analysis_method=original.analysis_method,
            declared_metrics=original.declared_metrics,
            metric_directions=original.metric_directions,
            tolerances=original.tolerances,
            output_artifacts=original.output_artifacts,
            research_question=original.research_question,
            task_type=original.task_type,
            target_name=original.target_name,
            baseline_method=original.baseline_method,
            comparison_method=original.comparison_method,
            primary_metric=original.primary_metric,
            model_family=original.model_family,
            hyperparameters=original.hyperparameters,
        )

        manifest, _, _, exit_code, _ = _run(
            execute_experiment_spec(spec, tmp_path, 120.0)
        )
        assert exit_code == 0
        assert manifest.status == "succeeded"
        assert "baseline_accuracy" in manifest.results

    def test_designer_output_spec_executes(self, tmp_path):
        """A spec produced by SpecDesigner (never registered in
        data/datasets/) must execute through execute_experiment_spec.
        """
        from backend.pipeline.experiment.spec_designer import (
            TABULAR_CALIBRATION_SELECTIVE_V1,
            IdeaInputs,
            SpecDesigner,
        )

        result = SpecDesigner().design(
            research_question="test",
            idea=IdeaInputs(requested_metrics=["baseline_accuracy"]),
            capability=TABULAR_CALIBRATION_SELECTIVE_V1,
            min_datasets=1,
        )
        assert result.status == "success"
        assert len(result.specs) >= 1

        # Take the first spec (iris) and execute it directly
        spec = result.specs[0]
        manifest, _, _, exit_code, _ = _run(
            execute_experiment_spec(spec, tmp_path, 300.0)
        )
        assert exit_code == 0
        assert manifest.status == "succeeded"
        assert "baseline_accuracy" in manifest.results
