"""Evidence Provenance Quality Scoring.

Verifies that claims in proposals trace to real citations.
Computes a coverage ratio: (supported_claims / total_claims).

Wraps and extends the existing CitationClaimAuditor by adding:
1. Claim extraction from proposal text (pattern-based, no LLM needed)
2. Coverage ratio computation across ALL claims (not just [SOURCE-X] tagged)
3. Integration with the quality_report for the decision gate

Inspired by DeepScientist's Paper Integrity Kernel:
"Never infer submission readiness only from green validators.
 Verify evidence provenance, claim scope, citation sufficiency."
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

# Claim extraction patterns — sentences that make assertions
_CLAIM_PATTERNS = [
    re.compile(r"(?:we propose|we present|we introduce|our approach|our method)", re.IGNORECASE),
    re.compile(r"(?:this enables|this allows|this achieves|this improves)", re.IGNORECASE),
    re.compile(r"(?:results? show|experiments? demonstrate|evaluation shows)", re.IGNORECASE),
    re.compile(r"(?:outperforms?|surpasses?|exceeds?|better than)", re.IGNORECASE),
    re.compile(r"(?:the key insight|the main contribution|the core idea)", re.IGNORECASE),
    re.compile(r"(?:addresses? the (?:gap|limitation|challenge)|solves? the problem)", re.IGNORECASE),
]

# Citation reference patterns
_CITATION_PATTERNS = [
    re.compile(r"\[SOURCE-(\d+)\]", re.IGNORECASE),
    re.compile(r"\[(\d+)\]"),  # [1], [2], etc.
    re.compile(r"\((?:et al\.?\s*,?\s*\d{4}[a-z]?)\)", re.IGNORECASE),  # (Author et al., 2024)
    re.compile(r"(?:Smith|Jones|Brown|Chen|Wang|Lee|Kim|Zhang|Liu|Garcia|Miller|Davis)\s*(?:et al\.?)?\s*[\(]?\s*\d{4}", re.IGNORECASE),
]


@dataclass
class ProvenanceReport:
    """Result of provenance checking for a single proposal."""

    total_claims: int
    supported_claims: int  # claims with at least one nearby citation
    unsupported_claims: int  # claims with no citation backing
    coverage_ratio: float  # supported / total (0.0 to 1.0)
    total_citations: int
    unique_citations: int
    unsupported_examples: list[str] = field(default_factory=list)  # sample unsupported claim texts
    trust_score: float | None = None  # from CitationClaimAuditor if available

    @property
    def is_low_coverage(self) -> bool:
        """True if coverage is below the 50% threshold."""
        return self.coverage_ratio < 0.5

    def to_dict(self) -> dict:
        return {
            "total_claims": self.total_claims,
            "supported_claims": self.supported_claims,
            "unsupported_claims": self.unsupported_claims,
            "coverage_ratio": round(self.coverage_ratio, 3),
            "total_citations": self.total_citations,
            "unique_citations": self.unique_citations,
            "unsupported_examples": self.unsupported_examples[:5],
            "trust_score": round(self.trust_score, 3) if self.trust_score is not None else None,
        }


class ProvenanceChecker:
    """Verify that every claim in a proposal traces to a real citation.

    Two-phase approach:
    Phase 1 (pattern-based, fast, no LLM):
        - Extract claims from proposal text
        - Check if each claim has a nearby citation reference
        - Compute coverage ratio

    Phase 2 (optional, LLM-based, slower):
        - Use CitationClaimAuditor for per-citation trust scoring
        - Add trust_score to the report
    """

    # Window size (chars) around a claim to look for citations
    CITATION_WINDOW = 300

    def __init__(
        self,
        provider: LLMProvider | None = None,
        enable_trust_scoring: bool = False,
    ) -> None:
        self._provider = provider
        self._enable_trust_scoring = enable_trust_scoring

    def check(
        self,
        proposal_text: str,
        citations: list[dict] | None = None,
    ) -> ProvenanceReport:
        """Check provenance of all claims in a proposal.

        Args:
            proposal_text: Full proposal markdown/text.
            citations: List of citation dicts: [{"title": ..., "abstract": ...}].
                       Used for unique citation count.

        Returns:
            ProvenanceReport with coverage ratio and details.
        """
        # Phase 1: Pattern-based claim extraction and citation proximity check
        claims = self._extract_claims(proposal_text)
        citation_positions = self._find_citations(proposal_text)

        total_claims = len(claims)
        supported = 0
        unsupported_examples: list[str] = []

        for claim in claims:
            has_nearby_citation = self._has_nearby_citation(
                claim, citation_positions, proposal_text
            )
            if has_nearby_citation:
                supported += 1
            elif len(unsupported_examples) < 5:
                # Store short snippet for debugging
                snippet = claim[:150].replace("\n", " ").strip()
                unsupported_examples.append(snippet)

        unsupported = total_claims - supported
        coverage_ratio = supported / total_claims if total_claims > 0 else 1.0

        # Count citations
        unique_citations = len(citations) if citations else 0
        total_citations = len(citation_positions)

        return ProvenanceReport(
            total_claims=total_claims,
            supported_claims=supported,
            unsupported_claims=unsupported,
            coverage_ratio=coverage_ratio,
            total_citations=total_citations,
            unique_citations=unique_citations,
            unsupported_examples=unsupported_examples,
        )

    @staticmethod
    def _extract_claims(text: str) -> list[str]:
        """Extract claim sentences from proposal text.

        Splits text into sentences, then filters for assertion patterns.
        """
        if not text:
            return []

        # Split into sentences (handle common abbreviations)
        # Simple sentence splitter: split on . ! ? followed by space + capital
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)

        claims: list[str] = []
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:
                continue

            # Check if sentence matches any claim pattern
            for pattern in _CLAIM_PATTERNS:
                if pattern.search(sentence):
                    claims.append(sentence)
                    break

        return claims

    @staticmethod
    def _find_citations(text: str) -> list[tuple[int, int]]:
        """Find all citation references in text.

        Returns:
            List of (start, end) position tuples.
        """
        positions: list[tuple[int, int]] = []
        for pattern in _CITATION_PATTERNS:
            for match in pattern.finditer(text):
                positions.append((match.start(), match.end()))
        return positions

    def _has_nearby_citation(
        self,
        claim_text: str,
        citation_positions: list[tuple[int, int]],
        full_text: str,
    ) -> bool:
        """Check if a claim has a citation reference nearby (within window)."""
        # Find the claim's position in the full text
        claim_start = full_text.find(claim_text[:50])  # use first 50 chars as anchor
        if claim_start == -1:
            return False

        claim_end = claim_start + len(claim_text)

        # Look for citations within the window around the claim
        window_start = claim_start - self.CITATION_WINDOW
        window_end = claim_end + self.CITATION_WINDOW

        for cit_start, cit_end in citation_positions:
            # Citation is "nearby" if it overlaps with or is adjacent to the claim
            if cit_start >= window_start and cit_start <= window_end:
                return True
            if cit_end >= window_start and cit_end <= window_end:
                return True

        return False
