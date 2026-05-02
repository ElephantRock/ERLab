"""Abstract scorer and composition patterns for evaluation.

Adopted from weave (Scorer ABC with score + summarize), with
weighted/chained/conditional composition for multi-dimensional
fitness evaluation.

Adopted from det-acp (policy-gated evaluation) for governance
integration: scorers can be gated by policy before execution.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ScoreDimension(str, Enum):
    NOVELTY = "novelty"
    FEASIBILITY = "feasibility"
    IMPACT = "impact"
    CLARITY = "clarity"
    SOUNDNESS = "soundness"
    COHERENCE = "coherence"
    COMPLETENESS = "completeness"


class ScoreResult(BaseModel):
    dimension: ScoreDimension
    score: float
    rationale: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationReport(BaseModel):
    target_id: str
    scores: list[ScoreResult] = Field(default_factory=list)
    overall_score: float = 0.0
    passed_threshold: float | None = None

    @property
    def passed(self) -> bool:
        return self.overall_score > 0.0

    @property
    def passed_gate(self) -> bool:
        if self.passed_threshold is None:
            return self.passed
        return self.overall_score >= self.passed_threshold


class Scorer(ABC):
    """Abstract scorer with score + summarize interface."""

    @abstractmethod
    async def score(self, target: Any, target_id: str = "") -> EvaluationReport:
        ...

    async def summarize(self, reports: list[EvaluationReport]) -> str:
        if not reports:
            return "No evaluation reports."
        avg = sum(r.overall_score for r in reports) / len(reports)
        passed = sum(1 for r in reports if r.passed)
        return f"{passed}/{len(reports)} passed, avg score: {avg:.2f}"


class DimensionScorer(Scorer):
    """Scores a single dimension using a callable."""

    def __init__(self, dimension: ScoreDimension, scorer_fn: callable, weight: float = 1.0):
        self._dimension = dimension
        self._scorer_fn = scorer_fn
        self._weight = weight

    async def score(self, target: Any, target_id: str = "") -> EvaluationReport:
        raw = self._scorer_fn(target)
        result = ScoreResult(
            dimension=self._dimension,
            score=raw * self._weight,
            rationale=f"Weighted score ({self._weight:.1f}x)",
        )
        return EvaluationReport(
            target_id=target_id,
            scores=[result],
            overall_score=result.score,
        )


class WeightedCompositeScorer(Scorer):
    """Composes multiple scorers with weights into a single score."""

    def __init__(self, scorers: list[tuple[Scorer, float]]):
        self._scorers = scorers
        total = sum(w for _, w in scorers)
        self._weights = (
            [w / total for _, w in scorers] if total > 0 else [1.0 / len(scorers)] * len(scorers)
        )
        self._inner = [s for s, _ in scorers]

    async def score(self, target: Any, target_id: str = "") -> EvaluationReport:
        all_scores = []
        overall = 0.0
        for scorer, weight in zip(self._inner, self._weights, strict=True):
            report = await scorer.score(target, target_id)
            all_scores.extend(report.scores)
            overall += report.overall_score * weight
        return EvaluationReport(
            target_id=target_id,
            scores=all_scores,
            overall_score=overall,
        )

    async def summarize(self, reports: list[EvaluationReport]) -> str:
        lines = [await s.summarize(reports) for s in self._inner]
        return "\n".join(lines)


class ChainedScorer(Scorer):
    """Chains scorers sequentially; stops on failure if configured."""

    def __init__(self, scorers: list[Scorer], stop_on_fail: bool = False):
        self._scorers = scorers
        self._stop_on_fail = stop_on_fail

    async def score(self, target: Any, target_id: str = "") -> EvaluationReport:
        all_scores = []
        overall = 0.0
        for scorer in self._scorers:
            report = await scorer.score(target, target_id)
            all_scores.extend(report.scores)
            overall += report.overall_score
            if self._stop_on_fail and not report.passed:
                break
        n = len(all_scores)
        return EvaluationReport(
            target_id=target_id,
            scores=all_scores,
            overall_score=overall / n if n > 0 else 0.0,
        )


class ConditionalScorer(Scorer):
    """Selects scorer based on a condition function."""

    def __init__(self, condition: callable, true_scorer: Scorer, false_scorer: Scorer):
        self._condition = condition
        self._true_scorer = true_scorer
        self._false_scorer = false_scorer

    async def score(self, target: Any, target_id: str = "") -> EvaluationReport:
        scorer = self._true_scorer if self._condition(target) else self._false_scorer
        return await scorer.score(target, target_id)


class FitnessScorer(Scorer):
    """Multi-dimensional fitness scoring across novelty/feasibility/impact.

    Convenience scorer that creates weighted DimensionScorers for the
    three core evaluation dimensions.
    """

    def __init__(
        self,
        novelty_fn: callable,
        feasibility_fn: callable,
        impact_fn: callable,
        novelty_weight: float = 0.4,
        feasibility_weight: float = 0.3,
        impact_weight: float = 0.3,
    ):
        self._composite = WeightedCompositeScorer(
            [
                (
                    DimensionScorer(ScoreDimension.NOVELTY, novelty_fn, novelty_weight),
                    novelty_weight,
                ),
                (
                    DimensionScorer(ScoreDimension.FEASIBILITY, feasibility_fn, feasibility_weight),
                    feasibility_weight,
                ),
                (DimensionScorer(ScoreDimension.IMPACT, impact_fn, impact_weight), impact_weight),
            ]
        )

    async def score(self, target: Any, target_id: str = "") -> EvaluationReport:
        return await self._composite.score(target, target_id)
