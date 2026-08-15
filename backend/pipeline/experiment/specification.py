"""Phase 5 — experiment specification loader.

A checked-in JSON file defining what is permitted to execute for a given
experiment spec. The runner receives the specification and a read-only dataset
path. It must not accept arbitrary file paths produced by the model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


class SpecValidationError(ValueError):
    """Raised when an experiment spec fails structural validation."""


@dataclass
class ExperimentSpec:
    """A registered experiment specification (checked-in JSON)."""

    spec_id: str
    description: str
    dataset_name: str
    dataset_version: str
    dataset_raw_filename: str
    dataset_raw_sha256: str
    split_method: str
    train_fraction: float
    test_fraction: float
    random_seed: int
    analysis_entrypoint: str
    analysis_method: str
    declared_metrics: list[str]
    metric_directions: dict[str, str]
    tolerances: dict[str, float]
    output_artifacts: list[str]
    research_question: str
    # Phase 8 / D2: structured research intent — the durable source of truth
    # for scope alignment. Every empirical spec must declare these so the
    # recovery and scope gates load a durable value, never infer from dataset
    # name or paper title.
    task_type: str = ""           # classification | regression | ...
    target_name: str = ""         # the prediction target
    baseline_method: str = ""     # declared baseline approach
    comparison_method: str = ""   # declared comparison model
    primary_metric: str = ""      # the single primary evaluation metric
    # Phase 14: nonlinear method identity
    model_family: str = ""        # e.g. "random_forest", "logistic_regression"
    hyperparameters: dict = field(default_factory=dict)  # frozen hyperparameters

    @property
    def research_intent(self) -> str:
        """The durable research question used by scope gates and recovery.

        Falls back to ``research_question`` for backward compatibility with
        Phase 5/7 specs that don't declare the structured fields.
        """
        return self.research_question

    def to_dict(self) -> dict:
        return {
            "experiment_spec_id": self.spec_id,
            "description": self.description,
            "dataset": {
                "name": self.dataset_name,
                "version": self.dataset_version,
                "raw_filename": self.dataset_raw_filename,
                "raw_sha256": self.dataset_raw_sha256,
            },
            "split": {
                "method": self.split_method,
                "train_fraction": self.train_fraction,
                "test_fraction": self.test_fraction,
                "random_seed": self.random_seed,
            },
            "analysis": {
                "entrypoint": self.analysis_entrypoint,
                "method": self.analysis_method,
                "declared_metrics": self.declared_metrics,
            },
            "metrics": {k: {"direction": v} for k, v in self.metric_directions.items()},
            "tolerances": self.tolerances,
            "output_artifacts": self.output_artifacts,
            "research_question": self.research_question,
            "research_intent": {
                "task_type": self.task_type,
                "target_name": self.target_name,
                "baseline_method": self.baseline_method,
                "comparison_method": self.comparison_method,
                "primary_metric": self.primary_metric,
            },
        }


_SPECS_DIR = Path(__file__).resolve().parents[3] / "data" / "datasets"
_SPECS: dict[str, ExperimentSpec] = {}


def list_specs(specs_dir: Path | None = None) -> list[ExperimentSpec]:
    """List registered experiment specifications in deterministic ID order.

    Registration remains file-based: any ``spec_*.json`` under the checked-in
    datasets directory is a selectable specification. The same parser used by
    ``load_spec`` validates each file so the API never invents a second schema.
    """
    base = specs_dir or _SPECS_DIR
    specs: dict[str, ExperimentSpec] = {}
    if not base.exists():
        return []

    for spec_file in sorted(base.rglob("spec_*.json")):
        with open(spec_file) as f:
            spec = _parse_spec(json.load(f))
        specs[spec.spec_id] = spec
        _SPECS[spec.spec_id] = spec

    return [specs[spec_id] for spec_id in sorted(specs)]


def load_spec(spec_id: str, specs_dir: Path | None = None) -> ExperimentSpec:
    """Load a registered experiment specification by ID."""
    if spec_id in _SPECS:
        return _SPECS[spec_id]
    base = specs_dir or _SPECS_DIR
    # Search all subdirectories for the spec file (handle dash/underscore variants)
    safe_id = spec_id.replace("-", "_")
    for pattern in [f"spec_{safe_id}.json", f"spec_{spec_id}.json"]:
        for spec_file in base.rglob(pattern):
            with open(spec_file) as f:
                raw = json.load(f)
            spec = _parse_spec(raw)
            _SPECS[spec_id] = spec
            return spec
    raise FileNotFoundError(f"Experiment spec '{spec_id}' not found in {base}")


def _require_field(obj: dict, key: str, context: str) -> object:
    """Get a required field or raise SpecValidationError."""
    if key not in obj:
        raise SpecValidationError(
            f"spec validation: missing required field '{key}' in {context}"
        )
    return obj[key]


def _require_str(obj: dict, key: str, context: str) -> str:
    """Get a required string field with type check."""
    val = _require_field(obj, key, context)
    if not isinstance(val, str) or not val.strip():
        raise SpecValidationError(
            f"spec validation: field '{key}' in {context}"
            f" must be a non-empty string, got {type(val).__name__}"
        )
    return val


def _require_num(
    obj: dict, key: str, context: str, *,
    minimum: float | None = None, maximum: float | None = None,
) -> float:
    """Get a required numeric field with type and range check."""
    val = _require_field(obj, key, context)
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise SpecValidationError(
            f"spec validation: field '{key}' in {context}"
            f" must be a number, got {type(val).__name__}"
        )
    if minimum is not None and val < minimum:
        raise SpecValidationError(
            f"spec validation: field '{key}' in {context}"
            f" must be >= {minimum}, got {val}"
        )
    if maximum is not None and val > maximum:
        raise SpecValidationError(
            f"spec validation: field '{key}' in {context}"
            f" must be <= {maximum}, got {val}"
        )
    return float(val)


def _require_list(
    obj: dict, key: str, context: str, *,
    min_items: int = 1,
) -> list:
    """Get a required list field with type and minimum-length check."""
    val = _require_field(obj, key, context)
    if not isinstance(val, list):
        raise SpecValidationError(
            f"spec validation: field '{key}' in {context}"
            f" must be a list, got {type(val).__name__}"
        )
    if len(val) < min_items:
        raise SpecValidationError(
            f"spec validation: field '{key}' in {context}"
            f" must have at least {min_items} item(s), got {len(val)}"
        )
    return val


def _parse_spec(raw: dict) -> ExperimentSpec:
    """Parse and validate a raw spec dict.

    Raises ``SpecValidationError`` on any structural, type, or range
    failure. Replaces the previous bare ``KeyError`` behavior so
    callers receive a clear, actionable error message.
    """
    if not isinstance(raw, dict):
        raise SpecValidationError(
            "spec validation: top-level spec must be a JSON object"
        )

    spec_id = _require_str(raw, "experiment_spec_id", "top-level")

    ds = raw.get("dataset")
    if not isinstance(ds, dict):
        raise SpecValidationError(
            "spec validation: 'dataset' must be a JSON object"
        )
    dataset_name = _require_str(ds, "name", "dataset")
    dataset_version = _require_str(ds, "version", "dataset")
    dataset_raw_filename = _require_str(ds, "raw_filename", "dataset")
    dataset_raw_sha256 = _require_str(ds, "raw_sha256", "dataset")

    sp = raw.get("split")
    if not isinstance(sp, dict):
        raise SpecValidationError(
            "spec validation: 'split' must be a JSON object"
        )
    split_method = _require_str(sp, "method", "split")
    train_fraction = _require_num(
        sp, "train_fraction", "split", minimum=0.0, maximum=1.0,
    )
    test_fraction = _require_num(
        sp, "test_fraction", "split", minimum=0.0, maximum=1.0,
    )
    random_seed = _require_num(
        sp, "random_seed", "split", minimum=0.0,
    )

    an = raw.get("analysis")
    if not isinstance(an, dict):
        raise SpecValidationError(
            "spec validation: 'analysis' must be a JSON object"
        )
    analysis_entrypoint = _require_str(an, "entrypoint", "analysis")
    analysis_method = _require_str(an, "method", "analysis")
    declared_metrics = _require_list(an, "declared_metrics", "analysis")
    for i, m in enumerate(declared_metrics):
        if not isinstance(m, str) or not m.strip():
            raise SpecValidationError(
                f"spec validation: declared_metrics[{i}]"
                f" must be a non-empty string"
            )

    # Optional fields with defaults (backward-compatible).
    metrics_raw = raw.get("metrics", {})
    if not isinstance(metrics_raw, dict):
        raise SpecValidationError(
            "spec validation: 'metrics' must be a JSON object"
        )
    metric_directions: dict[str, str] = {}
    for k, v in metrics_raw.items():
        if isinstance(v, dict) and "direction" in v:
            metric_directions[k] = v["direction"]
        else:
            raise SpecValidationError(
                f"spec validation: metrics['{k}'] must have"
                f" a 'direction' field"
            )

    tolerances = raw.get("tolerances", {})
    if not isinstance(tolerances, dict):
        raise SpecValidationError(
            "spec validation: 'tolerances' must be a JSON object"
        )

    output_artifacts = raw.get("output_artifacts", [])
    if not isinstance(output_artifacts, list):
        raise SpecValidationError(
            "spec validation: 'output_artifacts' must be a list"
        )

    ri = raw.get("research_intent", {})
    if not isinstance(ri, dict):
        raise SpecValidationError(
            "spec validation: 'research_intent' must be a JSON object"
        )

    return ExperimentSpec(
        spec_id=spec_id,
        description=raw.get("description", ""),
        dataset_name=dataset_name,
        dataset_version=dataset_version,
        dataset_raw_filename=dataset_raw_filename,
        dataset_raw_sha256=dataset_raw_sha256,
        split_method=split_method,
        train_fraction=train_fraction,
        test_fraction=test_fraction,
        random_seed=int(random_seed),
        analysis_entrypoint=analysis_entrypoint,
        analysis_method=analysis_method,
        declared_metrics=declared_metrics,
        metric_directions=metric_directions,
        tolerances=tolerances,
        output_artifacts=output_artifacts,
        research_question=raw.get("research_question", ""),
        task_type=ri.get("task_type", ""),
        target_name=ri.get("target_name", ""),
        baseline_method=ri.get("baseline_method", ""),
        comparison_method=ri.get("comparison_method", ""),
        primary_metric=ri.get("primary_metric", ""),
        model_family=ri.get("model_family", raw.get("model_family", "")),
        hyperparameters=raw.get("hyperparameters", {}),
    )
