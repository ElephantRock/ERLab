"""Admission policy — decide whether a model enters production.

Returns a structured AdmissionDecision with:
  - status (AdmissionStatus)
  - stage_eligibility (dict[str, str])
  - promotion_allowed (bool)

promotion_allowed is derived from status + stage_eligibility + policy gates,
not merely from status alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import yaml
from pathlib import Path


class AdmissionStatus(str, Enum):
    """Possible admission outcomes."""

    REJECTED = "rejected"
    REQUIRES_MANUAL_REVIEW = "requires_manual_review"
    APPROVED_FOR_LIMITED_USE = "approved_for_limited_use"
    APPROVED_FOR_REPAIR_ONLY = "approved_for_repair_only"
    APPROVED_FOR_PRODUCTION = "approved_for_production"


# Default policy thresholds
_DEFAULT_POLICY = {
    "hard_reject": {
        "smoke_test_passed": False,
        "hardware_stable": False,
        "crash_rate_gt": 0.02,
    },
    "production_required": {
        "schema_valid_rate_gte": 0.95,
        "valid_json_rate_gte": 0.95,
        "safe_context_window_gte": 4096,
    },
    "limited_use_allowed": {
        "schema_valid_rate_gte": 0.85,
        "valid_json_rate_gte": 0.90,
        "safe_context_window_gte": 4096,
    },
    "repair_only_allowed": {
        "schema_valid_rate_gte": 0.70,
        "valid_json_rate_gte": 0.75,
        "safe_context_window_gte": 4096,
    },
}

# v0.1 conservative stage assignments
_LOW_RISK_STAGES = {"draft", "repair", "gap_analysis", "feasibility_scoring"}
_MEDIUM_RISK_STAGES = {"idea_generation", "evaluation", "novelty_checking"}
_HIGH_RISK_STAGES = {"paper_synthesis", "proposal_synthesis", "adversarial_review", "citation_audit"}
_ALL_STAGES = _LOW_RISK_STAGES | _MEDIUM_RISK_STAGES | _HIGH_RISK_STAGES


@dataclass
class AdmissionDecision:
    """Structured admission decision."""

    status: AdmissionStatus
    stage_eligibility: dict[str, str]
    promotion_allowed: bool


def load_policy(path: str | Path | None = None) -> dict[str, Any]:
    """Load admission policy from YAML, or return defaults."""
    if path and Path(path).exists():
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    return _DEFAULT_POLICY


def decide_admission(
    smoke_passed: bool,
    hardware_stable: bool,
    schema_valid_rate: float,
    valid_json_rate: float,
    safe_context_window: int,
    native_json_mode: bool = False,
    policy: dict[str, Any] | None = None,
) -> AdmissionDecision:
    """Apply admission policy and return a structured decision.

    Args:
        smoke_passed: Did the smoke test pass?
        hardware_stable: Is the hardware stable?
        schema_valid_rate: Fraction of schema-compliant outputs.
        valid_json_rate: Fraction of parseable JSON outputs.
        safe_context_window: Estimated safe context tokens.
        native_json_mode: Does the model support native JSON mode?
        policy: Policy thresholds (None = defaults).

    Returns:
        AdmissionDecision with status, stage_eligibility, and promotion_allowed.
    """
    if policy is None:
        policy = _DEFAULT_POLICY

    # ---- Hard reject gates ----
    hard = policy.get("hard_reject", {})

    if not smoke_passed:
        return AdmissionDecision(
            status=AdmissionStatus.REJECTED,
            stage_eligibility={s: "blocked" for s in _ALL_STAGES},
            promotion_allowed=False,
        )

    if not hardware_stable:
        return AdmissionDecision(
            status=AdmissionStatus.REJECTED,
            stage_eligibility={s: "blocked" for s in _ALL_STAGES},
            promotion_allowed=False,
        )

    # ---- Compute stage eligibility ----
    eligibility: dict[str, str] = {}

    # v0.1: high-risk stages are NEVER approved from this harness alone
    for stage in _HIGH_RISK_STAGES:
        eligibility[stage] = "not_approved"

    # Schema-dependent stages
    if schema_valid_rate >= 0.95:
        for stage in _MEDIUM_RISK_STAGES:
            eligibility[stage] = "approved"
        for stage in _LOW_RISK_STAGES:
            eligibility[stage] = "approved"
    elif schema_valid_rate >= 0.85:
        for stage in _MEDIUM_RISK_STAGES:
            eligibility[stage] = "limited"
        for stage in _LOW_RISK_STAGES:
            eligibility[stage] = "approved"
    elif schema_valid_rate >= 0.70:
        for stage in _MEDIUM_RISK_STAGES:
            eligibility[stage] = "not_approved"
        for stage in _LOW_RISK_STAGES:
            eligibility[stage] = "limited"
    else:
        for stage in _MEDIUM_RISK_STAGES | _LOW_RISK_STAGES:
            eligibility[stage] = "not_approved"

    # Structured generation requires schema_valid >= 0.95
    if schema_valid_rate < 0.95:
        eligibility["structured_generation"] = "not_approved"
    else:
        eligibility["structured_generation"] = "approved"

    # ---- Determine status ----
    prod_req = policy.get("production_required", {})
    limited_req = policy.get("limited_use_allowed", {})
    repair_req = policy.get("repair_only_allowed", {})

    if _meets_thresholds(schema_valid_rate, valid_json_rate, safe_context_window, prod_req):
        status = AdmissionStatus.APPROVED_FOR_PRODUCTION
    elif _meets_thresholds(schema_valid_rate, valid_json_rate, safe_context_window, limited_req):
        status = AdmissionStatus.APPROVED_FOR_LIMITED_USE
    elif _meets_thresholds(schema_valid_rate, valid_json_rate, safe_context_window, repair_req):
        status = AdmissionStatus.APPROVED_FOR_REPAIR_ONLY
    else:
        status = AdmissionStatus.REQUIRES_MANUAL_REVIEW

    # ---- Determine promotion_allowed ----
    # Derived from status + eligibility, not status alone
    promotable_statuses = {
        AdmissionStatus.APPROVED_FOR_PRODUCTION,
        AdmissionStatus.APPROVED_FOR_LIMITED_USE,
        AdmissionStatus.APPROVED_FOR_REPAIR_ONLY,
    }

    has_eligible_stages = any(
        v not in ("not_approved", "blocked")
        for v in eligibility.values()
    )

    promotion_allowed = status in promotable_statuses and has_eligible_stages

    return AdmissionDecision(
        status=status,
        stage_eligibility=eligibility,
        promotion_allowed=promotion_allowed,
    )


def _meets_thresholds(
    schema_valid_rate: float,
    valid_json_rate: float,
    safe_context_window: int,
    thresholds: dict[str, Any],
) -> bool:
    """Check if metrics meet all thresholds in a policy tier."""
    if schema_valid_rate < thresholds.get("schema_valid_rate_gte", 0):
        return False
    if valid_json_rate < thresholds.get("valid_json_rate_gte", 0):
        return False
    if safe_context_window < thresholds.get("safe_context_window_gte", 0):
        return False
    return True
