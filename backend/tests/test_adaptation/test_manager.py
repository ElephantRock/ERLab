"""Tests for adaptation manager."""

import pytest

from backend.pipeline.adaptation.manager import AdaptationManager
from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.result import PipelineResult


class FakeEvolver:
    def apply_lessons(self, lessons, params):
        return dict(params)


class FakeLessonExtractor:
    async def extract(self, result, params):
        if not result.ideas:
            return ["No ideas generated — consider expanding search"]
        return []


def _make_idea(score: float = 0.5) -> ResearchIdea:
    return ResearchIdea(
        title="Test idea",
        problem_statement="Test problem",
        proposed_method="Test method",
        expected_contributions="Test contributions",
        novelty_rationale="Test rationale",
        evaluation_approach="Test approach",
        score=score,
    )


def _make_result(ideas: list[ResearchIdea] | None = None, run_id: str = "test_run") -> PipelineResult:
    return PipelineResult(ideas=ideas or [], run_id=run_id)


@pytest.fixture
def manager():
    return AdaptationManager(
        evolver=FakeEvolver(),
        lesson_extractor=FakeLessonExtractor(),
        feedback_window=5,
        min_improvement=0.02,
    )


class TestAdaptationManagerPostRun:
    @pytest.mark.anyio
    async def test_no_adaptation_on_single_run(self, manager):
        result = _make_result([_make_idea(0.5)])
        adapted = await manager.post_run_adaptation(result, {"generation_rounds": 2})
        assert adapted == {"generation_rounds": 2}

    @pytest.mark.anyio
    async def test_adaptation_report_initial(self, manager):
        report = manager.get_adaptation_report()
        assert report["adaptations_count"] == 0
        assert report["feedback_summary"]["runs_recorded"] == 0

    @pytest.mark.anyio
    async def test_records_feedback(self, manager):
        result = _make_result([_make_idea(0.7)], run_id="r1")
        await manager.post_run_adaptation(result, {})
        report = manager.get_adaptation_report()
        assert report["feedback_summary"]["runs_recorded"] == 1

    @pytest.mark.anyio
    async def test_plateau_triggers_adaptation(self, manager):
        # Run several times with same scores to create a plateau
        for i in range(3):
            result = _make_result([_make_idea(0.5)], run_id=f"r{i}")
            await manager.post_run_adaptation(result, {"generation_rounds": 2})
        report = manager.get_adaptation_report()
        assert report["adaptations_count"] >= 1

    @pytest.mark.anyio
    async def test_lessons_from_empty_result(self, manager):
        result = _make_result([], run_id="empty_run")
        adapted = await manager.post_run_adaptation(result, {"generation_rounds": 2})
        # Lesson extractor should have been called
        report = manager.get_adaptation_report()
        assert report["feedback_summary"]["runs_recorded"] == 1

    @pytest.mark.anyio
    async def test_build_feedback_extracts_scores(self, manager):
        result = _make_result([_make_idea(0.8), _make_idea(0.6)], run_id="scored")
        feedback = manager._build_feedback(result, "scored")
        assert feedback.avg_idea_score == pytest.approx(0.7)
        assert feedback.idea_count == 2

    @pytest.mark.anyio
    async def test_original_params_returned_when_no_changes(self, manager):
        params = {"generation_rounds": 2, "ideas_per_round": 3}
        result = _make_result([_make_idea(0.9)], run_id="good_run")
        adapted = await manager.post_run_adaptation(result, params)
        assert adapted == params

    @pytest.mark.anyio
    async def test_multiple_runs_accumulate_feedback(self, manager):
        for score in [0.3, 0.5, 0.7]:
            result = _make_result([_make_idea(score)], run_id=f"r_{score}")
            await manager.post_run_adaptation(result, {})
        report = manager.get_adaptation_report()
        assert report["feedback_summary"]["runs_recorded"] == 3
