"""Configurable quality gate for evaluation reports.

Replaces the trivial `passed > 0.0` with configurable thresholds
per dimension, composite scoring, and actionable recommendations.
"""

from __future__ import annotations

from pydantic import BaseModel

from backend.pipeline.evaluation.scorer import EvaluationReport, ScoreDimension


class QualityThreshold(BaseModel):
    dimension: ScoreDimension
    min_score: float = 0.0
    weight: float = 1.0
    required: bool = False


class QualityGateConfig(BaseModel):
    thresholds: list[QualityThreshold] = []
    composite_threshold: float = 0.5
    mode: str = "any"  # "any" (composite >= threshold) or "all" (all required must pass)

    @classmethod
    def default(cls) -> QualityGateConfig:
        return cls(
            thresholds=[
                QualityThreshold(
                    dimension=ScoreDimension.NOVELTY, min_score=0.3, weight=0.3
                ),
                QualityThreshold(
                    dimension=ScoreDimension.FEASIBILITY, min_score=0.4, weight=0.3
                ),
                QualityThreshold(
                    dimension=ScoreDimension.IMPACT, min_score=0.3, weight=0.2
                ),
                QualityThreshold(
                    dimension=ScoreDimension.SOUNDNESS,
                    min_score=0.5,
                    weight=0.2,
                    required=True,
                ),
            ],
            composite_threshold=0.4,
            mode="any",
        )


class QualityGateResult(BaseModel):
    passed: bool
    composite_score: float
    dimension_results: dict[str, tuple[float, bool]]  # name -> (score, passed)
    failures: list[str]
    recommendation: str  # "proceed", "retry_with_feedback", "discard"


class QualityGate:
    """Evaluates an EvaluationReport against configurable thresholds."""

    def __init__(self, config: QualityGateConfig) -> None:
        self._config = config
        self._threshold_map = {t.dimension: t for t in config.thresholds}

    def evaluate(self, report: EvaluationReport) -> QualityGateResult:
        score_map = {s.dimension: s.score for s in report.scores}
        dimension_results: dict[str, tuple[float, bool]] = {}
        failures: list[str] = []
        required_failed = False

        for dim, threshold in self._threshold_map.items():
            score = score_map.get(dim, 0.0)
            passed = score >= threshold.min_score
            dimension_results[dim.value] = (score, passed)
            if not passed:
                failures.append(
                    f"{dim.value}: {score:.2f} < {threshold.min_score:.2f}"
                )
                if threshold.required:
                    required_failed = True

        # Weighted composite
        total_weight = sum(t.weight for t in self._config.thresholds)
        composite = 0.0
        if total_weight > 0:
            for dim, threshold in self._threshold_map.items():
                score = score_map.get(dim, 0.0)
                composite += score * threshold.weight
            composite /= total_weight

        # Determine pass/fail
        if self._config.mode == "all":
            passed = not failures and not required_failed
        else:  # "any"
            passed = composite >= self._config.composite_threshold and not required_failed

        recommendation = self._recommend(passed, composite, failures)
        return QualityGateResult(
            passed=passed,
            composite_score=composite,
            dimension_results=dimension_results,
            failures=failures,
            recommendation=recommendation,
        )

    def _recommend(
        self, passed: bool, composite: float, failures: list[str]
    ) -> str:
        if passed:
            return "proceed"
        if composite >= 0.2 and len(failures) <= 2:
            return "retry_with_feedback"
        return "discard"
