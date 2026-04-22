"""Tests for strategy adapter."""

import pytest

from backend.pipeline.adaptation.strategy import StrategyAdapter


class FakeEvolver:
    def apply_lessons(self, lessons, params):
        adjusted = dict(params)
        for lesson in lessons:
            if "temperature" in lesson.lower():
                adjusted["ideator_temperature"] = adjusted.get("ideator_temperature", 0.7) + 0.1
        return adjusted


class FakeLessonExtractor:
    pass


@pytest.fixture
def evolver():
    return FakeEvolver()


@pytest.fixture
def adapter(evolver):
    return StrategyAdapter(evolver=evolver, lesson_extractor=FakeLessonExtractor())


class TestStrategyAdapter:
    @pytest.mark.anyio
    async def test_no_changes_when_no_feedback(self, adapter):
        params = {"generation_rounds": 2}
        result = await adapter.adapt({}, params)
        assert result == params

    @pytest.mark.anyio
    async def test_plateau_response_idea_score(self, adapter):
        params = {"generation_rounds": 2, "ideas_per_round": 3}
        result = await adapter.adapt({"metric": "avg_idea_score"}, params)
        assert result["generation_rounds"] == 3
        assert result["ideas_per_round"] == 4

    @pytest.mark.anyio
    async def test_plateau_response_novelty_score(self, adapter):
        params = {"ideator_temperature": 0.7, "refiner_temperature": 0.8}
        result = await adapter.adapt({"metric": "avg_novelty_score"}, params)
        assert result["ideator_temperature"] == pytest.approx(0.8)
        assert result["refiner_temperature"] == pytest.approx(0.9)

    @pytest.mark.anyio
    async def test_plateau_response_caps_at_max(self, adapter):
        params = {"generation_rounds": 7, "ideas_per_round": 9}
        result = await adapter.adapt({"metric": "avg_idea_score"}, params)
        assert result["generation_rounds"] == 8
        assert result["ideas_per_round"] == 10

    @pytest.mark.anyio
    async def test_lesson_feedback_delegated(self, evolver, adapter):
        params = {"ideator_temperature": 0.5}
        result = await adapter.adapt(
            {"lessons": ["increase temperature for diversity"]},
            params,
        )
        assert result["ideator_temperature"] == pytest.approx(0.6)

    @pytest.mark.anyio
    async def test_both_plateau_and_lessons(self, adapter):
        params = {"generation_rounds": 2, "ideator_temperature": 0.5}
        result = await adapter.adapt(
            {"metric": "avg_idea_score", "lessons": ["increase temperature for diversity"]},
            params,
        )
        assert result["generation_rounds"] == 3
        assert result["ideator_temperature"] == pytest.approx(0.6)

    @pytest.mark.anyio
    async def test_no_evolver_lessons_passthrough(self):
        adapter = StrategyAdapter(evolver=None)
        params = {"generation_rounds": 2}
        result = await adapter.adapt({"lessons": ["some lesson"]}, params)
        assert result == params

    @pytest.mark.anyio
    async def test_original_params_not_mutated(self, adapter):
        params = {"generation_rounds": 2}
        original = dict(params)
        await adapter.adapt({"metric": "avg_idea_score"}, params)
        assert params == original
