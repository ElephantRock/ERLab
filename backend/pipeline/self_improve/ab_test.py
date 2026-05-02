"""A/B test harness for evolved vs baseline pipeline parameters.

Compares evolved parameter performance against baseline using the
ParetoFrontier history. Provides statistical confidence scoring
for adoption decisions.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from backend.pipeline.self_improve.frontier import FrontierType, ParetoFrontier

logger = logging.getLogger(__name__)


class ABTestResult(BaseModel):
    """Result of comparing evolved params against baseline."""

    run_id: str = ""
    baseline_score: float = 0.0
    evolved_score: float = 0.0
    delta: float = 0.0
    winner: str = "tie"  # "baseline" | "evolved" | "tie"
    confidence: float = 0.0


class ABTestHarness:
    """Compare evolved parameters against baseline from frontier history."""

    def __init__(
        self,
        frontier: ParetoFrontier,
        min_confidence: float = 0.6,
    ) -> None:
        self._frontier = frontier
        self._min_confidence = min_confidence
        self._results: list[ABTestResult] = []

    def compare_against_baseline(
        self,
        params: dict[str, Any],
        run_id: str,
        score: float,
        objective: FrontierType = FrontierType.QUALITY,
    ) -> ABTestResult:
        """Compare current run score against best baseline in frontier.

        Args:
            params: The evolved parameters used.
            run_id: Pipeline run identifier.
            score: The composite quality score achieved.
            objective: Which frontier objective to compare on.

        Returns:
            ABTestResult with winner determination and confidence.
        """
        best_point = self._frontier.get_best(objective)
        baseline_score = best_point.scores.get(objective.value, 0.0) if best_point else 0.0

        delta = score - baseline_score

        # Simple confidence: based on delta magnitude and frontier size
        n_points = self._frontier.frontier_size
        if n_points == 0:
            confidence = 0.5
        else:
            # Larger delta + more history = higher confidence
            confidence = min(1.0, abs(delta) * 2.0 + n_points * 0.05)

        if delta > 0.01:
            winner = "evolved"
        elif delta < -0.01:
            winner = "baseline"
        else:
            winner = "tie"

        result = ABTestResult(
            run_id=run_id,
            baseline_score=baseline_score,
            evolved_score=score,
            delta=delta,
            winner=winner,
            confidence=confidence,
        )
        self._results.append(result)
        return result

    def should_adopt(self, result: ABTestResult) -> bool:
        """True if evolved params should be adopted.

        Requires: evolved wins AND confidence above threshold.
        """
        return result.winner == "evolved" and result.confidence >= self._min_confidence

    @property
    def results(self) -> list[ABTestResult]:
        return list(self._results)
