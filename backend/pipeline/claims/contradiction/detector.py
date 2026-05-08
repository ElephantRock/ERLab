"""ContradictionDetector — find conflicting claims across papers.

AIV v5.3 — BATCH-125
HB-01: Returns [] on failure. HB-02: Only RESULT claims with same dataset+metric.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from backend.pipeline.claims.models import Claim, ClaimType
from backend.pipeline.claims.contradiction.models import ContradictionCandidate

logger = logging.getLogger(__name__)


class ContradictionDetector:
    """Find contradictory claims across papers by comparing RESULT claims."""

    def __init__(self, claim_store=None, provider=None) -> None:
        self._claim_store = claim_store
        self._provider = provider

    def find_contradictions(
        self, claims: list[Claim]
    ) -> list[ContradictionCandidate]:
        """Find contradictions among claims.

        Returns [] on empty input or failure (HB-01).
        Only considers RESULT claims with same dataset + metric (HB-02).
        """
        try:
            candidates = self._find_candidates(claims)
            if self._provider is not None:
                candidates = [self._verify_contradiction(c) for c in candidates]
            return candidates
        except Exception as e:
            logger.warning("ContradictionDetector failed: %s", e)
            return []  # HB-01

    def _find_candidates(
        self, claims: list[Claim]
    ) -> list[ContradictionCandidate]:
        """Pair RESULT claims with same dataset + metric but different values."""
        # Filter to RESULT claims only (HB-02)
        result_claims = [c for c in claims if c.claim_type == ClaimType.RESULT]

        # Group by (dataset, metric)
        groups: dict[tuple[str, str], list[Claim]] = defaultdict(list)
        for claim in result_claims:
            if claim.dataset and claim.metric:
                key = (claim.dataset.lower().strip(), claim.metric.lower().strip())
                groups[key].append(claim)

        # Find pairs with different values from different papers
        candidates: list[ContradictionCandidate] = []
        for (dataset, metric), group in groups.items():
            for i, claim_a in enumerate(group):
                for claim_b in group[i + 1:]:
                    # Must be from different papers
                    if claim_a.source_paper_id == claim_b.source_paper_id:
                        continue
                    # Must have different values
                    val_a = (claim_a.value or "").strip()
                    val_b = (claim_b.value or "").strip()
                    if val_a and val_b and val_a != val_b:
                        candidates.append(ContradictionCandidate(
                            claim_a=claim_a,
                            claim_b=claim_b,
                            metric=metric,
                            dataset=dataset,
                            value_a=val_a,
                            value_b=val_b,
                        ))

        return candidates

    def _verify_contradiction(
        self, candidate: ContradictionCandidate
    ) -> ContradictionCandidate:
        """Use LLM to verify if a contradiction is genuine.

        For now, uses a simple heuristic: if values differ by >10% numerically,
        mark as genuine. Otherwise mark as spurious.
        """
        try:
            val_a = float(candidate.value_a.replace("%", ""))
            val_b = float(candidate.value_b.replace("%", ""))
            diff_pct = abs(val_a - val_b) / max(abs(val_a), abs(val_b), 0.001)
            if diff_pct > 0.1:
                candidate.is_genuine = True
                candidate.explanation = (
                    f"Values differ by {diff_pct:.1%}: "
                    f"{candidate.value_a} vs {candidate.value_b}"
                )
            else:
                candidate.is_genuine = False
                candidate.explanation = (
                    f"Values differ by only {diff_pct:.1%}: likely variation"
                )
        except (ValueError, ZeroDivisionError):
            # Non-numeric values — can't determine automatically
            candidate.is_genuine = None
            candidate.explanation = "Could not determine: non-numeric values"
        return candidate
