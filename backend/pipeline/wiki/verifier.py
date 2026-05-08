"""WikiVerifier — cross-checks wiki claims against source text.

AIV v5.3 — BATCH-123 TASK-02
HB-02: Verifier does NOT modify the wiki entry — only returns a new one with scores.
"""

from __future__ import annotations

import copy
import logging
import re

from backend.pipeline.wiki.models import WikiEntry

logger = logging.getLogger(__name__)


class WikiVerifier:
    """Verifies wiki entries against source paper text.

    Checks that factual claims in the wiki are supported by the source text.
    Sets quality_score and flags unsupported_claims.
    Does NOT modify the input wiki (HB-02).
    """

    def __init__(self, provider=None) -> None:
        self._provider = provider

    async def verify(self, wiki: WikiEntry, source_text: str) -> WikiEntry:
        """Verify a wiki entry against source text.

        Returns a NEW WikiEntry with quality_score and unsupported_claims set.
        Original wiki is NOT modified (HB-02).
        """
        # Deep copy to avoid mutation (HB-02)
        result = copy.deepcopy(wiki)
        unsupported: list[str] = []

        if not source_text or not source_text.strip():
            result.quality_score = 0.1
            result.unsupported_claims = ["Empty source text — cannot verify"]
            return result

        # Collect all factual claims from the wiki
        claims = self._extract_claims(wiki)
        source_lower = source_text.lower()

        verified = 0
        for claim in claims:
            if self._claim_supported(claim, source_lower):
                verified += 1
            else:
                unsupported.append(claim)

        total = max(len(claims), 1)
        result.quality_score = verified / total
        result.unsupported_claims = unsupported
        return result

    @staticmethod
    def _extract_claims(wiki: WikiEntry) -> list[str]:
        """Extract verifiable claims from a wiki entry."""
        claims: list[str] = []

        # Method details are factual claims
        if wiki.proposed_method:
            claims.append(wiki.proposed_method)
        for insight in wiki.key_insights:
            claims.append(insight)
        for exp in wiki.experiments:
            # Each experiment result is a factual claim
            parts = []
            if isinstance(exp, dict):
                if "dataset" in exp:
                    parts.append(f"dataset: {exp['dataset']}")
                if "metric" in exp and "value" in exp:
                    parts.append(f"{exp['metric']}: {exp['value']}")
            if parts:
                claims.append("; ".join(parts))

        return claims

    @staticmethod
    def _claim_supported(claim: str, source_lower: str) -> bool:
        """Check if a claim is supported by the source text.

        Uses keyword overlap: if >=40% of content words from the claim
        appear in the source, it's considered supported.
        """
        claim_lower = claim.lower()
        # Extract significant words (length > 3)
        claim_words = {w for w in re.findall(r"[a-z0-9]+", claim_lower) if len(w) > 3}
        if not claim_words:
            return True  # Empty claim is trivially supported

        found = sum(1 for w in claim_words if w in source_lower)
        ratio = found / len(claim_words)
        return ratio >= 0.4
