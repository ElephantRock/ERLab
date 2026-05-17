"""Claim type validator — epistemic enforcement layer.

Validates declared claim types against section contracts, checks benefit smuggling,
enforces contradiction override on ALL types including hypotheses, and classifies
each claim for downstream metric computation.

ARCHITECTURE:
    Validator → Classification (supported / hypothesis / overclaim / contradicted / assumption)
    Repair    → Mutation (mark / reclassify / split / remove / qualify)

The validator does NOT mutate. It classifies and recommends.
The repair loop (evidence_repair.py) acts on recommendations.

METRICS:
    direct_support_rate  = supported / total_claims
    epistemic_acceptability = (supported + design_justified + correctly_marked_hypotheses) / total_claims
    overclaim_rate       = unmarked_speculation_as_fact / total_claims
    speculative_honesty  = correctly_marked_hypotheses / (correctly_marked + unmarked_hypotheses)

    Assumptions NEVER enter total_claims.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from backend.pipeline.gateway.claim_types import (
    CLAIM_SUPPORT_REQUIREMENTS,
    CLAIM_TYPE_VALUES,
    ClaimType,
    DesignAssumption,
    detect_benefit_phrases,
    get_support_requirement,
    is_type_allowed_in_section,
    must_cite,
    must_mark_speculative,
)

logger = logging.getLogger(__name__)


# ── Classifications ──────────────────────────────────────────────────────

class ClaimClassification(str, Enum):
    """Epistemic classification of a claim after validation."""

    SUPPORTED = "supported"                      # Evidence supports the claim
    DESIGN_JUSTIFIED = "design_justified"         # No corpus needed, design rationale valid
    CORRECTLY_MARKED_HYPOTHESIS = "correctly_marked_hypothesis"  # Speculative + marked
    UNMARKED_SPECULATION = "unmarked_speculation" # Speculative content presented as fact
    UNSUPPORTED_OVERCLAIM = "unsupported_overclaim"  # Unsupported + not marked speculative
    CONTRADICTED = "contradicted"                  # Evidence contradicts (override for ALL types)
    TYPE_MISMATCH = "type_mismatch"               # Claim type not allowed in section
    MISSING_CITATION = "missing_citation"          # Required citation absent


# ── Repair Recommendations ───────────────────────────────────────────────

class RepairRecommendation(str, Enum):
    """What the repair loop should do with this claim."""

    KEEP = "keep"
    MARK_SPECULATIVE = "mark_speculative"    # Add speculative marker
    RECLASSIFY = "reclassify"                 # Change claim type
    SPLIT = "split"                           # Split into mechanism + benefit
    ADD_CITATION = "add_citation"             # Find and add missing citation
    QUALIFY_LANGUAGE = "qualify_language"     # Soften language
    REMOVE = "remove"                         # Cannot be repaired
    NONE = "none"                             # No action needed


# ── Validated Claim ──────────────────────────────────────────────────────

@dataclass
class ValidatedClaim:
    """A claim after type-aware validation.

    classification and recommendation are set by the validator.
    The repair loop reads recommendation and mutates accordingly.
    """

    claim_id: str
    text: str
    declared_type: str
    section: str
    evidence_ids: list[str]
    speculative: bool
    rationale: str = ""

    # Set by validator
    classification: ClaimClassification = ClaimClassification.SUPPORTED
    recommendation: RepairRecommendation = RepairRecommendation.NONE
    issues: list[str] = field(default_factory=list)

    # For split recommendations
    split_claims: list[dict] = field(default_factory=list)

    # Contradiction evidence
    contradicted_by: list[str] = field(default_factory=list)

    # Evidence support level
    support_level: str = "none"  # "strong" | "weak" | "none" | "contradicted"

    @property
    def is_valid(self) -> bool:
        return self.classification in (
            ClaimClassification.SUPPORTED,
            ClaimClassification.DESIGN_JUSTIFIED,
            ClaimClassification.CORRECTLY_MARKED_HYPOTHESIS,
        )

    @property
    def is_overclaim(self) -> bool:
        return self.classification in (
            ClaimClassification.UNMARKED_SPECULATION,
            ClaimClassification.UNSUPPORTED_OVERCLAIM,
        )

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "text": self.text[:200],
            "declared_type": self.declared_type,
            "section": self.section,
            "classification": self.classification.value,
            "recommendation": self.recommendation.value,
            "is_valid": self.is_valid,
            "is_overclaim": self.is_overclaim,
            "issues": self.issues,
            "support_level": self.support_level,
        }


# ── Metrics ──────────────────────────────────────────────────────────────

@dataclass
class EpistemicMetrics:
    """Three-metric model — computed ONLY from ValidatedClaim list.

    Assumptions NEVER appear in any denominator.
    """

    direct_support_rate: float = 0.0
    epistemic_acceptability_rate: float = 0.0
    overclaim_rate: float = 0.0
    speculative_honesty: float = 0.0
    total_claims: int = 0
    supported: int = 0
    design_justified: int = 0
    correctly_marked_hypotheses: int = 0
    unmarked_speculation: int = 0
    unsupported_overclaim: int = 0
    contradicted: int = 0
    type_mismatch: int = 0
    missing_citation: int = 0

    def to_dict(self) -> dict:
        return {
            "direct_support_rate": round(self.direct_support_rate, 3),
            "epistemic_acceptability_rate": round(self.epistemic_acceptability_rate, 3),
            "overclaim_rate": round(self.overclaim_rate, 3),
            "speculative_honesty": round(self.speculative_honesty, 3),
            "total_claims": self.total_claims,
            "breakdown": {
                "supported": self.supported,
                "design_justified": self.design_justified,
                "correctly_marked_hypotheses": self.correctly_marked_hypotheses,
                "unmarked_speculation": self.unmarked_speculation,
                "unsupported_overclaim": self.unsupported_overclaim,
                "contradicted": self.contradicted,
                "type_mismatch": self.type_mismatch,
                "missing_citation": self.missing_citation,
            },
        }


def compute_metrics(claims: list[ValidatedClaim]) -> EpistemicMetrics:
    """Compute epistemic metrics from validated claims.

    CRITICAL: Only ValidatedClaim items (ClaimType-derived) enter the denominator.
    DesignAssumption items are NEVER passed here.
    """
    if not claims:
        return EpistemicMetrics()

    m = EpistemicMetrics(total_claims=len(claims))

    for c in claims:
        cls = c.classification
        if cls == ClaimClassification.SUPPORTED:
            m.supported += 1
        elif cls == ClaimClassification.DESIGN_JUSTIFIED:
            m.design_justified += 1
        elif cls == ClaimClassification.CORRECTLY_MARKED_HYPOTHESIS:
            m.correctly_marked_hypotheses += 1
        elif cls == ClaimClassification.UNMARKED_SPECULATION:
            m.unmarked_speculation += 1
        elif cls == ClaimClassification.UNSUPPORTED_OVERCLAIM:
            m.unsupported_overclaim += 1
        elif cls == ClaimClassification.CONTRADICTED:
            m.contradicted += 1
        elif cls == ClaimClassification.TYPE_MISMATCH:
            m.type_mismatch += 1
        elif cls == ClaimClassification.MISSING_CITATION:
            m.missing_citation += 1

    total = m.total_claims

    # direct_support_rate: only fully supported claims
    m.direct_support_rate = m.supported / total

    # epistemic_acceptability: supported + design_justified + correctly marked hypotheses
    epistemic_ok = m.supported + m.design_justified + m.correctly_marked_hypotheses
    m.epistemic_acceptability_rate = epistemic_ok / total

    # overclaim_rate: unmarked speculation as fact + unsupported overclaim
    m.overclaim_rate = (m.unmarked_speculation + m.unsupported_overclaim) / total

    # speculative_honesty: correctly marked / (correctly marked + unmarked)
    total_speculative = m.correctly_marked_hypotheses + m.unmarked_speculation
    if total_speculative > 0:
        m.speculative_honesty = m.correctly_marked_hypotheses / total_speculative
    else:
        m.speculative_honesty = 1.0  # No speculative claims = honest by default

    return m


# ── Validator ────────────────────────────────────────────────────────────

class ClaimTypeValidator:
    """Validate declared claim types against section contracts.

    The validator:
    1. Checks type is allowed in the section
    2. Checks speculative marking where required
    3. Checks citation requirements
    4. Checks benefit-smuggling (mechanism claims with benefit keywords)
    5. Applies contradiction override (ALL types including hypotheses)
    6. Classifies each claim
    7. Recommends repair action

    The validator does NOT mutate claims. It only classifies and recommends.
    """

    def validate_claim(
        self,
        claim: dict,
        section: str,
        support_level: str = "none",
        contradicted_by: list[str] | None = None,
    ) -> ValidatedClaim:
        """Validate a single claim and return classification + recommendation.

        Args:
            claim: Dict with keys: claim_id, text, type, evidence_ids, speculative
            section: Section identifier
            support_level: "strong" | "weak" | "none" | "contradicted"
            contradicted_by: Source IDs that contradict this claim
        """
        claim_id = claim.get("claim_id", "UNKNOWN")
        text = claim.get("text", "")
        declared_type = claim.get("type", "")
        evidence_ids = claim.get("evidence_ids", [])
        speculative = claim.get("speculative", False)
        rationale = claim.get("rationale", "")

        vc = ValidatedClaim(
            claim_id=claim_id,
            text=text,
            declared_type=declared_type,
            section=section,
            evidence_ids=evidence_ids,
            speculative=speculative,
            rationale=rationale,
            support_level=support_level,
            contradicted_by=contradicted_by or [],
        )

        # ── Rule 0: Contradiction override (applies to ALL types) ──
        if support_level == "contradicted" or (contradicted_by and len(contradicted_by) > 0):
            vc.classification = ClaimClassification.CONTRADICTED
            vc.recommendation = RepairRecommendation.REMOVE
            vc.issues.append(
                f"CONTRADICTION OVERRIDE: Claim contradicted by evidence {contradicted_by}. "
                f"Applies to all types including hypotheses."
            )
            return vc

        # ── Rule 1: Type allowed in section? ──
        if not is_type_allowed_in_section(declared_type, section):
            vc.classification = ClaimClassification.TYPE_MISMATCH
            vc.recommendation = RepairRecommendation.RECLASSIFY
            vc.issues.append(
                f"Type '{declared_type}' not allowed in section '{section}'"
            )
            return vc

        # ── Rule 2: Benefit smuggling check ──
        if declared_type == ClaimType.METHOD_PROPOSED_MECHANISM.value:
            has_hard, has_soft, matched = detect_benefit_phrases(text)
            if has_hard:
                # Auto-split: mechanism claim contains benefit keywords
                vc.classification = ClaimClassification.UNMARKED_SPECULATION
                vc.recommendation = RepairRecommendation.SPLIT
                vc.issues.append(
                    f"BENEFIT SMUGGLING: Mechanism claim contains benefit keywords: {matched}. "
                    f"Must split into method_proposed_mechanism + method_claimed_benefit."
                )
                # Provide split recommendation
                vc.split_claims = self._generate_split(claim, matched)
                return vc
            elif has_soft:
                vc.issues.append(
                    f"SOFT BENEFIT WARNING: Possible benefit phrases: {matched}. "
                    f"Consider splitting."
                )

        # ── Rule 3: Speculative marking required? ──
        if must_mark_speculative(declared_type, section) and not speculative:
            # Speculative content presented as fact
            vc.classification = ClaimClassification.UNMARKED_SPECULATION
            vc.recommendation = RepairRecommendation.MARK_SPECULATIVE
            vc.issues.append(
                f"Type '{declared_type}' in section '{section}' must be marked speculative"
            )
            return vc

        # ── Rule 4: Citation required? ──
        if must_cite(declared_type, section) and not evidence_ids:
            vc.classification = ClaimClassification.MISSING_CITATION
            vc.recommendation = RepairRecommendation.ADD_CITATION
            vc.issues.append(
                f"Type '{declared_type}' in section '{section}' requires citation"
            )
            return vc

        # ── Rule 5: Support level classification ──
        req = get_support_requirement(declared_type)
        min_support = req.get("min_support", "none")
        corpus_required = req.get("corpus_required", False)

        if support_level == "strong":
            vc.classification = ClaimClassification.SUPPORTED
            vc.recommendation = RepairRecommendation.KEEP
        elif support_level == "weak":
            if min_support == "strong":
                # Required strong, only got weak → qualify
                vc.classification = ClaimClassification.SUPPORTED
                vc.recommendation = RepairRecommendation.QUALIFY_LANGUAGE
                vc.issues.append("Support weaker than required — qualifying language recommended")
            else:
                # weak is acceptable
                vc.classification = ClaimClassification.SUPPORTED
                vc.recommendation = RepairRecommendation.KEEP
        elif support_level == "none":
            if speculative:
                # Speculative claim with no evidence — check if correctly marked
                if declared_type in (
                    ClaimType.HYPOTHESIS.value,
                    ClaimType.EXPECTED_CONTRIBUTION.value,
                    ClaimType.METHOD_CLAIMED_BENEFIT.value,
                ):
                    vc.classification = ClaimClassification.CORRECTLY_MARKED_HYPOTHESIS
                    vc.recommendation = RepairRecommendation.KEEP
                    vc.issues.append("Correctly marked speculative claim")
                else:
                    vc.classification = ClaimClassification.DESIGN_JUSTIFIED
                    vc.recommendation = RepairRecommendation.KEEP
                    vc.issues.append("Design-justified claim (no corpus required)")
            else:
                if corpus_required:
                    # Needs corpus support but has none and isn't speculative
                    vc.classification = ClaimClassification.UNSUPPORTED_OVERCLAIM
                    vc.recommendation = RepairRecommendation.REMOVE
                    vc.issues.append(
                        f"Type '{declared_type}' requires corpus support but has none"
                    )
                else:
                    vc.classification = ClaimClassification.DESIGN_JUSTIFIED
                    vc.recommendation = RepairRecommendation.KEEP
                    vc.issues.append("No corpus required for this type")

        return vc

    def validate_section(
        self,
        section_id: str,
        claims: list[dict],
        support_levels: dict[str, str] | None = None,
        contradictions: dict[str, list[str]] | None = None,
    ) -> list[ValidatedClaim]:
        """Validate all claims in a section.

        Args:
            section_id: Section identifier
            claims: List of claim dicts
            support_levels: claim_id -> support_level mapping
            contradictions: claim_id -> [contradicting source IDs] mapping
        """
        support_levels = support_levels or {}
        contradictions = contradictions or {}

        validated = []
        for claim in claims:
            cid = claim.get("claim_id", "UNKNOWN")
            vc = self.validate_claim(
                claim=claim,
                section=section_id,
                support_level=support_levels.get(cid, "none"),
                contradicted_by=contradictions.get(cid),
            )
            validated.append(vc)

        return validated

    @staticmethod
    def _generate_split(claim: dict, benefit_keywords: list[str]) -> list[dict]:
        """Generate recommended split claims.

        Splits a mechanism+benefit claim into:
        1. Pure mechanism (method_proposed_mechanism)
        2. Benefit as hypothesis (method_claimed_benefit, speculative=true)
        """
        text = claim.get("text", "")
        claim_id = claim.get("claim_id", "UNKNOWN")

        # Find where the benefit phrase starts
        split_point = len(text)
        for kw in benefit_keywords:
            idx = text.lower().find(kw.lower())
            if idx > 0:
                split_point = idx
                break

        mechanism_text = text[:split_point].strip().rstrip(",;")
        benefit_text = text[split_point:].strip()

        if not mechanism_text:
            mechanism_text = text
            benefit_text = f"[Auto-extracted benefit from: {text}]"

        return [
            {
                "claim_id": f"{claim_id}-mechanism",
                "text": mechanism_text,
                "type": ClaimType.METHOD_PROPOSED_MECHANISM.value,
                "evidence_ids": claim.get("evidence_ids", []),
                "speculative": False,
                "rationale": "Split from combined mechanism+benefit claim",
            },
            {
                "claim_id": f"{claim_id}-benefit",
                "text": benefit_text,
                "type": ClaimType.METHOD_CLAIMED_BENEFIT.value,
                "evidence_ids": [],
                "speculative": True,
                "rationale": "Benefit claim extracted from mechanism description",
            },
        ]

    def validate_and_compute_metrics(
        self,
        section_id: str,
        claims: list[dict],
        support_levels: dict[str, str] | None = None,
        contradictions: dict[str, list[str]] | None = None,
    ) -> tuple[list[ValidatedClaim], EpistemicMetrics]:
        """Validate claims and compute metrics in one call."""
        validated = self.validate_section(section_id, claims, support_levels, contradictions)
        metrics = compute_metrics(validated)
        return validated, metrics
