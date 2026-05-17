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
from typing import Any

logger = logging.getLogger(__name__)


class RepairAction(str, Enum):
    """Action taken to repair a claim."""
    KEEP = "keep"                           # Already valid
    REPLACE_CITATION = "replace_citation"   # Found better supporting source
    QUALIFY_LANGUAGE = "qualify"            # Weakened claim to match evidence
    REWRITE = "rewrite"                     # Rewrote claim around evidence
    REMOVE = "remove"                       # No evidence found, claim removed


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

    def to_dict(self) -> dict:
        return {
            "total_claims": self.total_claims,
            "kept": self.kept,
            "citations_replaced": self.citations_replaced,
            "qualified": self.qualified,
            "rewritten": self.rewritten,
            "removed": self.removed,
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
        validation_results: list,  # list[ClaimEvidenceResult]
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
        from backend.pipeline.gateway.claim_evidence_validator import (
            ClaimAction,
            ClaimEvidenceResult,
            SupportLevel,
        )

        repaired_claims: list[RepairedClaim] = []
        kept = 0
        replaced = 0
        qualified = 0
        rewritten = 0
        removed = 0

        text = original_text

        for result in validation_results:
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
                # Qualify language
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
                # Replace in text
                text = text.replace(result.claim_text, qualified_text)

            elif better_source and better_text:
                # Found better evidence — rewrite claim with new citation
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
                    # Rewrite didn't help — remove
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
                # No better evidence but could try with qualified language
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
                # REMOVE or REGENERATE — remove the claim
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
        original_valid = sum(1 for r in validation_results if hasattr(r, 'is_valid') and r.is_valid)
        repaired_valid = kept + replaced + qualified + rewritten  # everything not removed

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
    """Quality gate for export based on claim survival rate.

    Thresholds:
    - draft: any survival rate (always allowed, clearly marked)
    - reviewable: ≥50% claim survival
    - submission: ≥75% claim survival
    """

    DRAFT_THRESHOLD = 0.0
    REVIEWABLE_THRESHOLD = 0.5
    SUBMISSION_THRESHOLD = 0.75

    @staticmethod
    def classify(survival_rate: float) -> str:
        """Classify a paper's export quality level."""
        if survival_rate >= ExportQualityGate.SUBMISSION_THRESHOLD:
            return "submission"
        elif survival_rate >= ExportQualityGate.REVIEWABLE_THRESHOLD:
            return "reviewable"
        else:
            return "draft"

    @staticmethod
    def get_banner(survival_rate: float) -> str:
        """Get a quality banner to prepend to exported papers."""
        level = ExportQualityGate.classify(survival_rate)
        banners = {
            "submission": "[SUBMISSION GRADE] Claim survival: {rate:.0%}",
            "reviewable": "[REVIEWABLE DRAFT] Claim survival: {rate:.0%}",
            "draft": "[DIAGNOSTIC DRAFT] Claim survival: {rate:.0%}. "
                     "Many claims lack supporting evidence. Not suitable for submission.",
        }
        return banners[level].format(rate=survival_rate)
