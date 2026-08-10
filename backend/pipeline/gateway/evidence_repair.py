"""Evidence repair loop — fix unsupported claims after validation.

After ClaimEvidenceValidator flags claims as unsupported/weak/contradicted,
this module attempts to repair them by:

1. Searching the corpus for better supporting evidence
2. Rewriting the claim to match available evidence
3. Removing claims that cannot be supported
4. Qualifying language for weakly-supported claims

Design principle: never fabricate support. If no evidence exists, remove.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RepairAction(str, Enum):
    """Action taken to repair a claim."""
    KEEP = "keep"                           # Already valid
    REPLACE_CITATION = "replace_citation"   # Found better supporting source
    QUALIFY_LANGUAGE = "qualify"            # Weakened claim to match evidence
    REWRITE = "rewrite"                     # Rewrote claim around evidence
    REMOVE = "remove"                       # No evidence found, claim removed
    MARK_SPECULATIVE = "mark_speculative"   # Added speculative marker to unmarked claim
    RECLASSIFY = "reclassify"               # Changed claim type (e.g., mechanism→hypothesis)
    SPLIT = "split"                         # Split mechanism+benefit into two claims


@dataclass
class RepairedClaim:
    """A claim after the repair loop."""

    original_claim_id: str
    original_text: str
    repaired_text: str
    action: RepairAction
    original_citations: list[str]
    new_citations: list[str]
    original_support: str
    new_support: str
    original_confidence: float
    new_confidence: float
    repair_reason: str

    @property
    def was_improved(self) -> bool:
        return self.new_confidence > self.original_confidence

    def to_dict(self) -> dict:
        return {
            "claim_id": self.original_claim_id,
            "action": self.action.value,
            "original_confidence": round(self.original_confidence, 2),
            "new_confidence": round(self.new_confidence, 2),
            "improved": self.was_improved,
            "repair_reason": self.repair_reason,
        }


@dataclass
class RepairReport:
    """Report from the evidence repair loop."""

    total_claims: int
    kept: int
    citations_replaced: int
    qualified: int
    rewritten: int
    removed: int
    original_survival_rate: float
    repaired_survival_rate: float
    repaired_text: str
    claims: list[RepairedClaim] = field(default_factory=list)
    # Type-aware repair counts
    marked_speculative: int = 0
    reclassified: int = 0
    split: int = 0

    def to_dict(self) -> dict:
        return {
            "total_claims": self.total_claims,
            "kept": self.kept,
            "citations_replaced": self.citations_replaced,
            "qualified": self.qualified,
            "rewritten": self.rewritten,
            "removed": self.removed,
            "marked_speculative": self.marked_speculative,
            "reclassified": self.reclassified,
            "split": self.split,
            "original_survival_rate": round(self.original_survival_rate, 3),
            "repaired_survival_rate": round(self.repaired_survival_rate, 3),
            "improvement": round(self.repaired_survival_rate - self.original_survival_rate, 3),
        }


@dataclass
class EvidenceCard:
    """A structured evidence item for closed-set citation."""

    evidence_id: str
    title: str
    abstract: str
    key_findings: list[str]
    relevant_sections: list[str]  # which paper sections this is relevant for


class EvidenceRepairLoop:
    """Repair unsupported claims by searching corpus and rewriting.

    Usage:
        repair = EvidenceRepairLoop(corpus_texts={"PAPER_001": "...", "PAPER_022": "..."})
        report = repair.repair(validation_results, original_text)
    """

    def __init__(
        self,
        corpus_texts: dict[str, str] | None = None,
    ):
        self._corpus = corpus_texts or {}

    def set_corpus(self, texts: dict[str, str]) -> None:
        """Update the corpus texts."""
        self._corpus = texts

    def repair(
        self,
        validation_results: list,  # list[ClaimEvidenceResult] or list[ValidatedClaim]
        original_text: str,
    ) -> RepairReport:
        """Run the repair loop on validation results.

        For each claim:
        - If KEEP → pass through
        - If KEEP_WITH_WARNING → try to qualify language
        - If REWRITE → search for better evidence, rewrite
        - If REMOVE → search for evidence; if found, rewrite; if not, remove
        - If REGENERATE → search for evidence; if found, rewrite; if not, remove

        Returns:
            RepairReport with per-claim repairs and updated text.
        """
        # Import both old (ClaimEvidenceResult) and new (ValidatedClaim) types
        from backend.pipeline.gateway.claim_type_validator import (
            ValidatedClaim,
        )

        repaired_claims: list[RepairedClaim] = []
        kept = 0
        replaced = 0
        qualified = 0
        rewritten = 0
        removed = 0
        marked_speculative = 0
        reclassified = 0
        split = 0

        text = original_text

        for result in validation_results:
            # ── Handle ValidatedClaim (type-aware path) ──
            if isinstance(result, ValidatedClaim):
                rc = self._repair_validated_claim(result, text)
                if rc is not None:
                    repaired_claims.append(rc)
                    text = self._apply_repair_to_text(text, result, rc)
                    # Track action counts
                    action = rc.action
                    if action == RepairAction.KEEP:
                        kept += 1
                    elif action == RepairAction.MARK_SPECULATIVE:
                        marked_speculative += 1
                    elif action == RepairAction.RECLASSIFY:
                        reclassified += 1
                    elif action == RepairAction.SPLIT:
                        split += 1
                    elif action == RepairAction.QUALIFY_LANGUAGE:
                        qualified += 1
                    elif action == RepairAction.REMOVE:
                        removed += 1
                    elif action == RepairAction.REWRITE:
                        rewritten += 1
                continue

            # ── Handle legacy ClaimEvidenceResult ──
            from backend.pipeline.gateway.claim_evidence_validator import (
                ClaimAction,
                ClaimEvidenceResult,
            )

            if not isinstance(result, ClaimEvidenceResult):
                continue

            if result.recommended_action in (ClaimAction.KEEP,):
                kept += 1
                repaired_claims.append(RepairedClaim(
                    original_claim_id=result.claim_id,
                    original_text=result.claim_text,
                    repaired_text=result.claim_text,
                    action=RepairAction.KEEP,
                    original_citations=result.cited_sources,
                    new_citations=result.cited_sources,
                    original_support=result.support.value,
                    new_support=result.support.value,
                    original_confidence=result.confidence,
                    new_confidence=result.confidence,
                    repair_reason="Already valid",
                ))
                continue

            # Try to find better supporting evidence
            better_source, better_text = self._find_supporting_evidence(
                result.claim_text, result.cited_sources,
            )

            if result.recommended_action == ClaimAction.KEEP_WITH_WARNING:
                qualified_text = self._qualify_language(result.claim_text)
                qualified += 1
                repaired_claims.append(RepairedClaim(
                    original_claim_id=result.claim_id,
                    original_text=result.claim_text,
                    repaired_text=qualified_text,
                    action=RepairAction.QUALIFY_LANGUAGE,
                    original_citations=result.cited_sources,
                    new_citations=result.cited_sources,
                    original_support=result.support.value,
                    new_support="qualified",
                    original_confidence=result.confidence,
                    new_confidence=min(result.confidence + 0.1, 0.7),
                    repair_reason="Qualified claim language to match evidence strength",
                ))
                text = text.replace(result.claim_text, qualified_text)

            elif better_source and better_text:
                rewritten_text = self._rewrite_with_evidence(
                    result.claim_text, better_source, better_text,
                )
                if rewritten_text != result.claim_text:
                    rewritten += 1
                    repaired_claims.append(RepairedClaim(
                        original_claim_id=result.claim_id,
                        original_text=result.claim_text,
                        repaired_text=rewritten_text,
                        action=RepairAction.REWRITE,
                        original_citations=result.cited_sources,
                        new_citations=[better_source],
                        original_support=result.support.value,
                        new_support="strong",
                        original_confidence=result.confidence,
                        new_confidence=0.7,
                        repair_reason=f"Found supporting evidence: {better_source}",
                    ))
                    text = text.replace(result.claim_text, rewritten_text)
                else:
                    text = self._remove_claim(text, result.claim_text)
                    removed += 1
                    repaired_claims.append(RepairedClaim(
                        original_claim_id=result.claim_id,
                        original_text=result.claim_text,
                        repaired_text="[removed]",
                        action=RepairAction.REMOVE,
                        original_citations=result.cited_sources,
                        new_citations=[],
                        original_support=result.support.value,
                        new_support="none",
                        original_confidence=result.confidence,
                        new_confidence=0.0,
                        repair_reason="No supporting evidence found after rewrite attempt",
                    ))
            elif result.recommended_action == ClaimAction.REWRITE:
                qualified_text = self._qualify_language(result.claim_text)
                if qualified_text != result.claim_text:
                    qualified += 1
                    repaired_claims.append(RepairedClaim(
                        original_claim_id=result.claim_id,
                        original_text=result.claim_text,
                        repaired_text=qualified_text,
                        action=RepairAction.QUALIFY_LANGUAGE,
                        original_citations=result.cited_sources,
                        new_citations=result.cited_sources,
                        original_support=result.support.value,
                        new_support="qualified",
                        original_confidence=result.confidence,
                        new_confidence=result.confidence + 0.05,
                        repair_reason="No better evidence found; qualified claim language",
                    ))
                    text = text.replace(result.claim_text, qualified_text)
                else:
                    text = self._remove_claim(text, result.claim_text)
                    removed += 1
                    repaired_claims.append(RepairedClaim(
                        original_claim_id=result.claim_id,
                        original_text=result.claim_text,
                        repaired_text="[removed]",
                        action=RepairAction.REMOVE,
                        original_citations=result.cited_sources,
                        new_citations=[],
                        original_support=result.support.value,
                        new_support="none",
                        original_confidence=result.confidence,
                        new_confidence=0.0,
                        repair_reason="No supporting evidence found, could not qualify",
                    ))
            else:
                text = self._remove_claim(text, result.claim_text)
                removed += 1
                repaired_claims.append(RepairedClaim(
                    original_claim_id=result.claim_id,
                    original_text=result.claim_text,
                    repaired_text="[removed]",
                    action=RepairAction.REMOVE,
                    original_citations=result.cited_sources,
                    new_citations=[],
                    original_support=result.support.value,
                    new_support="none",
                    original_confidence=result.confidence,
                    new_confidence=0.0,
                    repair_reason="No supporting evidence found in corpus",
                ))

        # Calculate survival rates
        total = max(len(validation_results), 1)
        original_valid = sum(
            1 for r in validation_results
            if hasattr(r, 'is_valid') and r.is_valid
        )
        repaired_valid = kept + replaced + qualified + rewritten + marked_speculative + reclassified

        return RepairReport(
            total_claims=total,
            kept=kept,
            citations_replaced=replaced,
            qualified=qualified,
            rewritten=rewritten,
            removed=removed,
            original_survival_rate=original_valid / total,
            repaired_survival_rate=repaired_valid / total,
            repaired_text=text,
            claims=repaired_claims,
        )

    def _repair_validated_claim(
        self,
        vc: ValidatedClaim,
        text: str,
    ) -> RepairedClaim | None:
        """Repair a ValidatedClaim based on its recommendation.

        The validator classified and recommended. This method acts.
        """
        from backend.pipeline.gateway.claim_type_validator import (
            ClaimClassification,
            RepairRecommendation,
        )

        base = RepairedClaim(
            original_claim_id=vc.claim_id,
            original_text=vc.text,
            repaired_text=vc.text,
            action=RepairAction.KEEP,
            original_citations=vc.evidence_ids,
            new_citations=vc.evidence_ids,
            original_support=vc.support_level,
            new_support=vc.support_level,
            original_confidence=0.5,
            new_confidence=0.5,
            repair_reason="",
        )

        rec = vc.recommendation

        if rec == RepairRecommendation.KEEP:
            base.repair_reason = "Valid claim"
            base.new_confidence = 0.8 if vc.is_valid else 0.5
            return base

        elif rec == RepairRecommendation.MARK_SPECULATIVE:
            base.action = RepairAction.MARK_SPECULATIVE
            base.repaired_text = self._add_speculative_marker(vc.text, vc.declared_type)
            base.new_support = "speculative"
            base.new_confidence = 0.4
            base.repair_reason = (
                f"Marked as speculative (type={vc.declared_type}, section={vc.section})"
            )
            return base

        elif rec == RepairRecommendation.RECLASSIFY:
            base.action = RepairAction.RECLASSIFY
            # Default reclassification: downgrade to hypothesis
            base.repaired_text = f"We hypothesize that {vc.text[0].lower()}{vc.text[1:]}"
            base.new_support = "reclassified"
            base.new_confidence = 0.3
            base.repair_reason = (
                f"Reclassified from {vc.declared_type} — type not allowed in {vc.section}"
            )
            return base

        elif rec == RepairRecommendation.SPLIT:
            base.action = RepairAction.SPLIT
            if vc.split_claims and len(vc.split_claims) >= 2:
                mechanism = vc.split_claims[0]
                benefit = vc.split_claims[1]
                base.repaired_text = (
                    f"{mechanism['text']} "
                    f"We hypothesize that {benefit['text'][0].lower()}{benefit['text'][1:]}"
                )
            else:
                base.repaired_text = self._add_speculative_marker(vc.text, vc.declared_type)
            base.new_support = "split"
            base.new_confidence = 0.5
            base.repair_reason = "Split mechanism+benefit into separate claims"
            return base

        elif rec == RepairRecommendation.ADD_CITATION:
            # Try to find a citation
            better_source, better_text = self._find_supporting_evidence(
                vc.text, vc.evidence_ids,
            )
            if better_source:
                base.action = RepairAction.REPLACE_CITATION
                base.repaired_text = f"{vc.text} [{better_source}]"
                base.new_citations = [better_source]
                base.new_support = "weak"
                base.new_confidence = 0.5
                base.repair_reason = f"Added citation: {better_source}"
            else:
                base.action = RepairAction.QUALIFY_LANGUAGE
                base.repaired_text = self._qualify_language(vc.text)
                base.new_support = "qualified"
                base.new_confidence = 0.3
                base.repair_reason = "No citation found; qualified language instead"
            return base

        elif rec == RepairRecommendation.QUALIFY_LANGUAGE:
            base.action = RepairAction.QUALIFY_LANGUAGE
            base.repaired_text = self._qualify_language(vc.text)
            base.new_support = "qualified"
            base.new_confidence = 0.4
            base.repair_reason = "Qualified language to match evidence strength"
            return base

        elif rec == RepairRecommendation.REMOVE:
            base.action = RepairAction.REMOVE
            base.repaired_text = "[removed]"
            base.new_citations = []
            base.new_support = "none"
            base.new_confidence = 0.0
            reason = "Removed: "
            if vc.classification == ClaimClassification.CONTRADICTED:
                reason += f"contradicted by {vc.contradicted_by}"
            elif vc.classification == ClaimClassification.UNSUPPORTED_OVERCLAIM:
                reason += "unsupported overclaim, no evidence found"
            else:
                reason += "cannot be repaired"
            base.repair_reason = reason
            return base

        else:
            # NONE or unknown
            base.repair_reason = "No action needed"
            return base

    @staticmethod
    def _add_speculative_marker(text: str, claim_type: str) -> str:
        """Add appropriate speculative marker based on claim type."""
        from backend.pipeline.gateway.claim_types import ClaimType

        prefix_map = {
            ClaimType.METHOD_CLAIMED_BENEFIT.value: "We hypothesize that",
            ClaimType.HYPOTHESIS.value: "We hypothesize that",
            ClaimType.EXPECTED_CONTRIBUTION.value: "We aim to",
        }

        prefix = prefix_map.get(claim_type, "We hypothesize that")

        # Don't double-prefix
        if text.lower().startswith(prefix.lower()):
            return text

        # Strip existing sentence-starting words
        text = text.strip()
        if text and text[0].isupper():
            text = text[0].lower() + text[1:]

        return f"{prefix} {text}"

    @staticmethod
    def _apply_repair_to_text(
        text: str,
        vc: ValidatedClaim,
        rc: RepairedClaim,
    ) -> str:
        """Apply a repair to the full text."""
        if rc.action == RepairAction.REMOVE:
            return EvidenceRepairLoop._remove_claim(text, vc.text)
        elif rc.action == RepairAction.KEEP:
            return text
        else:
            return text.replace(vc.text, rc.repaired_text)

    def _find_supporting_evidence(
        self,
        claim_text: str,
        existing_citations: list[str],
    ) -> tuple[str | None, str | None]:
        """Search corpus for evidence that better supports the claim.

        Returns:
            (source_id, source_text) or (None, None) if nothing found.
        """
        if not self._corpus:
            return None, None

        claim_words = set(claim_text.lower().split())
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "can", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "into", "about",
            "that", "this", "it", "its", "their", "they", "we", "our",
            "which", "who", "and", "or", "not", "but", "if", "then",
        }
        claim_keywords = claim_words - stop_words

        best_score = 0.0
        best_source = None
        best_text = None

        for source_id, source_text in self._corpus.items():
            # Skip already-cited sources
            clean_id = source_id.strip("[]()")
            for cite in existing_citations:
                if clean_id in cite or cite.strip("[]()") in clean_id:
                    continue

            source_words = set(source_text.lower().split())
            source_keywords = source_words - stop_words

            if not claim_keywords:
                continue

            overlap = claim_keywords & source_keywords
            score = len(overlap) / len(claim_keywords)

            if score > best_score and score >= 0.3:
                best_score = score
                best_source = source_id
                best_text = source_text[:500]

        return best_source, best_text

    @staticmethod
    def _qualify_language(claim_text: str) -> str:
        """Soften unsupported claims with qualifying language.

        Replaces definitive statements with qualified ones:
        - "X causes Y" → "X may contribute to Y"
        - "X proves Y" → "X suggests Y"
        - "X demonstrates Y" → "X indicates Y"
        """
        qualified = claim_text

        softening = [
            (r'\bcauses\b', 'may contribute to'),
            (r'\bproves\b', 'suggests'),
            (r'\bdemonstrates\b', 'indicates'),
            (r'\bestablishes\b', 'suggests'),
            (r'\bconfirms\b', 'supports'),
            (r'\bclearly\b', 'potentially'),
            (r'\bobviously\b', 'arguably'),
            (r'\bdefinitively\b', 'potentially'),
            (r'\bsignificantly\b', 'potentially'),
            (r'\bwill\b(?! be)', 'may'),
            (r'\bmust\b', 'might'),
            (r'\balways\b', 'often'),
            (r'\bnever\b', 'rarely'),
        ]

        for pattern, replacement in softening:
            qualified = re.sub(pattern, replacement, qualified, count=1, flags=re.IGNORECASE)

        return qualified

    @staticmethod
    def _rewrite_with_evidence(
        claim_text: str,
        evidence_id: str,
        evidence_text: str,
    ) -> str:
        """Rewrite a claim to incorporate the new evidence.

        Simple approach: replace old citations with the new one and
        add a qualifying prefix.
        """
        # Remove old citations
        cleaned = re.sub(r'\[SOURCE-\d+\]', '', claim_text).strip()
        cleaned = re.sub(r'\s+', ' ', cleaned)

        # Append new citation
        rewritten = f"{cleaned} [{evidence_id}]"

        return rewritten

    @staticmethod
    def _remove_claim(text: str, claim_text: str) -> str:
        """Remove a claim from text, cleaning up the resulting gap."""
        # Find the sentence containing this claim
        # Look for the first ~50 chars to locate it
        marker = claim_text[:50]
        idx = text.find(marker)
        if idx < 0:
            return text

        # Find sentence boundaries
        start = idx
        while start > 0 and text[start - 1] not in '.!?':
            start -= 1
        if start > 0:
            start += 1  # skip the period

        end = text.find('.', idx + len(marker))
        if end < 0:
            end = idx + len(claim_text)
        else:
            end += 1  # include the period

        # Remove the sentence and clean up whitespace
        removed = text[:start] + text[end:]
        removed = re.sub(r'\s{3,}', ' ', removed)  # collapse multiple spaces
        return removed.strip()


class ExportQualityGate:
    """Quality gate for export based on three-metric epistemic model.

    CRITICAL INVARIANT: The quality gate consumes validator output (EpistemicMetrics).
    It NEVER recomputes its own metrics. This prevents drift between
    validation and export classification.

    Classification rules (in priority order):
    1. Hard draft gate: overclaim_rate > 0.30 → always "draft"
    2. submission_candidate: epistemic_acceptability >= 0.75 AND direct_support >= 0.50 AND overclaim <= 0.15
    3. reviewable: epistemic_acceptability >= 0.55 AND overclaim <= 0.15
    4. Otherwise: draft
    """

    OVERCLAIM_HARD_GATE = 0.30
    SUBMISSION_EPISTEMIC = 0.75
    SUBMISSION_DIRECT_SUPPORT = 0.50
    SUBMISSION_OVERCLAIM = 0.15
    REVIEWABLE_EPISTEMIC = 0.55
    REVIEWABLE_OVERCLAIM = 0.15

    @staticmethod
    def classify_from_metrics(metrics: EpistemicMetrics) -> str:
        """Classify paper quality from pre-computed EpistemicMetrics.

        This is the PRIMARY classification method. It consumes validator output.
        """
        # Rule 1: Hard draft gate
        if metrics.overclaim_rate > ExportQualityGate.OVERCLAIM_HARD_GATE:
            return "draft"

        # Rule 2: Submission candidate
        if (
            metrics.epistemic_acceptability_rate >= ExportQualityGate.SUBMISSION_EPISTEMIC
            and metrics.direct_support_rate >= ExportQualityGate.SUBMISSION_DIRECT_SUPPORT
            and metrics.overclaim_rate <= ExportQualityGate.SUBMISSION_OVERCLAIM
        ):
            return "submission_candidate"

        # Rule 3: Reviewable
        if (
            metrics.epistemic_acceptability_rate >= ExportQualityGate.REVIEWABLE_EPISTEMIC
            and metrics.overclaim_rate <= ExportQualityGate.REVIEWABLE_OVERCLAIM
        ):
            return "reviewable"

        # Rule 4: Default
        return "draft"

    @staticmethod
    def classify(survival_rate: float) -> str:
        """Legacy classify from survival_rate only (backward compatible).

        Prefer classify_from_metrics() for new code.
        """
        if survival_rate >= ExportQualityGate.SUBMISSION_THRESHOLD:
            return "submission"
        elif survival_rate >= ExportQualityGate.REVIEWABLE_THRESHOLD:
            return "reviewable"
        else:
            return "draft"

    SUBMISSION_THRESHOLD = 0.75
    REVIEWABLE_THRESHOLD = 0.50

    @staticmethod
    def get_banner_from_metrics(metrics: EpistemicMetrics) -> str:
        """Get a quality banner with full three-metric reporting."""
        level = ExportQualityGate.classify_from_metrics(metrics)

        banner_map = {
            "submission_candidate": (
                "[SUBMISSION CANDIDATE] "
                "direct_support={ds:.0%}, epistemic_acceptability={ea:.0%}, "
                "overclaim={oc:.0%}, speculative_honesty={sh:.0%}"
            ),
            "reviewable": (
                "[REVIEWABLE DRAFT] "
                "direct_support={ds:.0%}, epistemic_acceptability={ea:.0%}, "
                "overclaim={oc:.0%}, speculative_honesty={sh:.0%}"
            ),
            "draft": (
                "[DIAGNOSTIC DRAFT] "
                "direct_support={ds:.0%}, epistemic_acceptability={ea:.0%}, "
                "overclaim={oc:.0%}, speculative_honesty={sh:.0%}. "
                "Not suitable for submission without further evidence grounding."
            ),
        }

        template = banner_map.get(level, banner_map["draft"])
        return template.format(
            ds=metrics.direct_support_rate,
            ea=metrics.epistemic_acceptability_rate,
            oc=metrics.overclaim_rate,
            sh=metrics.speculative_honesty,
        )

    @staticmethod
    def get_banner(survival_rate: float) -> str:
        """Legacy banner from survival_rate only."""
        level = ExportQualityGate.classify(survival_rate)
        banners = {
            "submission": "[SUBMISSION GRADE] Claim survival: {rate:.0%}",
            "reviewable": "[REVIEWABLE DRAFT] Claim survival: {rate:.0%}",
            "draft": "[DIAGNOSTIC DRAFT] Claim survival: {rate:.0%}. "
                     "Many claims lack supporting evidence. Not suitable for submission.",
        }
        return banners[level].format(rate=survival_rate)
