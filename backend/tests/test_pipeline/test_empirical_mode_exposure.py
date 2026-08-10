"""Empirical-mode exposure contract: registry read + estimate wiring."""

import json
from pathlib import Path

import pytest

from backend.api.routes.experiments import list_experiment_specs
from backend.pipeline.experiment import specification
from backend.pipeline.experiment.specification import list_specs
from backend.pipeline.monitoring.cost_estimator import estimate_run_cost


def _write_spec(base: Path, spec_id: str, *, dataset: str = "iris") -> None:
    target = base / dataset
    target.mkdir(parents=True, exist_ok=True)
    safe_id = spec_id.replace("-", "_")
    (target / f"spec_{safe_id}.json").write_text(
        json.dumps(
            {
                "experiment_spec_id": spec_id,
                "description": f"Registered {spec_id}",
                "dataset": {
                    "name": dataset,
                    "version": "1",
                    "raw_filename": "data.csv",
                    "raw_sha256": "abc123",
                },
                "split": {
                    "method": "stratified",
                    "train_fraction": 0.8,
                    "test_fraction": 0.2,
                    "random_seed": 42,
                },
                "analysis": {
                    "entrypoint": "analysis.py",
                    "method": "logistic_regression",
                    "declared_metrics": ["balanced_accuracy"],
                },
                "metrics": {"balanced_accuracy": {"direction": "higher_is_better"}},
                "research_question": "Does logistic regression classify Iris species?",
                "research_intent": {
                    "task_type": "classification",
                    "target_name": "species",
                    "baseline_method": "majority_class",
                    "comparison_method": "logistic_regression",
                    "primary_metric": "balanced_accuracy",
                },
            }
        ),
        encoding="utf-8",
    )


def test_list_specs_uses_registered_files_and_sorts_by_id(tmp_path):
    _write_spec(tmp_path, "z-spec")
    _write_spec(tmp_path, "a-spec", dataset="wine")

    specs = list_specs(tmp_path)

    assert [spec.spec_id for spec in specs] == ["a-spec", "z-spec"]
    assert specs[0].analysis_method == "logistic_regression"
    assert specs[0].primary_metric == "balanced_accuracy"


@pytest.mark.anyio
async def test_specs_endpoint_returns_selector_summary_and_yaml_compatible_strategies(tmp_path, monkeypatch):
    _write_spec(tmp_path, "phase5-pilot-v1")
    monkeypatch.setattr(specification, "_SPECS_DIR", tmp_path)
    specification._SPECS.clear()

    payload = await list_experiment_specs()

    assert payload["compatible_strategies"] == ["academic_proposal", "deep_research"]
    assert payload["specs"] == [
        {
            "spec_id": "phase5-pilot-v1",
            "description": "Registered phase5-pilot-v1",
            "research_question": "Does logistic regression classify Iris species?",
            "dataset_name": "iris",
            "analysis_method": "logistic_regression",
            "primary_metric": "balanced_accuracy",
        }
    ]


def test_pipeline_estimate_adds_experiment_only_when_requested():
    ordinary = estimate_run_cost("deep_research", include_experiment=False)
    empirical = estimate_run_cost("deep_research", include_experiment=True)

    ordinary_stages = [row["stage"] for row in ordinary.breakdown]
    empirical_stages = [row["stage"] for row in empirical.breakdown]

    assert "experiment_execution" not in ordinary_stages
    assert "experiment_execution" in empirical_stages
    assert empirical.stages == ordinary.stages + 1


def test_incompatible_strategy_does_not_gain_experiment_stage_in_estimate():
    quick = estimate_run_cost("fast_scan", include_experiment=True)
    review = estimate_run_cost("literature_review", include_experiment=True)

    assert "experiment_execution" not in [row["stage"] for row in quick.breakdown]
    assert "experiment_execution" not in [row["stage"] for row in review.breakdown]
