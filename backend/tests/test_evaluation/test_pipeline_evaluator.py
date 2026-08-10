"""Tests for the unified pipeline evaluator."""

import asyncio

from backend.pipeline.evaluation.cache import EvaluationCache
from backend.pipeline.evaluation.pipeline_evaluator import PipelineEvaluator
from backend.pipeline.evaluation.quality_gate import (
    QualityGate,
    QualityGateConfig,
    QualityThreshold,
)
from backend.pipeline.evaluation.scorer import ScoreDimension


class FakeNoveltyChecker:
    async def check_novelty(self, idea):
        class Report:
            overall_score = 0.75
            method_novelty = 0.8
            problem_novelty = 0.7
            domain_transfer = 0.6
            combination_novelty = 0.9
            novelty_arguments = "Novel approach"
            closest_matches = []
        return Report()


class FakeFeasibilityScorer:
    async def score_feasibility(self, idea, novelty_report=None):
        class Report:
            overall_score = 7.0
            data_availability = 7.0
            computational_requirements = 7.0
            methodological_complexity = 7.0
            evaluation_plan = 7.0
            novelty_grounding = 7.0
            impact_potential = 7.0
            reasoning = "Reasonable"
            estimated_timeline = "3-6 months"
            key_risks = ["Some risk"]
        return Report()


class FakeIdea:
    def __init__(self, title="Test Idea"):
        self.title = title


def _make_evaluator(use_geval=False, quality_gate=None):
    from backend.tests.conftest import FakeLLMProvider
    return PipelineEvaluator(
        provider=FakeLLMProvider(),
        novelty_checker=FakeNoveltyChecker(),
        feasibility_scorer=FakeFeasibilityScorer(),
        quality_gate=quality_gate,
        use_geval=use_geval,
        cache=EvaluationCache(max_size=10),
    )


def _make_novelty_report(score=0.75):
    class R:
        overall_score = score
        method_novelty = score
        problem_novelty = score
        domain_transfer = score
        combination_novelty = score
        novelty_arguments = "Test rationale"
        closest_matches = []
    return R()


def _make_feasibility_report(score=7.0):
    class R:
        overall_score = score
        data_availability = score
        computational_requirements = score
        methodological_complexity = score
        evaluation_plan = score
        novelty_grounding = score
        impact_potential = score
        reasoning = "Test"
        estimated_timeline = "3-6 months"
        key_risks = []
    return R()


class TestPipelineEvaluator:
    def test_evaluate_single_idea(self):
        evaluator = _make_evaluator()
        report = asyncio.run(evaluator.evaluate_idea(
            idea=FakeIdea(),
            novelty_report=_make_novelty_report(0.8),
            feasibility_report=_make_feasibility_report(8.0),
            target_id="idea_0",
        ))
        assert "novelty" in report.dimension_scores
        assert "feasibility" in report.dimension_scores
        assert report.dimension_scores["novelty"].score == 0.8
        assert report.dimension_scores["feasibility"].score == 0.8  # 8.0/10
        assert report.overall_score > 0

    def test_evaluate_all(self):
        evaluator = _make_evaluator()
        ideas = [FakeIdea("Idea 1"), FakeIdea("Idea 2")]
        novelty = {0: _make_novelty_report(), 1: _make_novelty_report(0.6)}
        feasibility = {0: _make_feasibility_report(), 1: _make_feasibility_report(5.0)}
        results = asyncio.run(evaluator.evaluate_all(ideas, novelty, feasibility))
        assert len(results) == 2
        assert results[0].overall_score > results[1].overall_score

    def test_with_quality_gate(self):
        config = QualityGateConfig(
            thresholds=[
                QualityThreshold(dimension=ScoreDimension.NOVELTY, min_score=0.5, weight=0.5),
                QualityThreshold(dimension=ScoreDimension.FEASIBILITY, min_score=0.5, weight=0.5),
            ],
            composite_threshold=0.5,
        )
        evaluator = _make_evaluator(quality_gate=QualityGate(config))
        report = asyncio.run(evaluator.evaluate_idea(
            idea=FakeIdea(),
            novelty_report=_make_novelty_report(0.8),
            feasibility_report=_make_feasibility_report(8.0),
        ))
        assert report.quality_gate_result is not None
        assert report.quality_gate_result.passed

    def test_quality_gate_failure(self):
        config = QualityGateConfig(
            thresholds=[
                QualityThreshold(dimension=ScoreDimension.NOVELTY, min_score=0.9, weight=1.0),
            ],
            composite_threshold=0.9,
        )
        evaluator = _make_evaluator(quality_gate=QualityGate(config))
        report = asyncio.run(evaluator.evaluate_idea(
            idea=FakeIdea(),
            novelty_report=_make_novelty_report(0.3),
            feasibility_report=_make_feasibility_report(3.0),
        ))
        assert not report.quality_gate_result.passed

    def test_cost_summary_empty(self):
        evaluator = _make_evaluator()
        summary = evaluator.cost_summary()
        assert summary["eval_count"] == 0
