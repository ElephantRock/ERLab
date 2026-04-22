"""Strategy adapter — wraps PipelineEvolver with plateau-aware adjustments."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.pipeline.self_improve.evolution import PipelineEvolver
    from backend.pipeline.self_improve.lessons import LessonExtractor

logger = logging.getLogger(__name__)


class StrategyAdapter:
    """Wraps PipelineEvolver to add plateau response and lesson feedback."""

    def __init__(
        self,
        evolver: PipelineEvolver,
        lesson_extractor: LessonExtractor | None = None,
    ) -> None:
        self._evolver = evolver
        self._lesson_extractor = lesson_extractor

    async def adapt(self, feedback: dict, current_params: dict) -> dict:
        """Main entry: check for plateau, apply lessons, return adjusted params."""
        adjusted = dict(current_params)

        # Apply plateau response if needed
        metric = feedback.get("metric", "")
        if metric:
            adjusted = self._apply_plateau_response(metric, adjusted)

        # Apply lesson-based feedback
        lessons = feedback.get("lessons", [])
        if lessons:
            adjusted = self._apply_lesson_feedback(lessons, adjusted)

        return adjusted

    def _apply_plateau_response(self, metric: str, params: dict) -> dict:
        """Aggressive parameter changes on plateau detection."""
        adjusted = dict(params)

        if metric == "avg_idea_score":
            # Increase exploration
            if "generation_rounds" in adjusted:
                adjusted["generation_rounds"] = min(
                    adjusted["generation_rounds"] + 1, 8
                )
            if "ideas_per_round" in adjusted:
                adjusted["ideas_per_round"] = min(
                    adjusted["ideas_per_round"] + 1, 10
                )
        elif metric == "avg_novelty_score":
            # Increase temperature for diversity
            for key in ("ideator_temperature", "refiner_temperature"):
                if key in adjusted:
                    adjusted[key] = min(adjusted[key] + 0.1, 1.5)

        logger.info("Plateau response for %s: adjusted params", metric)
        return adjusted

    def _apply_lesson_feedback(self, lessons: list[str], params: dict) -> dict:
        """Delegate lesson application to the evolver."""
        if self._evolver is not None:
            return self._evolver.apply_lessons(lessons, params)
        return params
