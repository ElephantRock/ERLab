"""ClaimEvidenceValidator — a claim survival gate.

Not just a citation checker. This validates that each claim-citation pair
in generated output survives a three-level audit:

Level 1: citation_exists — is this source in the corpus?
Level 2: citation_provided — was this source in the evidence set given to the model?
Level 3: citation_supports_claim — does the cited evidence support the local claim?

Then assigns a recommended action: keep, rewrite, remove, or regenerate.

Design principle: the validator does NOT silently remove bad claims.
It flags them with a recommended action and lets the caller decide.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SupportLevel(str, Enum):
    """How well the evidence supports the claim."""
    STRONG = "strong"
    WEAK = "weak"
    NONE = "none"
    CONTRADICTED = "contradicted"


class ClaimAction(str, Enum):
    """Recommended action for a claim."""
    KEEP = "keep"
    KEEP_WITH_WARNING = "keep_with_warning"
    REWRITE = "rewrite"
    REMOVE = "remove"
    REGENERATE = "regenerate"


@dataclass
class ClaimEvidenceResult:
    """Result of validating a single claim-evidence pair."""

    claim_id: str
    claim_text: str
    cited_sources: list[str]

    # Level 1: existence
    exists: bool = False

    # Level 2: was in evidence set
    was_provided: bool = False

    # Level 3: support judgment
    support: SupportLevel = SupportLevel.NONE
    support_reason: str = ""

    # Overall
    confidence: float = 0.0
    recommended_action: ClaimAction = ClaimAction.REMOVE
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Whether this claim should survive without modification."""
        return self.recommended_action in (ClaimAction.KEEP, ClaimAction.KEEP_WITH_WARNING)

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "claim_text": self.claim_text[:200],
            "cited_sources": self.cited_sources,
            "exists": self.exists,
            "was_provided": self.was_provided,
            "support": self.support.value,
            "confidence": round(self.confidence, 2),
            "recommended_action": self.recommended_action.value,
            "warnings": self.warnings,
        }


@dataclass
class ClaimExtraction:
    """A claim extracted from generated text."""

    claim_id: str
    claim_text: str
    citations: list[str]  # raw citation strings found near the claim
    context: str = ""  # surrounding text for context


@dataclass
class DocumentValidationResult:
    """Result of validating all claims in a document."""

    total_claims: int
    results: list[ClaimEvidenceResult] = field(default_factory=list)
    valid_claims: int = 0
    invalid_claims: int = 0
    needs_rewrite: int = 0
    trust_score: float = 0.0
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "total_claims": self.total_claims,
            "valid_claims": self.valid_claims,
            "invalid_claims": self.invalid_claims,
            "needs_rewrite": self.needs_rewrite,
            "trust_score": round(self.trust_score, 3),
            "summary": self.summary,
            "claims": [r.to_dict() for r in self.results],
        }


