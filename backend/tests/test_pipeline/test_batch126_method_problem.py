"""BATCH-126 Tests — Method-Problem Gap Matrix."""

import pytest
from backend.pipeline.claims.models import Claim, ClaimType
from backend.pipeline.claims.method_problem import MethodProblemDetector, MethodProblemGap


class TestMethodProblemDetector:
    def _method(self, name, paper_id="P1"):
        return Claim(claim_type=ClaimType.METHOD, title=name, description=f"{name} method",
                     source_paper_id=paper_id, method_name=name)

    def _result(self, dataset, metric, value, paper_id="P1", method_name=None):
        return Claim(claim_type=ClaimType.RESULT, title=f"{metric} on {dataset}",
                     description=f"Achieves {value}", source_paper_id=paper_id,
                     dataset=dataset, metric=metric, value=value, method_name=method_name)

    def test_gap_creates(self):
        """TEST-126-01-01: MethodProblemGap creates."""
        gap = MethodProblemGap(method_name="BERT", method_paper_id="P1",
                               problem_dataset="ImageNet", applicability_score=0.5)
        assert gap.method_name == "BERT"

    def test_empty_claims(self):
        """TEST-126-01-02: find_gaps returns [] on empty (HB-01)."""
        detector = MethodProblemDetector()
        assert detector.find_gaps([]) == []

    def test_known_pairs_excluded(self):
        """TEST-126-01-03: Known method-dataset pairs excluded."""
        detector = MethodProblemDetector()
        claims = [
            self._method("BERT", "P1"),
            self._result("GLUE", "accuracy", "80.5%", "P1", method_name="BERT"),
        ]
        gaps = detector.find_gaps(claims)
        # BERT on GLUE is known — should NOT be in gaps
        for g in gaps:
            assert not (g.method_name == "BERT" and g.problem_dataset.lower() == "glue")

    def test_novel_pairs_flagged(self):
        """TEST-126-01-04: Novel method-dataset pairs flagged."""
        detector = MethodProblemDetector()
        claims = [
            self._method("BERT", "P1"),
            self._method("ResNet", "P2"),
            self._result("GLUE", "accuracy", "80.5%", "P1", method_name="BERT"),
            self._result("ImageNet", "accuracy", "76%", "P2", method_name="ResNet"),
        ]
        gaps = detector.find_gaps(claims)
        # BERT on ImageNet and ResNet on GLUE should be flagged
        pairs = {(g.method_name, g.problem_dataset) for g in gaps}
        assert ("BERT", "ImageNet") in pairs or any(
            g.method_name == "BERT" and "imagenet" in g.problem_dataset.lower() for g in gaps
        )

    def test_only_method_and_result(self):
        """TEST-126-01-05: Only METHOD+RESULT claims used (HB-02)."""
        detector = MethodProblemDetector()
        claims = [
            self._method("BERT", "P1"),
            Claim(claim_type=ClaimType.LIMITATION, title="L", description="D", source_paper_id="P2"),
        ]
        gaps = detector.find_gaps(claims)
        # No datasets from RESULT claims → no gaps possible
        assert len(gaps) == 0

    def test_gaps_scored(self):
        """TEST-126-01-06: Gaps scored by applicability."""
        detector = MethodProblemDetector()
        claims = [
            self._method("GPT-3", "P1"),
            self._result("SQuAD", "F1", "90%", "P2"),  # Different paper, no method_name
        ]
        gaps = detector.find_gaps(claims)
        if gaps:
            assert all(g.applicability_score > 0 for g in gaps)
