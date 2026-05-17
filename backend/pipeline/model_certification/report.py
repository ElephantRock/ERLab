"""Capability report — machine-readable model certification artifact.

Includes provenance fields for reproducibility:
  eval_run_id, git_commit, manifest_hash, policy_version, schema_versions
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from backend.pipeline.model_certification.admission_policy import AdmissionStatus
from backend.pipeline.model_certification.hardware_probe import HardwareFitResult
from backend.pipeline.model_certification.smoke_test import SmokeTestResult
from backend.pipeline.model_certification.schema_eval import SchemaEvalResult


@dataclass
class CapabilityReport:
    """Machine-readable capability report for a model candidate."""

    # Identity
    model_id: str
    eval_version: str = "0.1"
    tested_at: str = ""
    status: str = "pending"  # AdmissionStatus value

    # Context
    safe_context_window: int = 0
    safe_output_tokens: int = 0

    # Sub-results
    hardware: dict | None = None      # HardwareFitResult as dict
    smoke_test: dict | None = None    # SmokeTestResult as dict
    schema_eval: dict | None = None   # SchemaEvalResult as dict

    # Admission
    stage_eligibility: dict[str, str] = field(default_factory=dict)
    promotion_allowed: bool = False
    scores: dict[str, float] = field(default_factory=dict)
    known_failure_modes: list[str] = field(default_factory=list)
    router_recommendation: dict[str, Any] = field(default_factory=dict)

    # v0.2 stage evaluation (optional, empty for v0.1 reports)
    stage_eval: dict[str, dict] | None = None              # stage → StageScoreCard dict
    stage_eligibility_v2: dict[str, dict] | None = None     # stage → StageEligibilityDecisionV2 dict

    # Provenance
    eval_run_id: str = ""
    git_commit: str | None = None
    manifest_hash: str = ""
    policy_version: str = "0.1"
    schema_versions: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.tested_at:
            self.tested_at = datetime.now(timezone.utc).isoformat()
        if not self.eval_run_id:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            self.eval_run_id = f"{self.model_id}-{ts}"
        if self.git_commit is None:
            self.git_commit = _get_git_commit()

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for YAML serialization."""
        return {
            "eval_run_id": self.eval_run_id,
            "model_id": self.model_id,
            "eval_version": self.eval_version,
            "tested_at": self.tested_at,
            "status": self.status,
            "safe_context_window": self.safe_context_window,
            "safe_output_tokens": self.safe_output_tokens,
            "hardware": self.hardware,
            "smoke_test": self.smoke_test,
            "schema_eval": self.schema_eval,
            "stage_eligibility": self.stage_eligibility,
            "promotion_allowed": self.promotion_allowed,
            "scores": self.scores,
            "known_failure_modes": self.known_failure_modes,
            "router_recommendation": self.router_recommendation,
            "stage_eval": self.stage_eval,
            "stage_eligibility_v2": self.stage_eligibility_v2,
            "provenance": {
                "git_commit": self.git_commit,
                "manifest_hash": self.manifest_hash,
                "policy_version": self.policy_version,
                "schema_versions": self.schema_versions,
            },
        }

    def to_yaml(self) -> str:
        """Serialize to YAML string."""
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml(cls, text: str) -> CapabilityReport:
        """Deserialize from YAML string."""
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError("YAML must contain a mapping")

        provenance = data.pop("provenance", {})

        return cls(
            model_id=data.get("model_id", "unknown"),
            eval_version=data.get("eval_version", "0.1"),
            tested_at=data.get("tested_at", ""),
            status=data.get("status", "pending"),
            safe_context_window=data.get("safe_context_window", 0),
            safe_output_tokens=data.get("safe_output_tokens", 0),
            hardware=data.get("hardware"),
            smoke_test=data.get("smoke_test"),
            schema_eval=data.get("schema_eval"),
            stage_eligibility=data.get("stage_eligibility", {}),
            promotion_allowed=data.get("promotion_allowed", False),
            scores=data.get("scores", {}),
            known_failure_modes=data.get("known_failure_modes", []),
            router_recommendation=data.get("router_recommendation", {}),
            stage_eval=data.get("stage_eval"),
            stage_eligibility_v2=data.get("stage_eligibility_v2"),
            eval_run_id=data.get("eval_run_id", ""),
            git_commit=provenance.get("git_commit"),
            manifest_hash=provenance.get("manifest_hash", ""),
            policy_version=provenance.get("policy_version", "0.1"),
            schema_versions=provenance.get("schema_versions", {}),
        )

    def write_to(self, directory: str | Path) -> Path:
        """Write report to data/model_certification/reports/<model_id>/<timestamp>.yaml."""
        dir_path = Path(directory) / self.model_id
        dir_path.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = dir_path / f"{ts}.yaml"
        path.write_text(self.to_yaml(), encoding="utf-8")
        return path


def _get_git_commit() -> str | None:
    """Get current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None
