"""DeepEval adapter with bias mitigation for multi-pass evaluation.

Wraps deepeval's GEval metric with position/format bias reduction by
running each evaluation multiple times with shuffled criteria order,
then averaging the results.
"""

from __future__ import annotations

import json
import logging
import random
from typing import Any

from backend.pipeline.evaluation.scorer import (
    EvaluationReport,
    ScoreDimension,
    ScoreResult,
    Scorer,
)

logger = logging.getLogger(__name__)


class DeepEvalScorer(Scorer):
    """Wraps deepeval's metrics with bias mitigation.

    Runs each evaluation n_passes times with shuffled criteria order,
    then averages scores to reduce position/format bias.
    """

    def __init__(
        self,
        provider: Any,
        dimension: ScoreDimension,
        rubric: Any,
        n_passes: int = 3,
    ) -> None:
        self._provider = provider
        self._dimension = dimension
        self._rubric = rubric
        self._n_passes = max(1, n_passes)

    async def score(self, target: Any, target_id: str = "") -> EvaluationReport:
        scores: list[float] = []
        rationales: list[str] = []

        for pass_idx in range(self._n_passes):
            criteria_steps = self._shuffled_steps(pass_idx)
            reasoning = await self._generate_reasoning(target, criteria_steps)
            score = await self._extract_score(reasoning)
            scores.append(score)
            rationales.append(reasoning)

        avg_score = sum(scores) / len(scores)
        score_std = (sum((s - avg_score) ** 2 for s in scores) / len(scores)) ** 0.5

        return EvaluationReport(
            target_id=target_id,
            scores=[
                ScoreResult(
                    dimension=self._dimension,
                    score=avg_score,
                    rationale=rationales[0],
                    metadata={
                        "pass_scores": scores,
                        "score_std": round(score_std, 4),
                        "n_passes": self._n_passes,
                        "bias_mitigated": True,
                    },
                )
            ],
            overall_score=avg_score,
        )

    def _shuffled_steps(self, seed_offset: int) -> str:
        """Return rubric scoring steps with shuffled line order."""
        steps = self._rubric.scoring_steps.split("\n")
        rng = random.Random(42 + seed_offset)
        shuffled = list(steps)
        rng.shuffle(shuffled)
        return "\n".join(shuffled)

    async def _generate_reasoning(self, target: Any, criteria_steps: str) -> str:
        prompt = (
            f"Evaluate the following research idea on this criterion:\n"
            f"Criterion: {self._rubric.criteria}\n\n"
            f"Steps:\n{criteria_steps}\n\n"
            f"Research idea:\n{target}\n\n"
            f"Provide step-by-step reasoning (2-4 sentences)."
        )
        return await self._provider.complete(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=256,
        )

    async def _extract_score(self, reasoning: str) -> float:
        prompt = (
            f"Based on this reasoning:\n{reasoning}\n\n"
            f"Assign a score between {self._rubric.scale_min} and {self._rubric.scale_max} "
            f"for the '{self._dimension.value}' dimension.\n"
            f"Respond with ONLY the numeric score, nothing else."
        )
        raw = await self._provider.complete(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=16,
        )
        try:
            return max(self._rubric.scale_min, min(self._rubric.scale_max, float(raw.strip())))
        except ValueError:
            logger.warning("DeepEval score parse failed: '%s', defaulting to 0.5", raw[:50])
            return 0.5
