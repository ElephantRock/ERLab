"""EAD-0: Spec validation hardening regression tests.

Verifies that _parse_spec raises SpecValidationError (not bare KeyError)
on malformed specs, and that all existing valid specs still load correctly.
"""

from __future__ import annotations

import pytest

from backend.pipeline.experiment.specification import (
    ExperimentSpec,
    SpecValidationError,
    _parse_spec,
    list_specs,
    load_spec,
)


def _valid_raw():
    """Return a minimal valid raw spec dict."""
    return {
        "experiment_spec_id": "test-v1",
        "description": "test",
        "dataset": {
            "name": "iris",
            "version": "1.0",
            "raw_filename": "iris.csv",
            "raw_sha256": "abc123",
        },
        "split": {
            "method": "stratified",
            "train_fraction": 0.8,
            "test_fraction": 0.2,
            "random_seed": 42,
        },
        "analysis": {
            "entrypoint": "experiments/test/analysis.py",
            "method": "logistic regression",
            "declared_metrics": ["accuracy"],
        },
        "metrics": {"accuracy": {"direction": "higher_better"}},
    }


# ── Valid spec loads ────────────────────────────────────────────────────────


def test_valid_spec_loads():
    spec = _parse_spec(_valid_raw())
    assert spec.spec_id == "test-v1"
    assert spec.dataset_name == "iris"
    assert spec.train_fraction == 0.8
    assert spec.declared_metrics == ["accuracy"]


def test_all_existing_specs_load():
    specs = list_specs()
    assert len(specs) >= 4
    for s in specs:
        assert isinstance(s, ExperimentSpec)
        assert s.spec_id
        assert s.dataset_name


def test_load_spec_by_id():
    spec = load_spec("phase5-pilot-v1")
    assert spec.dataset_name == "iris"
    assert "baseline_accuracy" in spec.declared_metrics


# ── Missing required fields ─────────────────────────────────────────────────


def test_missing_top_level_id():
    raw = _valid_raw()
    del raw["experiment_spec_id"]
    with pytest.raises(SpecValidationError, match="experiment_spec_id"):
        _parse_spec(raw)


def test_missing_dataset_section():
    raw = _valid_raw()
    del raw["dataset"]
    with pytest.raises(SpecValidationError, match="dataset"):
        _parse_spec(raw)


def test_missing_split_section():
    raw = _valid_raw()
    del raw["split"]
    with pytest.raises(SpecValidationError, match="split"):
        _parse_spec(raw)


def test_missing_analysis_section():
    raw = _valid_raw()
    del raw["analysis"]
    with pytest.raises(SpecValidationError, match="analysis"):
        _parse_spec(raw)


def test_missing_nested_field():
    raw = _valid_raw()
    del raw["dataset"]["name"]
    with pytest.raises(SpecValidationError, match="name.*dataset"):
        _parse_spec(raw)


def test_missing_declared_metrics():
    raw = _valid_raw()
    del raw["analysis"]["declared_metrics"]
    with pytest.raises(SpecValidationError, match="declared_metrics"):
        _parse_spec(raw)


# ── Type errors ─────────────────────────────────────────────────────────────


def test_non_dict_top_level():
    with pytest.raises(SpecValidationError, match="JSON object"):
        _parse_spec("not a dict")  # type: ignore[arg-type]


def test_dataset_not_dict():
    raw = _valid_raw()
    raw["dataset"] = "not a dict"
    with pytest.raises(SpecValidationError, match="dataset.*JSON object"):
        _parse_spec(raw)


def test_train_fraction_not_number():
    raw = _valid_raw()
    raw["split"]["train_fraction"] = "0.8"
    with pytest.raises(SpecValidationError, match="train_fraction.*number"):
        _parse_spec(raw)


def test_declared_metrics_not_list():
    raw = _valid_raw()
    raw["analysis"]["declared_metrics"] = "accuracy"
    with pytest.raises(SpecValidationError, match="declared_metrics.*list"):
        _parse_spec(raw)


def test_declared_metric_item_not_string():
    raw = _valid_raw()
    raw["analysis"]["declared_metrics"] = [42]
    with pytest.raises(SpecValidationError, match="declared_metrics"):
        _parse_spec(raw)


# ── Range errors ────────────────────────────────────────────────────────────


def test_train_fraction_above_one():
    raw = _valid_raw()
    raw["split"]["train_fraction"] = 1.5
    with pytest.raises(SpecValidationError, match="train_fraction.*<= 1.0"):
        _parse_spec(raw)


def test_train_fraction_negative():
    raw = _valid_raw()
    raw["split"]["train_fraction"] = -0.1
    with pytest.raises(SpecValidationError, match="train_fraction.*>= 0"):
        _parse_spec(raw)


def test_random_seed_negative():
    raw = _valid_raw()
    raw["split"]["random_seed"] = -1
    with pytest.raises(SpecValidationError, match="random_seed.*>= 0"):
        _parse_spec(raw)


def test_empty_declared_metrics():
    raw = _valid_raw()
    raw["analysis"]["declared_metrics"] = []
    with pytest.raises(SpecValidationError, match="declared_metrics.*at least"):
        _parse_spec(raw)


# ── Optional fields validation ──────────────────────────────────────────────


def test_research_intent_not_dict():
    raw = _valid_raw()
    raw["research_intent"] = "not a dict"
    with pytest.raises(SpecValidationError, match="research_intent.*JSON"):
        _parse_spec(raw)


def test_metrics_not_dict():
    raw = _valid_raw()
    raw["metrics"] = "not a dict"
    with pytest.raises(SpecValidationError, match="metrics.*JSON"):
        _parse_spec(raw)


def test_metric_without_direction():
    raw = _valid_raw()
    raw["metrics"] = {"accuracy": {"wrong_key": "value"}}
    with pytest.raises(SpecValidationError, match="direction"):
        _parse_spec(raw)


# ── Backward compatibility ──────────────────────────────────────────────────


def test_spec_without_optional_fields():
    """Minimal spec with only required fields loads with defaults."""
    raw = _valid_raw()
    # Remove optional fields to test defaults
    raw.pop("description", None)
    raw.pop("metrics", None)
    raw.pop("tolerances", None)
    raw.pop("output_artifacts", None)
    spec = _parse_spec(raw)
    assert spec.description == ""
    assert spec.metric_directions == {}
    assert spec.tolerances == {}
    assert spec.task_type == ""
