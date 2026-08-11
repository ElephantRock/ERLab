"""EvolutionEngine — per-stage outcome tracking with time-decayed digests.

Wraps PipelineEvolver to add: per-stage outcome recording, time-decayed
digests for prompt overlay generation, and history-aware parameter proposal.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.pipeline.self_improve.evolution import PARAM_RANGES, PipelineEvolver

logger = logging.getLogger(__name__)


class StageOutcome(BaseModel):
    """Recorded outcome for a single pipeline stage execution."""

    stage_name: str
    run_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    score: float = 0.0
    params_used: dict[str, Any] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)


class EvolutionEngine:
    """Wraps PipelineEvolver with per-stage outcome tracking and prompt overlays.

    Records outcomes per stage, applies exponential time decay to weight
    recent outcomes more heavily, and generates LLM-based prompt overlays
    from accumulated stage knowledge.
    """

    def __init__(
        self,
        evolver: PipelineEvolver,
        provider: Any = None,
        decay_rate: float = 0.95,
        max_digest_entries: int = 10,
    ) -> None:
        self._evolver = evolver
        self._provider = provider
        self._decay_rate = decay_rate
        self._max_digest = max_digest_entries
        self._outcomes: list[StageOutcome] = []

    @property
    def evolver(self) -> PipelineEvolver:
        return self._evolver

    def record_stage_outcome(
        self,
        stage_name: str,
        run_id: str,
        score: float,
        params: dict[str, Any],
        issues: list[str] | None = None,
    ) -> None:
        """Record a per-stage outcome with metadata."""
        outcome = StageOutcome(
            stage_name=stage_name,
            run_id=run_id,
            score=score,
            params_used=dict(params),
            issues=issues or [],
        )
        self._outcomes.append(outcome)
        logger.debug(
            "Stage outcome recorded: %s score=%.3f run=%s",
            stage_name, score, run_id,
        )

    def get_time_decayed_digest(
        self, stage_name: str, max_entries: int | None = None
    ) -> list[tuple[StageOutcome, float]]:
        """Return recent outcomes with exponential time decay weighting.

        Returns list of (outcome, weight) tuples, most recent first.
        Weight = decay_rate ^ (position_from_end), so the most recent
        outcome gets weight 1.0, the second-most gets decay_rate, etc.
        """
        limit = max_entries or self._max_digest
        stage_outcomes = [o for o in self._outcomes if o.stage_name == stage_name]
        recent = stage_outcomes[-limit:]

        if not recent:
            return []

        # Assign weights: most recent = 1.0, older = decay^distance
        weighted = []
        n = len(recent)
        for i, outcome in enumerate(recent):
            distance = n - 1 - i  # 0 for most recent
            weight = self._decay_rate ** distance
            weighted.append((outcome, weight))

        weighted.reverse()  # Most recent first
        return weighted

    async def generate_prompt_overlay(self, stage_name: str) -> str | None:
        """Generate a prompt overlay from accumulated stage outcomes.

        Uses the LLM to synthesize improvement suggestions from the
        time-decayed digest of past outcomes.
        """
        digest = self.get_time_decayed_digest(stage_name)
        if not digest or not self._provider:
            return None

        # Build a summary of recent outcomes
        avg_score = sum(w * o.score for o, w in digest) / sum(w for _, w in digest)
        issues_seen = set()
        for outcome, _ in digest:
            for issue in outcome.issues:
                issues_seen.add(issue)

        if avg_score > 0.7 and not issues_seen:
            return None  # No overlay needed — performing well

        summary_lines = [
            f"Stage: {stage_name}",
            f"Recent weighted average score: {avg_score:.3f}",
            f"Observations: {len(digest)}",
        ]
        if issues_seen:
            summary_lines.append(f"Known issues: {'; '.join(list(issues_seen)[:5])}")

        try:
            overlay = await self._provider.complete(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a research pipeline optimization assistant. "
                            "Given stage performance data, generate a brief (1-2 sentence) "
                            "suggestion for improving this stage's output quality."
                        ),
                    },
                    {"role": "user", "content": "\n".join(summary_lines)},
                ],
                temperature=0.3,
                max_tokens=128,
            )
            return overlay.strip() if overlay.strip() else None
        except Exception as e:
            logger.warning("Prompt overlay generation failed: %s", e)
            return None

    def propose_with_history(self) -> dict[str, Any]:
        """Delegate to evolver.propose() with history context.

        If recent outcomes show consistent low scores for specific stages,
        biases parameter proposals toward addressing those stages.
        """
        params = self._evolver.propose()

        # Bias: if any stage has avg score < 0.4, nudge relevant params
        stage_averages: dict[str, float] = {}
        for outcome in self._outcomes[-20:]:
            stage_averages.setdefault(outcome.stage_name, 0.0)
            stage_averages[outcome.stage_name] = (
                stage_averages[outcome.stage_name] + outcome.score
            )

        if stage_averages:
            for stage in stage_averages:
                count = sum(1 for o in self._outcomes[-20:] if o.stage_name == stage)
                if count > 0:
                    stage_averages[stage] /= count

            # Nudge toward more exploration if idea generation is low
            if stage_averages.get("idea_generation", 1.0) < 0.4:
                if "ideas_per_round" in params:
                    params["ideas_per_round"] = min(
                        PARAM_RANGES["ideas_per_round"][1],
                        int(params["ideas_per_round"]) + 1,
                    )
                if "generation_rounds" in params:
                    params["generation_rounds"] = min(
                        PARAM_RANGES["generation_rounds"][1],
                        int(params["generation_rounds"]) + 1,
                    )

        return params
