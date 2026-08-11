"""Stage eligibility policy — per-stage admission gates.

v0.2 supersedes v0.1 generic eligibility with measured per-stage decisions.
v0.1 fields are never deleted — v0.2 adds stage_eligibility_v2 alongside.

Implementation cautions enforced:
  - paper/proposal synthesis capped at limited_use in v0.2
  - citation_fabrication > 0.00 blocks grounded approval
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from backend.pipeline.model_certification.stage_report import (
    StageEligibilityDecisionV2,
    StageScoreCard,
)

# Default per-stage gates
_DEFAULT_STAGE_GATES: dict[str, dict[str, Any]] = {
    "query_generation": {
        "min_schema_valid_rate": 0.90,
        "min_stage_score": 0.75,
    },
    "literature_filtering": {
        "min_recall": 0.85,
        "max_false_rejection_rate": 0.15,
    },
    "paper_extraction": {
        "min_field_completeness": 0.85,
        "min_extraction_accuracy": 0.80,
    },
    "evidence_table": {
        "max_unsupported_claim_rate": 0.15,
        "min_citation_completeness": 0.85,
    },
    "repair": {
        "min_schema_repair_success": 0.85,
        "min_semantic_preservation": 0.80,
    },
    "adversarial_review": {
        "min_weakness_detection_rate": 0.70,
        "max_false_alarm_rate": 0.35,
    },
    "paper_synthesis": {
        "min_section_completeness": 0.90,
        "max_citation_fabrication_rate": 0.00,
        "min_citation_grounding": 0.70,
        "max_eligibility": "limited_use",  # v0.2 cap
    },
    "proposal_synthesis": {
        "min_method_specificity": 0.70,
        "min_feasibility_clarity": 0.70,
        "max_eligibility": "limited_use",  # v0.2 cap
    },
}

# High-risk stages that cannot exceed limited_use in v0.2
_V02_CAPS: dict[str, str] = {
    "paper_synthesis": "limited_use",
    "proposal_synthesis": "limited_use",
}


def load_stage_policy(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """Load per-stage policy gates from YAML."""
    if path and Path(path).exists():
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    return _DEFAULT_STAGE_GATES


def decide_stage_eligibility(
    stage: str,
    scorecard: StageScoreCard,
    policy_gates: dict[str, dict[str, Any]] | None = None,
) -> StageEligibilityDecisionV2:
    """Decide eligibility for a single stage based on measured scores.

    Returns StageEligibilityDecisionV2 with eligibility:
      approved | limited_use | repair_only | not_approved
    """
    if policy_gates is None:
        policy_gates = _DEFAULT_STAGE_GATES

    gates = policy_gates.get(stage, {})
    if not gates:
        return StageEligibilityDecisionV2(
            stage=stage,
            eligibility="not_approved",
            reason=f"No policy gates defined for stage '{stage}'",
            score=scorecard.aggregate_score,
        )

    # Check grounding hard gates first
    hard_failures = _check_grounding_hard_gates(stage, scorecard)
    if hard_failures:
        return StageEligibilityDecisionV2(
            stage=stage,
            eligibility="not_approved",
            reason="Grounding hard gate failed",
            score=scorecard.aggregate_score,
            hard_failures=hard_failures,
        )

    # Check metric thresholds
    all_metrics = {**scorecard.metrics, **scorecard.grounding_metrics}
    failures = []

    for gate_name, threshold in gates.items():
        if gate_name in ("max_eligibility",):
            continue  # meta-gate, handled below

        # Determine direction: min_ or max_
        if gate_name.startswith("min_"):
            metric_name = gate_name[4:]  # strip "min_"
            actual = all_metrics.get(metric_name, 0.0)
            if actual < threshold:
                failures.append(f"{gate_name}: {actual:.3f} < {threshold}")
        elif gate_name.startswith("max_"):
            metric_name = gate_name[4:]  # strip "max_"
            actual = all_metrics.get(metric_name, 1.0)
            if actual > threshold:
                failures.append(f"{gate_name}: {actual:.3f} > {threshold}")

    if not failures:
        eligibility = "approved"
        reason = "All gates passed"
    elif len(failures) <= 2:
        eligibility = "limited_use"
        reason = f"Minor threshold misses: {'; '.join(failures[:3])}"
    elif len(failures) <= 4:
        eligibility = "repair_only"
        reason = f"Multiple threshold misses: {'; '.join(failures[:3])}"
    else:
        eligibility = "not_approved"
        reason = f"Too many threshold misses: {'; '.join(failures[:3])}"

    # Apply v0.2 caps for high-risk stages
    cap = _V02_CAPS.get(stage)
    if cap:
        rank = {"approved": 3, "limited_use": 2, "repair_only": 1, "not_approved": 0}
        if rank.get(eligibility, 0) > rank.get(cap, 0):
            eligibility = cap
            if not failures:
                reason = f"v0.2 cap: {stage} limited to {cap}"
            else:
                reason += f" (v0.2 cap: {cap})"

    return StageEligibilityDecisionV2(
        stage=stage,
        eligibility=eligibility,
        reason=reason,
        score=scorecard.aggregate_score,
        hard_failures=hard_failures,
    )


def _check_grounding_hard_gates(
    stage: str,
    scorecard: StageScoreCard,
) -> list[str]:
    """Check grounding hard gates for a stage."""
    failures = []
    gm = scorecard.grounding_metrics

    if not gm:
        return []

    # Citation fabrication > 0.00 → hard fail
    if gm.get("citation_fabrication_rate", 0.0) > 0.00:
        failures.append(
            f"Citation fabrication detected: {gm['citation_fabrication_rate']:.3f}"
        )

    # Unsupported claims > 0.20 → hard fail
    if gm.get("unsupported_claim_rate", 0.0) > 0.20:
        failures.append(
            f"Unsupported claim rate too high: {gm['unsupported_claim_rate']:.3f} > 0.20"
        )

    return failures


def decide_all_stages(
    scorecards: dict[str, StageScoreCard],
    policy_gates: dict[str, dict[str, Any]] | None = None,
) -> dict[str, StageEligibilityDecisionV2]:
    """Decide eligibility for all stages with scorecards."""
    decisions = {}
    for stage, card in scorecards.items():
        decisions[stage] = decide_stage_eligibility(stage, card, policy_gates)
    return decisions
