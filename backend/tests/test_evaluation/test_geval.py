"""Tests for GEval-style rubric scorer."""

import asyncio

from backend.pipeline.evaluation.cache import EvaluationCache
from backend.pipeline.evaluation.geval import DEFAULT_RUBRICS, EvaluationRubric, GEvalScorer
from backend.pipeline.evaluation.scorer import ScoreDimension
from backend.tests.conftest import FakeLLMProvider


class TestEvaluationRubric:
    def test_default_rubrics_exist(self):
        assert len(DEFAULT_RUBRICS) == 7
        for dim in ScoreDimension:
            assert dim in DEFAULT_RUBRICS

    def test_custom_rubric(self):
        rubric = EvaluationRubric(
            dimension=ScoreDimension.CLARITY,
            criteria="Is it clear?",
            scoring_steps="1. Read. 2. Score.",
        )
        assert rubric.dimension == ScoreDimension.CLARITY
        assert rubric.scale_min == 0.0
        assert rubric.scale_max == 1.0


class TestGEvalScorer:
    def test_score_extraction(self):
        provider = FakeLLMProvider(
            responses={"complete": "0.8"}
        )
        rubric = DEFAULT_RUBRICS[ScoreDimension.NOVELTY]
        scorer = GEvalScorer(provider, rubric)
        report = asyncio.run(scorer.score("test idea", "id1"))
        assert report.overall_score == 0.8
        assert report.scores[0].dimension == ScoreDimension.NOVELTY

    def test_score_clamped(self):
        provider = FakeLLMProvider(
            responses={"complete": "1.5"}
        )
        rubric = DEFAULT_RUBRICS[ScoreDimension.FEASIBILITY]
        scorer = GEvalScorer(provider, rubric)
        report = asyncio.run(scorer.score("test idea", "id2"))
        assert report.overall_score <= 1.0

    def test_parse_failure_defaults(self):
        provider = FakeLLMProvider(
            responses={"complete": "not a number"}
        )
        rubric = DEFAULT_RUBRICS[ScoreDimension.IMPACT]
        scorer = GEvalScorer(provider, rubric)
        report = asyncio.run(scorer.score("test idea", "id3"))
        assert report.overall_score == 0.5  # default on parse failure

    def test_caching(self):
        call_count = 0
        class CountingProvider(FakeLLMProvider):
            async def complete(self, messages, temperature=0.7, max_tokens=4096):
                nonlocal call_count
                call_count += 1
                return "0.7"

        cache = EvaluationCache(max_size=10)
        provider = CountingProvider()
        rubric = DEFAULT_RUBRICS[ScoreDimension.CLARITY]
        scorer = GEvalScorer(provider, rubric, cache=cache)

        # First call: miss
        r1 = asyncio.run(scorer.score("test idea", "id4"))
        assert call_count == 2  # reasoning + score extraction

        # Second call: hit
        r2 = asyncio.run(scorer.score("test idea", "id4"))
        assert call_count == 2  # no new calls
        assert r2.overall_score == r1.overall_score
