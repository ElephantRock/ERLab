"""Unified pipeline evaluator — composes all scorers into a single evaluation.

Wraps existing novelty/feasibility/mechanical scorers via adapters,
optionally adds GEval rubric scoring, and runs quality gates.
Reuses already-computed reports to avoid duplicate LLM calls.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from backend.pipeline.evaluation.cache import EvaluationCache
from backend.pipeline.evaluation.cost import EvaluationCostRecord, EvaluationCostTracker
from backend.pipeline.evaluation.deepeval_adapter import DeepEvalScorer
from backend.pipeline.evaluation.adversarial_debate import AdversarialDebate, DebateResult
from backend.pipeline.evaluation.geval import DEFAULT_RUBRICS, GEvalScorer
from backend.pipeline.evaluation.normalizers import (
    FeasibilityScorerAdapter,
    MechanicalCheckAdapter,
    NoveltyScorerAdapter,
)
from backend.pipeline.evaluation.quality_gate import QualityGate, QualityGateResult
from backend.pipeline.evaluation.scorer import (
    EvaluationReport,
    ScoreDimension,
    ScoreResult,
    WeightedCompositeScorer,
)

logger = logging.getLogger(__name__)


class UnifiedEvaluationReport(BaseModel):
    idea_id: str
    idea_title: str
    dimension_scores: dict[str, ScoreResult]
    overall_score: float
    quality_gate_result: QualityGateResult | None = None
    debate_result: DebateResult | None = None
    cost: EvaluationCostRecord | None = None
    evaluated_at: datetime = datetime.now(timezone.utc)


class PipelineEvaluator:
    """Orchestrates evaluation across all pipeline stages.

    Composes novelty, feasibility, mechanical, and optional GEval
    scorers into a unified evaluation.
    """

    def __init__(
        self,
        provider: Any,
        novelty_checker: Any,
        feasibility_scorer: Any,
        quality_gate: QualityGate | None = None,
        use_geval: bool = False,
        use_deepeval: bool = False,
        use_debate: bool = False,
        cache: EvaluationCache | None = None,
    ) -> None:
        self._provider = provider
        self._cache = cache or EvaluationCache()
        self._cost_tracker = EvaluationCostTracker()
        self._quality_gate = quality_gate

        self._novelty_adapter = NoveltyScorerAdapter(novelty_checker)
        self._feasibility_adapter = FeasibilityScorerAdapter(feasibility_scorer)
        self._mechanical_adapter = MechanicalCheckAdapter()

        self._geval_scorers: dict[ScoreDimension, GEvalScorer] = {}
        if use_geval:
            for dim, rubric in DEFAULT_RUBRICS.items():
                self._geval_scorers[dim] = GEvalScorer(provider, rubric, self._cache)

        self._deepeval_scorers: dict[ScoreDimension, DeepEvalScorer] = {}
        if use_deepeval:
            for dim, rubric in DEFAULT_RUBRICS.items():
                self._deepeval_scorers[dim] = DeepEvalScorer(provider, dim, rubric)

        self._debate: AdversarialDebate | None = None
        if use_debate:
            self._debate = AdversarialDebate(provider)

    async def evaluate_idea(
        self,
        idea: Any,
        novelty_report: Any | None = None,
        feasibility_report: Any | None = None,
        target_id: str = "",
    ) -> UnifiedEvaluationReport:
        dimension_scores: dict[str, ScoreResult] = {}
        overall_parts: list[tuple[float, float]] = []  # (score, weight)

        # Novelty
        if novelty_report is not None:
            novelty_eval = self._eval_from_novelty_report(novelty_report, target_id)
            for s in novelty_eval.scores:
                dimension_scores[s.dimension.value] = s
                overall_parts.append((s.score, 0.3))

        # Feasibility (normalize 0-10 to 0-1)
        if feasibility_report is not None:
            feas_eval = self._eval_from_feasibility_report(
                feasibility_report, target_id
            )
            for s in feas_eval.scores:
                dimension_scores[s.dimension.value] = s
                overall_parts.append((s.score, 0.3))

        # Mechanical checks (requires IdeaCandidate, skip for ResearchIdea)
        # This is applied separately in the generation loop, not here.

        # Optional GEval scoring
        for dim, geval in self._geval_scorers.items():
            if dim.value not in dimension_scores:
                geval_report = await geval.score(idea, target_id)
                for s in geval_report.scores:
                    dimension_scores[s.dimension.value] = s
                    overall_parts.append((s.score, 0.2))

        # Optional DeepEval scoring (bias-mitigated multi-pass)
        for dim, deval in self._deepeval_scorers.items():
            if dim.value not in dimension_scores:
                deval_report = await deval.score(idea, target_id)
                for s in deval_report.scores:
                    dimension_scores[f"{s.dimension.value}_deepeval"] = s
                    overall_parts.append((s.score, 0.1))

        # Weighted composite
        total_weight = sum(w for _, w in overall_parts)
        overall = (
            sum(s * w for s, w in overall_parts) / total_weight
            if total_weight > 0
            else 0.0
        )

        # Quality gate
        gate_result = None
        if self._quality_gate:
            eval_report = EvaluationReport(
                target_id=target_id,
                scores=list(dimension_scores.values()),
                overall_score=overall,
            )
            gate_result = self._quality_gate.evaluate(eval_report)

        # Adversarial debate (only if idea passes quality gate)
        debate_result = None
        if self._debate and (gate_result is None or gate_result.passed):
            try:
                debate_result = await self._debate.debate(idea)
            except Exception as e:
                logger.warning("Debate failed for %s: %s", target_id, e)

        return UnifiedEvaluationReport(
            idea_id=target_id,
            idea_title=getattr(idea, "title", str(idea)[:80]),
            dimension_scores=dimension_scores,
            overall_score=overall,
            quality_gate_result=gate_result,
            debate_result=debate_result,
        )

    async def evaluate_all(
        self,
        ideas: list[Any],
        novelty_reports: dict[int, Any],
        feasibility_reports: dict[int, Any],
    ) -> dict[int, UnifiedEvaluationReport]:
        results: dict[int, UnifiedEvaluationReport] = {}
        for idx, idea in enumerate(ideas):
            report = await self.evaluate_idea(
                idea=idea,
                novelty_report=novelty_reports.get(idx),
                feasibility_report=feasibility_reports.get(idx),
                target_id=f"idea_{idx}",
            )
            results[idx] = report
        return results

    def cost_summary(self) -> dict[str, Any]:
        return self._cost_tracker.summary()

    @staticmethod
    def _eval_from_novelty_report(
        report: Any, target_id: str
    ) -> EvaluationReport:
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

    @staticmethod
    def _eval_from_feasibility_report(
        report: Any, target_id: str
    ) -> EvaluationReport:
        normalized = report.overall_score / 10.0
        scores = [
            ScoreResult(
                dimension=ScoreDimension.FEASIBILITY,
                score=normalized,
                rationale=report.reasoning,
                metadata={
                    "timeline": report.estimated_timeline,
                    "risks": report.key_risks,
                },
            ),
        ]
        return EvaluationReport(
            target_id=target_id,
            scores=scores,
            overall_score=normalized,
        )
