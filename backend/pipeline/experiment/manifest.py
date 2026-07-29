"""Phase 5 — experiment manifest: reproducibility and result identity.

Non-duplicative: does NOT store code_md, stdout, stderr, exit_code — those
remain on the existing ExperimentResult row. The manifest stores only
reproducibility metadata and result artifact identity.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DatasetIdentity:
    """Frozen identity of a registered dataset."""

    name: str
    version: str
    source: str
    license: str
    relative_path: str
    raw_sha256: str
    processed_sha256: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "source": self.source,
            "license": self.license,
            "relative_path": self.relative_path,
            "raw_sha256": self.raw_sha256,
            "processed_sha256": self.processed_sha256,
        }


@dataclass
class SplitSpec:
    """Frozen train/test split specification."""

    method: str
    train_fraction: float
    test_fraction: float
    random_seed: int

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "train_fraction": self.train_fraction,
            "test_fraction": self.test_fraction,
            "random_seed": self.random_seed,
        }


@dataclass
class AnalysisSpec:
    """Frozen analysis specification."""

    entrypoint: str
    code_sha256: str
    command: str
    method: str
    declared_metrics: list[str]

    def to_dict(self) -> dict:
        return {
            "entrypoint": self.entrypoint,
            "code_sha256": self.code_sha256,
            "command": self.command,
            "method": self.method,
            "declared_metrics": self.declared_metrics,
        }


@dataclass
class EnvironmentRecord:
    """Captured execution environment for reproducibility."""

    python_version: str
    platform: str
    dependency_lock_sha256: str | None = None
    relevant_package_versions: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "python_version": self.python_version,
            "platform": self.platform,
            "dependency_lock_sha256": self.dependency_lock_sha256,
            "relevant_package_versions": self.relevant_package_versions,
        }


@dataclass
class ResultArtifact:
    """Identity of a single result artifact file."""

    filename: str
    sha256: str
    artifact_type: str  # metrics | predictions | table | figure

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "sha256": self.sha256,
            "artifact_type": self.artifact_type,
        }


@dataclass
class ExperimentManifest:
    """Complete reproducibility manifest for one experiment execution.

    Does NOT duplicate code_md, stdout, stderr, exit_code — those remain on
    ExperimentResult. This stores only reproducibility and result identity.
    """

    schema_version: str = "1"
    experiment_spec_id: str = ""
    dataset: DatasetIdentity | None = None
    split: SplitSpec | None = None
    analysis: AnalysisSpec | None = None
    environment: EnvironmentRecord | None = None
    configuration: dict = field(default_factory=dict)
    results: dict[str, float] = field(default_factory=dict)  # metric_name -> observed_value
    result_artifacts: list[ResultArtifact] = field(default_factory=list)
    observed_at: str = ""
    reproduction: dict = field(default_factory=dict)  # declared_tolerances

    # Execution state (mirrors the DB row but without duplicating logs)
    status: str = "pending"  # pending | succeeded | failed | invalid_results | not_requested | reproduction_failed

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "experiment_spec_id": self.experiment_spec_id,
            "dataset": self.dataset.to_dict() if self.dataset else None,
            "split": self.split.to_dict() if self.split else None,
            "analysis": self.analysis.to_dict() if self.analysis else None,
            "environment": self.environment.to_dict() if self.environment else None,
            "configuration": self.configuration,
            "results": self.results,
            "result_artifacts": [a.to_dict() for a in self.result_artifacts],
            "observed_at": self.observed_at,
            "reproduction": self.reproduction,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ExperimentManifest:
        ds = d.get("dataset")
        sp = d.get("split")
        an = d.get("analysis")
        env = d.get("environment")
        artifacts = d.get("result_artifacts", [])
        return cls(
            schema_version=d.get("schema_version", "1"),
            experiment_spec_id=d.get("experiment_spec_id", ""),
            dataset=DatasetIdentity(**ds) if ds else None,
            split=SplitSpec(**sp) if sp else None,
            analysis=AnalysisSpec(**an) if an else None,
            environment=EnvironmentRecord(**env) if env else None,
            configuration=d.get("configuration", {}),
            results=d.get("results", {}),
            result_artifacts=[ResultArtifact(**a) for a in artifacts] if artifacts else [],
            observed_at=d.get("observed_at", ""),
            reproduction=d.get("reproduction", {}),
            status=d.get("status", "pending"),
        )


@dataclass
class ResultMarker:
    """A single empirical result linked to a paper claim.

    Separates empirical provenance ([RESULT-N]) from literature provenance
    ([SOURCE-N]).
    """

    marker_index: int
    marker: str  # e.g. "RESULT-1"
    metric_name: str
    observed_value: float
    artifact_path: str
    artifact_sha256: str
    experiment_result_id: int
    paper_claim_key: str = ""  # which claim this result supports
    paper_section: str = ""  # which paper section cites it

    def to_dict(self) -> dict:
        return {
            "marker_index": self.marker_index,
            "marker": self.marker,
            "metric_name": self.metric_name,
            "observed_value": self.observed_value,
            "artifact_path": self.artifact_path,
            "artifact_sha256": self.artifact_sha256,
            "experiment_result_id": self.experiment_result_id,
            "paper_claim_key": self.paper_claim_key,
            "paper_section": self.paper_section,
        }


def compute_sha256(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
