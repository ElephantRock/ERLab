"""Adapter wrappers that convert existing scoring modules into the Scorer ABC.

Normalizes all scores to 0-1 at the adapter boundary. Existing modules
remain untouched — their internal score scales are preserved.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.pipeline.evaluation.scorer import (
    EvaluationReport,
    ScoreDimension,
    Scorer,
    ScoreResult,
)

logger = logging.getLogger(__name__)


class NoveltyScorerAdapter(Scorer):
    """Wraps NoveltyChecker. Scores are already 0-1 — pass-through."""

    def __init__(self, novelty_checker: Any) -> None:
        self._checker = novelty_checker

    async def score(self, target: Any, target_id: str = "") -> EvaluationReport:
        report = await self._checker.check_novelty(target)
        scores = [
            ScoreResult(
                dimension=ScoreDimension.NOVELTY,
                score=report.overall_score,
                rationale=report.novelty_arguments,
                metadata={
                    "method_novelty": report.method_novelty,
                    "problem_novelty": report.problem_novelty,
                    "domain_transfer": report.domain_transfer,
                    "combination_novelty": report.combination_novelty,
                },
            ),
        ]
        return EvaluationReport(
            target_id=target_id,
            scores=scores,
            overall_score=report.overall_score,
        )


class FeasibilityScorerAdapter(Scorer):
    """Wraps FeasibilityScorer. Divides 0-10 scores by 10 to normalize to 0-1."""

    def __init__(self, feasibility_scorer: Any) -> None:
        self._scorer = feasibility_scorer

    async def score(self, target: Any, target_id: str = "") -> EvaluationReport:
        idea, novelty_report = target
        report = await self._scorer.score_feasibility(idea, novelty_report)
        normalized = report.overall_score / 10.0
        scores = [
            ScoreResult(
                dimension=ScoreDimension.FEASIBILITY,
                score=normalized,
                rationale=report.reasoning,
                metadata={
                    "timeline": report.estimated_timeline,
                    "risks": report.key_risks,
                    "data_availability": report.data_availability / 10.0,
                    "computational_requirements": report.computational_requirements / 10.0,
                    "methodological_complexity": report.methodological_complexity / 10.0,
                    "evaluation_plan": report.evaluation_plan / 10.0,
                },
            ),
        ]
        return EvaluationReport(
            target_id=target_id,
            scores=scores,
            overall_score=normalized,
        )


class MechanicalCheckAdapter(Scorer):
    """Wraps mechanical_quality_check. Scores are already 0-1."""

    async def score(self, target: Any, target_id: str = "") -> EvaluationReport:
        from backend.pipeline.generation.mechanical_checks import mechanical_quality_check

        report = mechanical_quality_check(target)
        scores = [
            ScoreResult(
                dimension=ScoreDimension.SOUNDNESS,
                score=report.composite_score,
                rationale="; ".join(report.flagged_issues) or "All heuristics passed",
                metadata={
                    "heuristics": [r.model_dump() for r in report.heuristic_results],
                },
            ),
        ]
        return EvaluationReport(
            target_id=target_id,
            scores=scores,
            overall_score=report.composite_score,
        )
