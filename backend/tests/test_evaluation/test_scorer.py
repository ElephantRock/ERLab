"""Tests for Scorer ABC, fitness evaluation, and composition."""

import asyncio

from backend.pipeline.evaluation.scorer import (
    ChainedScorer,
    ConditionalScorer,
    DimensionScorer,
    FitnessScorer,
    ScoreDimension,
    WeightedCompositeScorer,
)


class TestDimensionScorer:
    def test_score(self):
        asyncio.run(self._test())

    async def _test(self):
        scorer = DimensionScorer(ScoreDimension.NOVELTY, lambda x: 0.8)
        report = await scorer.score("test idea", target_id="t1")
        assert report.overall_score == 0.8
        assert len(report.scores) == 1
        assert report.scores[0].dimension == ScoreDimension.NOVELTY

    def test_weighted(self):
        asyncio.run(self._test_weighted())

    async def _test_weighted(self):
        scorer = DimensionScorer(ScoreDimension.IMPACT, lambda x: 1.0, weight=0.5)
        report = await scorer.score("x")
        assert report.overall_score == 0.5


class TestWeightedCompositeScorer:
    def test_composite(self):
        asyncio.run(self._test())

    async def _test(self):
        scorers = [
            (DimensionScorer(ScoreDimension.NOVELTY, lambda x: 0.9), 0.4),
            (DimensionScorer(ScoreDimension.FEASIBILITY, lambda x: 0.6), 0.3),
            (DimensionScorer(ScoreDimension.IMPACT, lambda x: 0.8), 0.3),
        ]
        composite = WeightedCompositeScorer(scorers)
        report = await composite.score("idea", target_id="c1")
        assert len(report.scores) == 3
        assert 0.0 <= report.overall_score <= 1.0


class TestChainedScorer:
    def test_chain(self):
        asyncio.run(self._test())

    async def _test(self):
        scorer = ChainedScorer(
            [
                DimensionScorer(ScoreDimension.NOVELTY, lambda x: 0.7),
                DimensionScorer(ScoreDimension.FEASIBILITY, lambda x: 0.5),
            ]
        )
        report = await scorer.score("idea")
        assert len(report.scores) == 2

    def test_stop_on_fail(self):
        asyncio.run(self._test_stop())

    async def _test_stop(self):
        scorer = ChainedScorer(
            [
                DimensionScorer(ScoreDimension.NOVELTY, lambda x: 0.0),
                DimensionScorer(ScoreDimension.FEASIBILITY, lambda x: 0.9),
            ],
            stop_on_fail=True,
        )
        report = await scorer.score("idea")
        assert len(report.scores) == 1


class TestConditionalScorer:
    def test_condition_true(self):
        asyncio.run(self._test_true())

    async def _test_true(self):
        scorer = ConditionalScorer(
            condition=lambda x: len(x) > 5,
            true_scorer=DimensionScorer(ScoreDimension.NOVELTY, lambda x: 0.9),
            false_scorer=DimensionScorer(ScoreDimension.NOVELTY, lambda x: 0.3),
        )
        report = await scorer.score("long enough idea")
        assert report.overall_score == 0.9

    def test_condition_false(self):
        asyncio.run(self._test_false())

    async def _test_false(self):
        scorer = ConditionalScorer(
            condition=lambda x: len(x) > 100,
            true_scorer=DimensionScorer(ScoreDimension.NOVELTY, lambda x: 0.9),
            false_scorer=DimensionScorer(ScoreDimension.NOVELTY, lambda x: 0.3),
        )
        report = await scorer.score("short")
        assert report.overall_score == 0.3


class TestFitnessScorer:
    def test_fitness(self):
        asyncio.run(self._test())

    async def _test(self):
        scorer = FitnessScorer(
            novelty_fn=lambda x: 0.8,
            feasibility_fn=lambda x: 0.7,
            impact_fn=lambda x: 0.6,
        )
        report = await scorer.score("test idea", target_id="fit1")
        assert len(report.scores) == 3
        assert report.overall_score > 0


class TestEvaluationReportPassedGate:
    def test_passed_fallback_when_no_threshold(self):
        from backend.pipeline.evaluation.scorer import (
            EvaluationReport,
            ScoreDimension,
            ScoreResult,
        )
        report = EvaluationReport(
            target_id="t1",
            scores=[ScoreResult(dimension=ScoreDimension.NOVELTY, score=0.5)],
            overall_score=0.5,
        )
        assert report.passed is True
        assert report.passed_gate is True

    def test_passed_gate_with_threshold(self):
        from backend.pipeline.evaluation.scorer import (
            EvaluationReport,
            ScoreDimension,
            ScoreResult,
        )
        report = EvaluationReport(
            target_id="t2",
            scores=[ScoreResult(dimension=ScoreDimension.NOVELTY, score=0.3)],
            overall_score=0.3,
            passed_threshold=0.5,
        )
        assert report.passed is True  # > 0.0
        assert report.passed_gate is False  # < 0.5
