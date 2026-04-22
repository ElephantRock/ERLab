"""Tests for feedback collector."""

import pytest

from backend.pipeline.adaptation.feedback import FeedbackCollector, RunFeedback


def _make_feedback(run_id: str = "r1", avg_score: float = 0.5, novelty: float = 0.5,
                   lessons: list[str] | None = None) -> RunFeedback:
    return RunFeedback(
        run_id=run_id,
        avg_idea_score=avg_score,
        avg_novelty_score=novelty,
        idea_count=3,
        lessons=lessons or [],
    )


class TestRunFeedback:
    def test_default_values(self):
        fb = RunFeedback(run_id="test")
        assert fb.avg_idea_score == 0.0
        assert fb.avg_novelty_score == 0.0
        assert fb.idea_count == 0
        assert fb.lessons == []

    def test_with_lessons(self):
        fb = _make_feedback(lessons=["lesson a", "lesson b"])
        assert len(fb.lessons) == 2


class TestFeedbackCollector:
    def test_record_and_summary(self):
        collector = FeedbackCollector(feedback_window=5)
        collector.record(_make_feedback("r1", avg_score=0.6))
        summary = collector.summary()
        assert summary["runs_recorded"] == 1
        assert summary["latest_run_id"] == "r1"

    def test_summary_empty(self):
        collector = FeedbackCollector()
        assert collector.summary() == {"runs_recorded": 0}

    def test_window_trims_old_entries(self):
        collector = FeedbackCollector(feedback_window=3)
        for i in range(5):
            collector.record(_make_feedback(f"r{i}", avg_score=0.5 + i * 0.1))
        assert collector.summary()["runs_recorded"] == 3

    def test_get_trend(self):
        collector = FeedbackCollector(feedback_window=5)
        for score in [0.3, 0.4, 0.5]:
            collector.record(_make_feedback(avg_score=score))
        trend = collector.get_trend("avg_idea_score")
        assert trend == [0.3, 0.4, 0.5]

    def test_get_trend_empty(self):
        collector = FeedbackCollector()
        assert collector.get_trend("avg_idea_score") == []

    def test_get_trend_invalid_metric(self):
        collector = FeedbackCollector()
        collector.record(_make_feedback())
        assert collector.get_trend("nonexistent_metric") == []

    def test_detect_plateau_true(self):
        collector = FeedbackCollector(feedback_window=5)
        for _ in range(3):
            collector.record(_make_feedback(avg_score=0.5))
        assert collector.detect_plateau("avg_idea_score", min_improvement=0.02) is True

    def test_detect_plateau_false(self):
        collector = FeedbackCollector(feedback_window=5)
        collector.record(_make_feedback(avg_score=0.3))
        collector.record(_make_feedback(avg_score=0.8))
        assert collector.detect_plateau("avg_idea_score", min_improvement=0.02) is False

    def test_detect_plateau_insufficient_data(self):
        collector = FeedbackCollector()
        collector.record(_make_feedback())
        assert collector.detect_plateau("avg_idea_score") is False

    def test_get_recent_lessons(self):
        collector = FeedbackCollector(feedback_window=5)
        collector.record(_make_feedback(lessons=["a"]))
        collector.record(_make_feedback(lessons=["b", "c"]))
        assert collector.get_recent_lessons() == ["a", "b", "c"]
