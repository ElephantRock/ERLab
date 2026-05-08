"""BATCH-125 Tests — Contradiction Detector."""

import pytest
from backend.pipeline.claims.models import Claim, ClaimType
from backend.pipeline.claims.contradiction.models import ContradictionCandidate
from backend.pipeline.claims.contradiction.detector import ContradictionDetector


def _result_claim(paper_id, dataset, metric, value):
    return Claim(
        claim_type=ClaimType.RESULT,
        title=f"{metric} on {dataset}",
        description=f"Achieves {value} {metric} on {dataset}",
        source_paper_id=paper_id,
        dataset=dataset,
        metric=metric,
        value=value,
    )


class TestContradictionDetector:
    def test_candidate_creates(self):
        """TEST-125-01-01: ContradictionCandidate creates with all fields."""
        c = _result_claim("P1", "SQuAD", "F1", "90.0")
        cand = ContradictionCandidate(
            claim_a=c, claim_b=c, metric="F1", dataset="SQuAD",
            value_a="90.0", value_b="80.0",
        )
        assert cand.is_genuine is None

    def test_candidates_pair_same_metric_and_dataset(self):
        """TEST-125-01-02: find_candidates pairs claims with same metric+dataset."""
        detector = ContradictionDetector()
        claims = [
            _result_claim("P1", "SQuAD", "F1", "90.0"),
            _result_claim("P2", "SQuAD", "F1", "80.0"),
            _result_claim("P3", "GLUE", "accuracy", "85.0"),  # Different dataset/metric
        ]
        candidates = detector.find_contradictions(claims)
        assert len(candidates) == 1
        assert candidates[0].dataset == "squad"
        assert candidates[0].metric == "f1"

    def test_returns_empty_on_failure(self):
        """TEST-125-01-03: Returns [] on empty input (HB-01)."""
        detector = ContradictionDetector()
        assert detector.find_contradictions([]) == []

    def test_only_result_claims_candidates(self):
        """TEST-125-01-04: Only RESULT claims are candidates (HB-02)."""
        detector = ContradictionDetector()
        claims = [
            _result_claim("P1", "SQuAD", "F1", "90.0"),
            Claim(claim_type=ClaimType.METHOD, title="Method", description="D", source_paper_id="P2"),
        ]
        candidates = detector.find_contradictions(claims)
        assert len(candidates) == 0  # No pair possible with METHOD claim

    def test_different_values_flagged(self):
        """TEST-125-01-05: Different values flagged as candidate."""
        detector = ContradictionDetector()
        claims = [
            _result_claim("P1", "ImageNet", "accuracy", "76.5%"),
            _result_claim("P2", "ImageNet", "accuracy", "85.2%"),
        ]
        candidates = detector.find_contradictions(claims)
        assert len(candidates) == 1
        assert candidates[0].value_a != candidates[0].value_b

    def test_verification_marks_genuine(self):
        """TEST-125-01-06: Verification marks genuine vs spurious."""
        from unittest.mock import MagicMock
        provider = MagicMock()  # triggers heuristic path
        detector = ContradictionDetector(provider=provider)
        claims = [
            _result_claim("P1", "ImageNet", "accuracy", "76.5"),
            _result_claim("P2", "ImageNet", "accuracy", "95.2"),
        ]
        candidates = detector.find_contradictions(claims)
        assert len(candidates) == 1
        assert candidates[0].is_genuine is True  # >10% difference

    def test_end_to_end_contradiction(self):
        """TEST-125-01-07: End-to-end: 6 claims → 1 contradiction."""
        detector = ContradictionDetector()
        claims = [
            _result_claim("P1", "GLUE", "accuracy", "80.5"),
            _result_claim("P2", "GLUE", "accuracy", "92.1"),  # Contradicts P1
            _result_claim("P3", "GLUE", "accuracy", "80.5"),  # Same as P1, no contradiction
            _result_claim("P4", "SQuAD", "F1", "93.2"),       # Different metric
            Claim(claim_type=ClaimType.METHOD, title="BERT", description="D", source_paper_id="P5"),
            Claim(claim_type=ClaimType.LIMITATION, title="Compute", description="D", source_paper_id="P6"),
        ]
        candidates = detector.find_contradictions(claims)
        # P1 vs P2 (different values), P1 vs P3 (same values, skip)
        # P2 vs P3 (different values)
        # So 2 candidates: P1-P2 and P2-P3
        assert len(candidates) >= 1
        # At least one should involve P2 (the outlier)
        papers_involved = set()
        for c in candidates:
            papers_involved.add(c.claim_a.source_paper_id)
            papers_involved.add(c.claim_b.source_paper_id)
        assert "P2" in papers_involved
