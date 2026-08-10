"""GEval-style rubric-based LLM-as-judge scorer.

Adapted from deepeval's GEval pattern: two-step LLM call
(chain-of-thought reasoning, then score extraction).
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from pydantic import BaseModel

from backend.pipeline.evaluation.cache import EvaluationCache
from backend.pipeline.evaluation.scorer import (
    EvaluationReport,
    ScoreDimension,
    Scorer,
    ScoreResult,
)

logger = logging.getLogger(__name__)


class EvaluationRubric(BaseModel):
    dimension: ScoreDimension
    criteria: str
    scoring_steps: str
    scale_min: float = 0.0
    scale_max: float = 1.0


DEFAULT_RUBRICS: dict[ScoreDimension, EvaluationRubric] = {
    ScoreDimension.NOVELTY: EvaluationRubric(
        dimension=ScoreDimension.NOVELTY,
        criteria="How original is this research idea compared to existing work?",
        scoring_steps=(
            "1. Identify the core claim of the idea.\n"
            "2. Compare against known research directions.\n"
            "3. Assess whether the method, problem, or application is new.\n"
            "4. Score: 0=completely derivative, 1=highly novel contribution."
        ),
    ),
    ScoreDimension.FEASIBILITY: EvaluationRubric(
        dimension=ScoreDimension.FEASIBILITY,
        criteria="How feasible is this research idea given typical academic resources?",
        scoring_steps=(
            "1. Evaluate data availability requirements.\n"
            "2. Assess computational resource needs.\n"
            "3. Judge methodological complexity.\n"
            "4. Score: 0=infeasible, 1=highly feasible within 3-6 months."
        ),
    ),
    ScoreDimension.IMPACT: EvaluationRubric(
        dimension=ScoreDimension.IMPACT,
        criteria="What is the potential impact of this research idea on the field?",
        scoring_steps=(
            "1. Assess the significance of the problem addressed.\n"
            "2. Evaluate potential citation impact.\n"
            "3. Consider breadth of applicability.\n"
            "4. Score: 0=marginal contribution, 1=field-changing potential."
        ),
    ),
    ScoreDimension.CLARITY: EvaluationRubric(
        dimension=ScoreDimension.CLARITY,
        criteria="How clearly and precisely is this research idea formulated?",
        scoring_steps=(
            "1. Check if the problem statement is specific and unambiguous.\n"
            "2. Evaluate whether the proposed method is well-described.\n"
            "3. Assess the evaluation plan's concreteness.\n"
            "4. Score: 0=vague and unclear, 1=precise and actionable."
        ),
    ),
    ScoreDimension.SOUNDNESS: EvaluationRubric(
        dimension=ScoreDimension.SOUNDNESS,
        criteria="How methodologically sound is this research idea?",
        scoring_steps=(
            "1. Check for logical consistency between problem and method.\n"
            "2. Verify the evaluation approach matches the claims.\n"
            "3. Identify any circular reasoning or unsupported claims.\n"
            "4. Score: 0=major flaws, 1=rigorous and well-grounded."
        ),
    ),
    ScoreDimension.COHERENCE: EvaluationRubric(
        dimension=ScoreDimension.COHERENCE,
        criteria="How logically consistent is this research idea internally?",
        scoring_steps=(
            "1. Check if problem statement and proposed method align.\n"
            "2. Verify expected contributions follow from the method.\n"
            "3. Identify internal contradictions or gaps in logic.\n"
            "4. Score: 0=contradictory, 1=fully coherent narrative."
        ),
    ),
    ScoreDimension.COMPLETENESS: EvaluationRubric(
        dimension=ScoreDimension.COMPLETENESS,
        criteria="How completely does this idea address all required research components?",
        scoring_steps=(
            "1. Verify the idea specifies a clear problem.\n"
            "2. Check that a method is proposed, not just a vague direction.\n"
            "3. Confirm an evaluation plan exists.\n"
            "4. Score: 0=major gaps, 1=all components specified."
        ),
    ),
}


class GEvalScorer(Scorer):
    """LLM-as-judge scorer using structured rubrics with optional caching."""

    def __init__(
        self,
        provider: Any,
        rubric: EvaluationRubric,
        cache: EvaluationCache | None = None,
    ) -> None:
        self._provider = provider
        self._rubric = rubric
        self._cache = cache

    async def score(self, target: Any, target_id: str = "") -> EvaluationReport:
        cache_key = self._cache_key(target)
        if self._cache and (cached := self._cache.get(cache_key)):
            return cached

        reasoning = await self._generate_reasoning(target)
        score = await self._extract_score(target, reasoning)
        score = max(self._rubric.scale_min, min(self._rubric.scale_max, score))

        result = ScoreResult(
            dimension=self._rubric.dimension,
            score=score,
            rationale=reasoning,
        )
        report = EvaluationReport(
            target_id=target_id,
            scores=[result],
            overall_score=score,
        )
        if self._cache:
            self._cache.put(cache_key, report)
        return report

    def _cache_key(self, target: Any) -> str:
        content = json.dumps(
            {"target": str(target)[:500], "rubric": self._rubric.criteria},
            sort_keys=True,
        )
        return hashlib.sha256(content.encode()).hexdigest()

    async def _generate_reasoning(self, target: Any) -> str:
        prompt = (
            f"Evaluate the following research idea on this criterion:\n"
            f"Criterion: {self._rubric.criteria}\n\n"
            f"Steps:\n{self._rubric.scoring_steps}\n\n"
            f"Research idea:\n{target}\n\n"
            f"Provide step-by-step reasoning (2-4 sentences)."
        )
        return await self._provider.complete(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=256,
        )

    async def _extract_score(self, target: Any, reasoning: str) -> float:
        prompt = (
            f"Based on this reasoning:\n{reasoning}\n\n"
            f"Assign a score between {self._rubric.scale_min} and {self._rubric.scale_max} "
            f"for the '{self._rubric.dimension.value}' dimension.\n"
            f"Respond with ONLY the numeric score, nothing else."
        )
        raw = await self._provider.complete(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=16,
        )
        try:
            return float(raw.strip())
        except ValueError:
            logger.warning("GEval score parse failed: '%s', defaulting to 0.5", raw[:50])
            return 0.5
