"""Certified Capability Lookup — reads production registry + capability reports.

Prefers v0.2 stage eligibility when present, falls back to v0.1 generic eligibility.
Returns CertifiedModelCandidate objects for the SmartRouter to evaluate.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from backend.pipeline.model_certification.report import CapabilityReport
from backend.pipeline.model_certification.stage_report import StageScoreCard

logger = logging.getLogger(__name__)


@dataclass
class CertifiedModelCandidate:
    """A model that has been certified for at least some stages."""

    model_id: str
    provider: str
    allowed_stages: list[str] = field(default_factory=list)
    stage_eligibility: str = "limited_use"   # overall v0.1 admission status
    safe_context_window: int = 0
    safe_output_tokens: int = 0
    schema_valid_rate: float = 0.0
    stage_score: float | None = None         # v0.2 aggregate score for specific stage
    grounding_metrics: dict[str, float] = field(default_factory=dict)
    latency_class: str | None = None
    report_path: str = ""
    eval_version: str = "0.1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "allowed_stages": self.allowed_stages,
            "stage_eligibility": self.stage_eligibility,
            "safe_context_window": self.safe_context_window,
            "safe_output_tokens": self.safe_output_tokens,
            "schema_valid_rate": self.schema_valid_rate,
            "stage_score": self.stage_score,
            "grounding_metrics": self.grounding_metrics,
            "latency_class": self.latency_class,
            "report_path": self.report_path,
            "eval_version": self.eval_version,
        }


class CertifiedCapabilityLookup:
    """Reads production registry + capability reports for certified candidates."""

    def __init__(self, registry_dir: str | Path = "data/model_certification") -> None:
        self._dir = Path(registry_dir)
        self._production_registry: dict[str, dict[str, Any]] = {}
        self._report_cache: dict[str, CapabilityReport] = {}
        self._load_production_registry()

    def _load_production_registry(self) -> None:
        """Load production_registry.yaml."""
        reg_path = self._dir / "production_registry.yaml"
        if not reg_path.exists():
            logger.debug("No production registry at %s", reg_path)
            return

        data = yaml.safe_load(reg_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            self._production_registry = data.get("models", {})

    def get_candidates_for_stage(self, stage: str) -> list[CertifiedModelCandidate]:
        """Return all production models eligible for this stage.

        Prefers v0.2 stage_eligibility_v2 when present.
        Falls back to v0.1 stage_eligibility otherwise.
        """
        candidates = []

        for model_id, entry in self._production_registry.items():
            if not isinstance(entry, dict):
                continue

            allowed_stages = entry.get("allowed_stages", {})
            if not isinstance(allowed_stages, dict):
                continue

            # Check if this stage is allowed (v0.1 style)
            stage_eligibility_v1 = allowed_stages.get(stage)
            if not stage_eligibility_v1 or stage_eligibility_v1 in ("not_approved", "blocked"):
                continue

            # Try to load report for richer data
            report = self.get_latest_report(model_id)
            provider = entry.get("provider", "unknown")
            safe_ctx = 0
            safe_out = 0
            schema_rate = 0.0
            stage_score = None
            grounding_metrics: dict[str, float] = {}
            eval_version = "0.1"
            latency_class = None

            if report:
                safe_ctx = report.safe_context_window
                safe_out = report.safe_output_tokens
                eval_version = report.eval_version

                # Schema valid rate from scores
                schema_rate = report.scores.get("schema_valid_rate", 0.0)
                if not schema_rate and report.schema_eval:
                    schema_rate = report.schema_eval.get("schema_valid_rate", 0.0)

                # v0.2: check stage_eligibility_v2
                if report.stage_eligibility_v2 and stage in report.stage_eligibility_v2:
                    v2_decision = report.stage_eligibility_v2[stage]
                    if isinstance(v2_decision, dict):
                        v2_elig = v2_decision.get("eligibility", "")
                        if v2_elig in ("not_approved",):
                            continue  # v0.2 overrides v0.1
                        stage_score = v2_decision.get("score")

                # v0.2: grounding metrics from stage eval
                if report.stage_eval and stage in report.stage_eval:
                    stage_card = report.stage_eval[stage]
                    if isinstance(stage_card, dict):
                        gm = stage_card.get("grounding_metrics", {})
                        if isinstance(gm, dict):
                            grounding_metrics = {k: float(v) for k, v in gm.items() if isinstance(v, (int, float))}
                        if stage_score is None:
                            stage_score = stage_card.get("aggregate_score")

                # Latency class from router_recommendation or hardware
                rr = report.router_recommendation or {}
                latency_class = rr.get("latency_class")

            candidates.append(CertifiedModelCandidate(
                model_id=model_id,
                provider=provider,
                allowed_stages=list(allowed_stages.keys()),
                stage_eligibility=entry.get("status", stage_eligibility_v1),
                safe_context_window=safe_ctx,
                safe_output_tokens=safe_out,
                schema_valid_rate=schema_rate,
                stage_score=stage_score,
                grounding_metrics=grounding_metrics,
                latency_class=latency_class,
                report_path=entry.get("report_path", ""),
                eval_version=eval_version,
            ))

        return candidates

    def get_latest_report(self, model_id: str) -> CapabilityReport | None:
        """Load the most recent capability report for a model."""
        if model_id in self._report_cache:
            return self._report_cache[model_id]

        reports_dir = self._dir / "reports" / model_id
        if not reports_dir.exists():
            return None

        yaml_files = sorted(reports_dir.glob("*.yaml"), reverse=True)
        if not yaml_files:
            return None

        try:
            report = CapabilityReport.from_yaml(
                yaml_files[0].read_text(encoding="utf-8")
            )
            self._report_cache[model_id] = report
            return report
        except Exception as e:
            logger.warning("Failed to load report for %s: %s", model_id, e)
            return None

    def get_stage_scorecard(self, model_id: str, stage: str) -> StageScoreCard | None:
        """Get v0.2 stage scorecard, or None if only v0.1 data exists."""
        report = self.get_latest_report(model_id)
        if not report or not report.stage_eval:
            return None

        card_data = report.stage_eval.get(stage)
        if not isinstance(card_data, dict):
            return None

        return StageScoreCard.from_dict(card_data)

    @property
    def production_models(self) -> dict[str, dict[str, Any]]:
        """Raw production registry data."""
        return dict(self._production_registry)
