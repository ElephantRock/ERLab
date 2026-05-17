"""Claim types, section contracts, and support requirements.

Defines the epistemic taxonomy for evidence-grounded generation.

CRITICAL INVARIANTS:
- DesignAssumption is NOT a ClaimType. It is a separate dataclass.
- Assumptions are NEVER in the claim denominator.
- The contradiction override applies to ALL claim types including hypotheses.
- Benefit-smuggling uses two tiers: hard (auto-split) and soft (warning only).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ── Claim Types ──────────────────────────────────────────────────────────

class ClaimType(str, Enum):
    """11 epistemic claim types. Each has distinct support requirements.

    These are the ONLY types that enter the claim denominator for metrics.
    DesignAssumption is NOT a ClaimType — it is a separate register.
    """

    BACKGROUND = "background"
    PRIOR_LIMITATION = "prior_limitation"
    METHOD_DESIGN_MOTIVATION = "method_design_motivation"
    METHOD_PROPOSED_MECHANISM = "method_proposed_mechanism"
    METHOD_CLAIMED_BENEFIT = "method_claimed_benefit"
    HYPOTHESIS = "hypothesis"
    EVALUATION_BENCHMARK = "evaluation_benchmark"
    EVALUATION_METRIC = "evaluation_metric"
    EVALUATION_PROTOCOL = "evaluation_protocol"
    EXPECTED_CONTRIBUTION = "expected_contribution"
    RESULT = "result"


# Set for fast membership checks — assumptions are NOT here
CLAIM_TYPE_VALUES = {ct.value for ct in ClaimType}


# ── Design Assumption (separate register) ────────────────────────────────

@dataclass
class DesignAssumption:
    """A design assumption — NOT a ClaimType.

    Assumptions are reported separately from claims. They do NOT affect
    direct_support_rate, epistemic_acceptability_rate, or overclaim_rate.
    """

    assumption_id: str       # Deterministic: P0-method-A001
    text: str
    basis: str               # "analogical" | "theoretical" | "empirical" | "conjecture"
    supporting_sources: list[str] = field(default_factory=list)
    risk: str = "medium"     # "low" | "medium" | "high"
    validation_plan: str = ""

    def to_dict(self) -> dict:
        return {
            "assumption_id": self.assumption_id,
            "text": self.text[:200],
            "basis": self.basis,
            "risk": self.risk,
            "validation_plan": self.validation_plan[:200],
            "has_validation_plan": bool(self.validation_plan.strip()),
        }


# ── Benefit Detection Keywords ───────────────────────────────────────────

# Hard keywords: auto-split mechanism → mechanism + benefit
BENEFIT_SPLIT_KEYWORDS = [
    "improves", "enables", "solves", "reduces", "advances",
    "increases", "outperforms", "mitigates", "enhances",
]

# Soft keywords: log warning, don't auto-split
BENEFIT_WARNING_KEYWORDS = [
    "is robust to", "is suitable for", "supports safer",
    "allows better", "facilitates", "promotes",
    "leads to", "contributes to", "paves the way",
]


def detect_benefit_phrases(text: str) -> tuple[bool, bool, list[str]]:
    """Check if text contains benefit phrases.

    Returns:
        (has_hard, has_soft, matched_keywords)
    """
    text_lower = text.lower()

    hard_matches = [kw for kw in BENEFIT_SPLIT_KEYWORDS if kw in text_lower]
    soft_matches = [kw for kw in BENEFIT_WARNING_KEYWORDS if kw in text_lower]

    return (len(hard_matches) > 0, len(soft_matches) > 0, hard_matches + soft_matches)


# ── Support Requirements ─────────────────────────────────────────────────

CLAIM_SUPPORT_REQUIREMENTS: dict[str, dict[str, Any]] = {
    ClaimType.BACKGROUND.value: {
        "min_support": "strong",
        "corpus_required": True,
    },
    ClaimType.PRIOR_LIMITATION.value: {
        "min_support": "weak",
        "corpus_required": True,
    },
    ClaimType.METHOD_DESIGN_MOTIVATION.value: {
        "min_support": "weak",
        "corpus_required": True,
        "analogical_ok": True,
    },
    ClaimType.METHOD_PROPOSED_MECHANISM.value: {
        "min_support": "none",
        "corpus_required": False,
        "must_be_purely_descriptive": True,
    },
    ClaimType.METHOD_CLAIMED_BENEFIT.value: {
        "min_support": "none",
        "corpus_required": False,
        "must_be_marked_speculative": True,
    },
    ClaimType.HYPOTHESIS.value: {
        "min_support": "none",
        "corpus_required": False,
        "must_be_marked_speculative": True,
    },
    ClaimType.EVALUATION_BENCHMARK.value: {
        "min_support": "weak",
        "corpus_required": False,
        "cite_precedent_or_mark_new": True,
    },
    ClaimType.EVALUATION_METRIC.value: {
        "min_support": "weak",
        "corpus_required": False,
        "cite_precedent_or_mark_new": True,
    },
    ClaimType.EVALUATION_PROTOCOL.value: {
        "min_support": "none",
        "corpus_required": False,
        "requires_design_rationale": True,
    },
    ClaimType.EXPECTED_CONTRIBUTION.value: {
        "min_support": "none",
        "corpus_required": False,
        "must_be_marked_speculative": True,
    },
    ClaimType.RESULT.value: {
        "min_support": "strong",
        "corpus_required": True,
        "requires_experiment": True,
    },
}


# ── Section Contracts ────────────────────────────────────────────────────

SECTION_CONTRACTS: dict[str, dict[str, Any]] = {
    "abstract": {
        "allowed_types": [
            ClaimType.BACKGROUND.value,
            ClaimType.METHOD_PROPOSED_MECHANISM.value,
            ClaimType.EXPECTED_CONTRIBUTION.value,
        ],
        "must_mark_speculative": [
            ClaimType.EXPECTED_CONTRIBUTION.value,
        ],
        "require_four_blocks": False,
    },
    "introduction": {
        "allowed_types": [
            ClaimType.BACKGROUND.value,
            ClaimType.PRIOR_LIMITATION.value,
            ClaimType.METHOD_DESIGN_MOTIVATION.value,
        ],
        "must_cite": [
            ClaimType.BACKGROUND.value,
            ClaimType.PRIOR_LIMITATION.value,
        ],
        "require_four_blocks": False,
    },
    "related_work": {
        "allowed_types": [
            ClaimType.BACKGROUND.value,
            ClaimType.PRIOR_LIMITATION.value,
        ],
        "must_cite": True,  # ALL claims must cite corpus
        "allow_speculative": False,
        "require_four_blocks": False,
    },
    "proposed_method": {
        "allowed_types": [
            ClaimType.METHOD_DESIGN_MOTIVATION.value,
            ClaimType.METHOD_PROPOSED_MECHANISM.value,
            ClaimType.METHOD_CLAIMED_BENEFIT.value,
            ClaimType.HYPOTHESIS.value,
            ClaimType.BACKGROUND.value,
        ],
        "must_cite": [
            ClaimType.BACKGROUND.value,
            ClaimType.METHOD_DESIGN_MOTIVATION.value,
        ],
        "must_mark_speculative": [
            ClaimType.METHOD_CLAIMED_BENEFIT.value,
            ClaimType.HYPOTHESIS.value,
        ],
        "require_four_blocks": False,
        "has_assumption_register": True,
    },
    "evaluation_plan": {
        "allowed_types": [
            ClaimType.EVALUATION_BENCHMARK.value,
            ClaimType.EVALUATION_METRIC.value,
            ClaimType.EVALUATION_PROTOCOL.value,
            ClaimType.BACKGROUND.value,
            ClaimType.HYPOTHESIS.value,
        ],
        "must_cite": [
            ClaimType.BACKGROUND.value,
        ],
        "must_mark_speculative": [
            ClaimType.HYPOTHESIS.value,
        ],
        "require_four_blocks": True,
        "required_blocks": [
            "benchmarks", "metrics", "protocol", "expected_outcomes",
        ],
        "has_assumption_register": True,
    },
    "discussion": {
        "allowed_types": [
            ClaimType.BACKGROUND.value,
            ClaimType.HYPOTHESIS.value,
            ClaimType.EXPECTED_CONTRIBUTION.value,
        ],
        "must_mark_speculative": [
            ClaimType.HYPOTHESIS.value,
            ClaimType.EXPECTED_CONTRIBUTION.value,
        ],
        "require_four_blocks": False,
    },
    "conclusion": {
        "allowed_types": [
            ClaimType.BACKGROUND.value,
            ClaimType.EXPECTED_CONTRIBUTION.value,
        ],
        "must_mark_speculative": [
            ClaimType.EXPECTED_CONTRIBUTION.value,
        ],
        "require_four_blocks": False,
    },
}


# ── Allowed speculative markers ──────────────────────────────────────────

# For expected_contribution: these are acceptable ways to frame speculation
EXPECTED_CONTRIBUTION_ALLOWED_MARKERS = [
    "we expect", "we aim to", "this work is intended to",
    "this paper proposes", "we hope to", "we plan to",
]

# These imply established fact and are NOT acceptable for speculative claims
EXPECTED_CONTRIBUTION_FORBIDDEN_MARKERS = [
    "this work advances", "this method enables", "this framework solves",
    "our approach achieves", "we demonstrate", "we show that",
]


def is_type_allowed_in_section(claim_type: str, section_id: str) -> bool:
    """Check if a claim type is allowed in a given section."""
    contract = SECTION_CONTRACTS.get(section_id, {})
    allowed = contract.get("allowed_types", [])
    return claim_type in allowed


def must_mark_speculative(claim_type: str, section_id: str) -> bool:
    """Check if a claim type must be marked speculative in a section."""
    contract = SECTION_CONTRACTS.get(section_id, {})
    speculative_types = contract.get("must_mark_speculative", [])
    return claim_type in speculative_types


def must_cite(claim_type: str, section_id: str) -> bool:
    """Check if a claim type requires citation in a section."""
    contract = SECTION_CONTRACTS.get(section_id, {})
    cite_rule = contract.get("must_cite", False)
    if cite_rule is True:
        return True  # ALL claims must cite
    if isinstance(cite_rule, list):
        return claim_type in cite_rule
    return False


def get_support_requirement(claim_type: str) -> dict[str, Any]:
    """Get support requirements for a claim type."""
    return CLAIM_SUPPORT_REQUIREMENTS.get(claim_type, {
        "min_support": "none",
        "corpus_required": False,
    })
