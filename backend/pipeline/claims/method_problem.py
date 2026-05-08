"""Method-problem gap detection."""

from __future__ import annotations

from dataclasses import dataclass

from backend.pipeline.claims.models import Claim, ClaimType


@dataclass
class MethodProblemGap:
    """A gap where a method has not been applied to a dataset/problem."""
    method_name: str
    method_paper_id: str
    problem_dataset: str
    applicability_score: float  # 0-1
    reasoning: str = ""


class MethodProblemDetector:
    """Find unexplored method-dataset combinations from claims."""

    def find_gaps(self, claims: list[Claim]) -> list[MethodProblemGap]:
        """Identify method-dataset pairs that haven't been explored.

        Returns [] on empty input (HB-01). Only uses METHOD + RESULT claims (HB-02).
        """
        if not claims:
            return []  # HB-01

        methods: list[tuple[str, str]] = []  # (method_name, paper_id)
        datasets: set[str] = set()
        known_pairs: set[tuple[str, str]] = set()  # (method, dataset)

        for claim in claims:
            if claim.claim_type == ClaimType.METHOD and claim.method_name:
                methods.append((claim.method_name, claim.source_paper_id))
            elif claim.claim_type == ClaimType.RESULT and claim.dataset:
                datasets.add(claim.dataset)
                if claim.method_name:  # Some RESULT claims reference the method
                    known_pairs.add((claim.method_name.lower(), claim.dataset.lower()))

        if not methods or not datasets:
            return []

        gaps: list[MethodProblemGap] = []
        for method_name, paper_id in methods:
            for dataset in datasets:
                pair = (method_name.lower(), dataset.lower())
                if pair not in known_pairs:
                    score = self._score_gap(method_name, dataset)
                    if score > 0:
                        gaps.append(MethodProblemGap(
                            method_name=method_name,
                            method_paper_id=paper_id,
                            problem_dataset=dataset,
                            applicability_score=score,
                            reasoning=f"{method_name} has not been applied to {dataset}",
                        ))

        return sorted(gaps, key=lambda g: g.applicability_score, reverse=True)

    @staticmethod
    def _score_gap(method_name: str, dataset: str) -> float:
        """Heuristic applicability score.

        Higher score for methods and datasets from related domains.
        Simple keyword overlap for now.
        """
        # Base score for any novel combination
        return 0.5
