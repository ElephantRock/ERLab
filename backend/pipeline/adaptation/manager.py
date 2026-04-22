"""Adaptation manager — orchestrates post-run behavioral adaptation."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from backend.pipeline.adaptation.feedback import FeedbackCollector, RunFeedback
from backend.pipeline.adaptation.strategy import StrategyAdapter

if TYPE_CHECKING:
    from backend.pipeline.metacognitive.manager import MetacognitiveManager
    from backend.pipeline.result import PipelineResult
    from backend.pipeline.self_improve.evolution import PipelineEvolver
    from backend.pipeline.self_improve.lessons import LessonExtractor

logger = logging.getLogger(__name__)


class AdaptationManager:
    """Post-run behavioral adaptation: feedback → plateau check → lesson extraction → param adjustment."""

    def __init__(
        self,
        evolver: PipelineEvolver,
        lesson_extractor: LessonExtractor,
        metacog: MetacognitiveManager | None = None,
        feedback_window: int = 5,
        min_improvement: float = 0.02,
    ) -> None:
        self._collector = FeedbackCollector(feedback_window=feedback_window)
        self._strategy = StrategyAdapter(evolver=evolver, lesson_extractor=lesson_extractor)
        self._metacog = metacog
        self._min_improvement = min_improvement
        self._adaptations_count = 0

    async def post_run_adaptation(
        self,
        result: PipelineResult,
        params: dict,
        run_id: str = "",
    ) -> dict:
        """Collect feedback, check plateaus, extract lessons, adapt params."""
        # 1. Build feedback from result
        feedback = self._build_feedback(result, run_id)
        self._collector.record(feedback)

        # 2. Check for plateaus
        adaptation_input: dict = {"lessons": feedback.lessons}

        for metric in ("avg_idea_score", "avg_novelty_score"):
            if self._collector.detect_plateau(metric, self._min_improvement):
                logger.info("Plateau detected on %s", metric)
                adaptation_input["metric"] = metric

        # 3. Extract lessons via LessonExtractor
        if self._strategy._lesson_extractor is not None:
            try:
                extracted = await self._strategy._lesson_extractor.extract(result, params)
                feedback.lessons.extend(extracted)
                adaptation_input["lessons"] = feedback.lessons
            except Exception as e:
                logger.warning("Lesson extraction failed: %s", e)

        # 4. Adapt params
        if adaptation_input.get("metric") or adaptation_input.get("lessons"):
            adapted = await self._strategy.adapt(adaptation_input, params)
            self._adaptations_count += 1
            logger.info("Adapted params for run %s", run_id)
            return adapted

        return dict(params)

    def _build_feedback(self, result: PipelineResult, run_id: str) -> RunFeedback:
        """Extract RunFeedback from a PipelineResult."""
        ideas = result.ideas
        avg_score = sum(i.score for i in ideas) / len(ideas) if ideas else 0.0

        novelty_scores = [
            report.novelty_score
            for report in result.novelty_reports.values()
            if hasattr(report, "novelty_score")
        ]
        avg_novelty = sum(novelty_scores) / len(novelty_scores) if novelty_scores else 0.0

        return RunFeedback(
            run_id=run_id or result.run_id,
            avg_idea_score=avg_score,
            avg_novelty_score=avg_novelty,
            idea_count=len(ideas),
            timestamp=datetime.now(),
        )

    def get_adaptation_report(self) -> dict:
        """Return summary of adaptation state."""
        return {
            "adaptations_count": self._adaptations_count,
            "feedback_summary": self._collector.summary(),
        }
