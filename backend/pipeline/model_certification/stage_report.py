"""Stage scorecards and report extension for v0.2.

Extends CapabilityReport with stage-specific evaluation data.
v0.2 fields are added alongside v0.1 fields — never deleted or mutated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.pipeline.model_certification.report import CapabilityReport


@dataclass
class StageScoreCard:
    """Score summary for a single pipeline stage."""

    stage: str
    cases_run: int = 0
    cases_passed: int = 0
    aggregate_score: float = 0.0
    schema_valid_rate: float = 0.0

    # Latency profile
    latency_p50: float = 0.0
    latency_p95: float = 0.0

    # Budget compliance
    token_budget_violation_rate: float = 0.0

    # Stage-specific metrics (metric_name → score)
    metrics: dict[str, float] = field(default_factory=dict)

    # Grounding metrics (empty if not required for this stage)
    grounding_metrics: dict[str, float] = field(default_factory=dict)

    # Known issues
    known_failure_modes: list[str] = field(default_factory=list)

    # Provenance
    scoring_method: str = "heuristic_gold_v0.2"
    case_suite_version: str = "seed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "cases_run": self.cases_run,
            "cases_passed": self.cases_passed,
            "aggregate_score": self.aggregate_score,
            "schema_valid_rate": self.schema_valid_rate,
            "latency_p50": self.latency_p50,
            "latency_p95": self.latency_p95,
            "token_budget_violation_rate": self.token_budget_violation_rate,
            "metrics": self.metrics,
            "grounding_metrics": self.grounding_metrics,
            "known_failure_modes": self.known_failure_modes,
            "scoring_method": self.scoring_method,
            "case_suite_version": self.case_suite_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StageScoreCard:
        return cls(**{
            k: v for k, v in data.items()
            if k in cls.__dataclass_fields__
        })


@dataclass
class StageEligibilityDecisionV2:
    """Per-stage eligibility decision with measured evidence."""

    stage: str
    eligibility: str          # approved | limited_use | repair_only | not_approved
    reason: str = ""
    score: float = 0.0
    hard_failures: list[str] = field(default_factory=list)
    manual_override: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "eligibility": self.eligibility,
            "reason": self.reason,
            "score": self.score,
            "hard_failures": self.hard_failures,
            "manual_override": self.manual_override,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StageEligibilityDecisionV2:
        return cls(**{
            k: v for k, v in data.items()
            if k in cls.__dataclass_fields__
        })


def extend_report_with_stage_eval(
    report: CapabilityReport,
    stage_scorecards: dict[str, StageScoreCard],
    stage_eligibility_v2: dict[str, StageEligibilityDecisionV2],
) -> CapabilityReport:
    """Extend a v0.1 CapabilityReport with v0.2 stage evaluation data.

    v0.1 fields (stage_eligibility) are preserved and never deleted.
    v0.2 fields are added alongside them.

    Args:
        report: The base v0.1 CapabilityReport.
        stage_scorecards: Per-stage scorecards.
        stage_eligibility_v2: Per-stage measured eligibility decisions.

    Returns:
        The same report object with v0.2 fields populated.
    """
    report.eval_version = "0.2"

    # Add stage eval scorecards
    report.stage_eval = {
        stage: card.to_dict()
        for stage, card in stage_scorecards.items()
    }

    # Add measured stage eligibility (alongside v0.1 generic eligibility)
    report.stage_eligibility_v2 = {
        stage: decision.to_dict()
        for stage, decision in stage_eligibility_v2.items()
    }

    return report


def compute_latency_percentiles(latencies: list[float]) -> tuple[float, float]:
    """Compute p50 and p95 from a list of latency values."""
    if not latencies:
        return 0.0, 0.0

    sorted_lat = sorted(latencies)
    n = len(sorted_lat)
    p50_idx = max(0, int(n * 0.50) - 1)
    p95_idx = max(0, int(n * 0.95) - 1)
    return sorted_lat[p50_idx], sorted_lat[min(p95_idx, n - 1)]
