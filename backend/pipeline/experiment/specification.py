"""Phase 5 — experiment specification loader.

A checked-in JSON file defining what is permitted to execute for a given
experiment spec. The runner receives the specification and a read-only dataset
path. It must not accept arbitrary file paths produced by the model.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path


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


def _parse_spec(raw: dict) -> ExperimentSpec:
    ds = raw["dataset"]
    sp = raw["split"]
    an = raw["analysis"]
    # Phase 8 / D2: research_intent is a structured block for new specs.
    # Backward-compatible: older specs (Iris/Phase 5/7) don't have it, so
    # all fields default to empty strings. The research_question property
    # still works as the scope-gate source.
    ri = raw.get("research_intent", {})
    return ExperimentSpec(
        spec_id=raw["experiment_spec_id"],
        description=raw.get("description", ""),
        dataset_name=ds["name"],
        dataset_version=ds["version"],
        dataset_raw_filename=ds["raw_filename"],
        dataset_raw_sha256=ds["raw_sha256"],
        split_method=sp["method"],
        train_fraction=sp["train_fraction"],
        test_fraction=sp["test_fraction"],
        random_seed=sp["random_seed"],
        analysis_entrypoint=an["entrypoint"],
        analysis_method=an["method"],
        declared_metrics=an["declared_metrics"],
        metric_directions={k: v["direction"] for k, v in raw.get("metrics", {}).items()},
        tolerances=raw.get("tolerances", {}),
        output_artifacts=raw.get("output_artifacts", []),
        research_question=raw.get("research_question", ""),
        task_type=ri.get("task_type", ""),
        target_name=ri.get("target_name", ""),
        baseline_method=ri.get("baseline_method", ""),
        comparison_method=ri.get("comparison_method", ""),
        primary_metric=ri.get("primary_metric", ""),
    )
