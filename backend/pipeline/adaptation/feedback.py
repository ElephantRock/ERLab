"""Feedback collector — sliding window of run metrics for trend detection."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RunFeedback(BaseModel):
    """Metrics captured after a pipeline run."""

    run_id: str
    avg_idea_score: float = 0.0
    avg_novelty_score: float = 0.0
    idea_count: int = 0
    token_usage: int = 0
    elapsed_seconds: float = 0.0
    lessons: list[str] = Field(default_factory=list)
    frontier_scores: dict[str, float] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class FeedbackCollector:
    """Sliding window of run feedback for trend and plateau detection."""

    def __init__(self, feedback_window: int = 5) -> None:
        self._window = feedback_window
        self._history: list[RunFeedback] = []

    def record(self, feedback: RunFeedback) -> None:
        """Add a feedback entry, trimming to window size."""
        self._history.append(feedback)
        if len(self._history) > self._window:
            self._history = self._history[-self._window:]

    def get_trend(self, metric: str) -> list[float]:
        """Extract a metric's values across the window."""
        values: list[float] = []
        for fb in self._history:
            val = getattr(fb, metric, None)
            if val is not None and isinstance(val, (int, float)):
                values.append(float(val))
        return values

    def detect_plateau(self, metric: str, min_improvement: float = 0.02) -> bool:
        """True if the metric has not improved by min_improvement over the window."""
        values = self.get_trend(metric)
        if len(values) < 2:
            return False
        earliest = values[0]
        latest = values[-1]
        return (latest - earliest) < min_improvement

    def get_recent_lessons(self) -> list[str]:
        """Aggregate lessons from all recorded feedback."""
        lessons: list[str] = []
        for fb in self._history:
            lessons.extend(fb.lessons)
        return lessons

    def summary(self) -> dict:
        """Return a summary of collected feedback."""
        if not self._history:
            return {"runs_recorded": 0}
        latest = self._history[-1]
        return {
            "runs_recorded": len(self._history),
            "latest_run_id": latest.run_id,
            "latest_avg_score": latest.avg_idea_score,
            "latest_idea_count": latest.idea_count,
            "window_size": self._window,
        }