class ClaimEvidenceValidator:
    """Validates claim-evidence alignment in generated research artifacts.

    Usage:
        validator = ClaimEvidenceValidator(corpus_ids={"PAPER_001", "PAPER_022"})
        result = validator.validate_document(proposal_text, provided_evidence_ids)
    """

    def __init__(
        self,
        corpus_ids: set[str] | None = None,
    ):
        self._corpus_ids = corpus_ids or set()

    def set_corpus(self, ids: set[str]) -> None:
        """Update the corpus ID set."""
        self._corpus_ids = ids

    def extract_claims(self, text: str) -> list[ClaimExtraction]:
        """Extract claims with their citations from text.

        A claim is a sentence or clause that contains a citation marker.
        Citation patterns recognized:
        - [1], [2], [3] — numbered bracket citations
        - (Author, Year) — author-year citations
        - [PAPER_XXX] — ID-based citations
        """
        claims: list[ClaimExtraction] = []
        claim_id = 0

        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)

        for sentence in sentences:
            # Find bracket citations: [1], [2,3], [PAPER_014]
            bracket_cites = re.findall(r'\[([^\]]+)\]', sentence)

            # Find author-year citations: (Smith et al., 2024)
            author_cites = re.findall(
                r'\(([A-Z][a-z]+(?:\s+(?:et\s+al\.?|and\s+[A-Z][a-z]+))?(?:,\s*\d{4})?)\)',
                sentence,
            )

            all_citations = bracket_cites + author_cites

            if all_citations and len(sentence.strip()) > 10:
                claims.append(ClaimExtraction(
                    claim_id=f"C-{claim_id:03d}",
                    claim_text=sentence.strip(),
                    citations=[f"[{c}]" if not c.startswith("[") else c for c in all_citations],
                    context="",  # Could expand to include surrounding sentences
                ))
                claim_id += 1

        return claims

    def check_level1_exists(self, citation: str) -> bool:
        """Level 1: Does this citation exist in the corpus?

        Checks both the raw citation string and extracted ID.
        """
        # Clean citation to extract ID
        clean = citation.strip("[]()")

        # Check direct match
        if clean in self._corpus_ids:
            return True

        # Check if any corpus ID contains this citation
        for corpus_id in self._corpus_ids:
            if clean in corpus_id or corpus_id in clean:
                return True

        # Check numeric index — [1] might refer to first paper
        if clean.isdigit():
            # Numeric citations need a mapping we don't have here
            # Flag as potentially valid if corpus is non-empty
            return len(self._corpus_ids) > 0

        return False

    def check_level2_provided(
        self,
        citation: str,
        provided_evidence_ids: set[str],
    ) -> bool:
        """Level 2: Was this source in the evidence set given to the model?

        This is the closed-set check. A citation that exists in the corpus
        but wasn't provided as evidence indicates leakage (the model found
        it through training data, not through RAG).
        """
        clean = citation.strip("[]()")

        if clean in provided_evidence_ids:
            return True

        for ev_id in provided_evidence_ids:
            if clean in ev_id or ev_id in clean:
                return True

        return False

    def check_level3_support(
        self,
        claim_text: str,
        citation: str,
        evidence_texts: dict[str, str] | None = None,
    ) -> tuple[SupportLevel, str]:
        """Level 3: Does the cited evidence support the claim?

        Without an LLM call, uses heuristic matching:
        - Keyword overlap between claim and evidence
        - Presence of claim entities in evidence text

        For full support checking, pass evidence_texts and use
        validate_with_llm() instead.
        """
        if not evidence_texts:
            return SupportLevel.NONE, "No evidence text available for support check"

        clean = citation.strip("[]()")

        # Find matching evidence text
        evidence_text = ""
        for ev_id, ev_text in evidence_texts.items():
            if clean in ev_id or ev_id in clean:
                evidence_text = ev_text
                break

        if not evidence_text:
            return SupportLevel.NONE, f"No evidence text found for citation '{clean}'"

        # Heuristic: keyword overlap
        claim_words = set(claim_text.lower().split())
        evidence_words = set(evidence_text.lower().split())

        # Remove common stop words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "can", "shall", "to", "of", "in", "for",
            "on", "with", "at", "by", "from", "as", "into", "about", "that", "this",
            "it", "its", "their", "they", "we", "our", "which", "who", "whom",
        }
        claim_keywords = claim_words - stop_words
        evidence_keywords = evidence_words - stop_words

        if not claim_keywords:
            return SupportLevel.NONE, "No extractable keywords from claim"

        overlap = claim_keywords & evidence_keywords
        overlap_ratio = len(overlap) / len(claim_keywords) if claim_keywords else 0

        if overlap_ratio >= 0.4:
            return SupportLevel.STRONG, f"Strong keyword overlap: {overlap_ratio:.0%} ({len(overlap)} words)"
        elif overlap_ratio >= 0.2:
            return SupportLevel.WEAK, f"Weak keyword overlap: {overlap_ratio:.0%} ({len(overlap)} words)"
        else:
            return SupportLevel.NONE, f"Minimal keyword overlap: {overlap_ratio:.0%} ({len(overlap)} words)"

    def determine_action(
        self,
        exists: bool,
        was_provided: bool,
        support: SupportLevel,
    ) -> tuple[ClaimAction, float]:
        """Determine recommended action and confidence based on validation results.

        Returns:
            (action, confidence) tuple.
        """
        if not exists:
            return ClaimAction.REMOVE, 0.0

        if not was_provided:
            return ClaimAction.REMOVE, 0.1  # hallucinated grounding

        if support == SupportLevel.STRONG:
            return ClaimAction.KEEP, 0.9
        elif support == SupportLevel.WEAK:
            return ClaimAction.KEEP_WITH_WARNING, 0.5
        elif support == SupportLevel.CONTRADICTED:
            return ClaimAction.REGENERATE, 0.1
        else:  # NONE
            return ClaimAction.REWRITE, 0.3

    def validate_claim(
        self,
        claim: ClaimExtraction,
        provided_evidence_ids: set[str],
        evidence_texts: dict[str, str] | None = None,
    ) -> ClaimEvidenceResult:
        """Validate a single claim across all three levels."""
        warnings: list[str] = []

        # Get primary citation
        primary_citation = claim.citations[0] if claim.citations else ""

        # Level 1
        exists = self.check_level1_exists(primary_citation)

        # Level 2
        was_provided = self.check_level2_provided(primary_citation, provided_evidence_ids)

        # Level 3
        support, support_reason = self.check_level3_support(
            claim.claim_text, primary_citation, evidence_texts,
        )

        # Determine action
        action, confidence = self.determine_action(exists, was_provided, support)

        if not exists:
            warnings.append(f"Citation '{primary_citation}' not found in corpus")
        if exists and not was_provided:
            warnings.append(f"Citation '{primary_citation}' exists but was not in evidence set (leakage)")
        if support == SupportLevel.NONE:
            warnings.append(f"No support found for claim (citation: '{primary_citation}')")
        elif support == SupportLevel.WEAK:
            warnings.append(f"Weak support for claim (citation: '{primary_citation}')")

        return ClaimEvidenceResult(
            claim_id=claim.claim_id,
            claim_text=claim.claim_text,
            cited_sources=claim.citations,
            exists=exists,
            was_provided=was_provided,
            support=support,
            support_reason=support_reason,
            confidence=confidence,
            recommended_action=action,
            warnings=warnings,
        )

    def validate_document(
        self,
        text: str,
        provided_evidence_ids: set[str] | None = None,
        evidence_texts: dict[str, str] | None = None,
    ) -> DocumentValidationResult:
        """Validate all claims in a document.

        Args:
            text: The generated document/proposal text.
            provided_evidence_ids: IDs of evidence provided to the model (closed set).
            evidence_texts: Mapping of evidence ID → text for support checking.

        Returns:
            DocumentValidationResult with per-claim validation and overall trust score.
        """
        provided_ids = provided_evidence_ids or set()

        # Extract claims
        claims = self.extract_claims(text)

        if not claims:
            return DocumentValidationResult(
                total_claims=0,
                trust_score=1.0,  # no claims to validate → neutral trust
                summary="No claims with citations found in document",
            )

        # Validate each claim
        results: list[ClaimEvidenceResult] = []
        valid = 0
        invalid = 0
        rewrite = 0

        for claim in claims:
            result = self.validate_claim(claim, provided_ids, evidence_texts)
            results.append(result)

            if result.is_valid:
                valid += 1
            else:
                invalid += 1
                if result.recommended_action in (ClaimAction.REWRITE, ClaimAction.REGENERATE):
                    rewrite += 1

        # Calculate trust score: weighted average of claim confidences
        if results:
            trust_score = sum(r.confidence for r in results) / len(results)
        else:
            trust_score = 1.0

        # Build summary
        summary_parts = [
            f"{len(results)} claims validated",
            f"{valid} valid",
            f"{invalid} flagged",
        ]
        if rewrite > 0:
            summary_parts.append(f"{rewrite} need rewrite/regeneration")

        return DocumentValidationResult(
            total_claims=len(results),
            results=results,
            valid_claims=valid,
            invalid_claims=invalid,
            needs_rewrite=rewrite,
            trust_score=trust_score,
            summary=", ".join(summary_parts),
        )

    def get_claims_by_action(self, action: ClaimAction, results: list[ClaimEvidenceResult]) -> list[ClaimEvidenceResult]:
        """Filter results by recommended action."""
        return [r for r in results if r.recommended_action == action]

    def sanitize_text(
        self,
        text: str,
        results: list[ClaimEvidenceResult],
        mode: str = "flag",
    ) -> str:
        """Apply claim validation results to text.

        Args:
            text: Original text.
            results: Validation results for each claim.
            mode: "flag" (add warning markers), "remove" (remove bad claims),
                  or "replace" (replace citations with [unverified]).

        Returns:
            Modified text.
        """
        if mode == "flag":
            modified = text
            for r in results:
                if r.recommended_action in (ClaimAction.REMOVE, ClaimAction.REGENERATE):
                    # Add warning before the claim
                    warning = f" ⚠️[FLAGGED: {r.recommended_action.value}]"
                    # Find the claim in text and add warning after it
                    # Simple approach: find the first sentence that matches
                    claim_start = modified.find(r.claim_text[:50])
                    if claim_start >= 0:
                        # Find end of sentence
                        sentence_end = modified.find(".", claim_start)
                        if sentence_end >= 0:
                            modified = (
                                modified[:sentence_end + 1]
                                + warning
                                + modified[sentence_end + 1:]
                            )
            return modified

        elif mode == "replace":
            modified = text
            for r in results:
                if not r.exists:
                    # Replace non-existent citations with [unverified]
                    for cite in r.cited_sources:
                        modified = modified.replace(cite, "[unverified]")
            return modified

        else:  # "remove"
            # For now, same as flag — removing sentences is risky
            return self.sanitize_text(text, results, mode="flag")
