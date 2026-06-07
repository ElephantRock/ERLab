"""Unit tests for feasibility scoring stage."""

import asyncio

from backend.pipeline.feasibility.feasibility_scorer import (
    FeasibilityReport,
    FeasibilityScorer,
)
from backend.tests.conftest import FakeLLMProvider
from backend.tests.test_pipeline.conftest import SchemaAwareFakeProvider


class TestFeasibilityScorer:
    def test_score_happy_path(self, sample_ideas):
        scorer = FeasibilityScorer(SchemaAwareFakeProvider())
        report = asyncio.run(scorer.score_feasibility(sample_ideas[0]))
        assert isinstance(report, FeasibilityReport)
        assert 0 <= report.overall_score <= 10
        assert isinstance(report.data_availability, float)
        assert isinstance(report.computational_requirements, float)
        assert isinstance(report.methodological_complexity, float)
        assert isinstance(report.evaluation_plan, float)
        assert isinstance(report.novelty_grounding, float)
        assert isinstance(report.impact_potential, float)
        assert isinstance(report.reasoning, str)
        assert isinstance(report.estimated_timeline, str)
        assert isinstance(report.key_risks, list)

    def test_with_novelty_report(self, sample_ideas, sample_novelty_report):
        scorer = FeasibilityScorer(SchemaAwareFakeProvider())
        report = asyncio.run(
            scorer.score_feasibility(sample_ideas[0], novelty_report=sample_novelty_report)
        )
        assert isinstance(report, FeasibilityReport)

    def test_without_novelty_report(self, sample_ideas):
        scorer = FeasibilityScorer(SchemaAwareFakeProvider())
        report = asyncio.run(
            scorer.score_feasibility(sample_ideas[0], novelty_report=None)
        )
        assert isinstance(report, FeasibilityReport)

    def test_llm_failure_returns_default_5(self, sample_ideas):
        provider = SchemaAwareFakeProvider()

        async def _fail(*args, **kwargs):
            raise RuntimeError("timeout")

        provider.structured_output = _fail
        scorer = FeasibilityScorer(provider)
        report = asyncio.run(scorer.score_feasibility(sample_ideas[0]))
        assert report.overall_score == 5.0
        assert report.data_availability == 5.0
        assert "Scoring evaluation failed" in report.key_risks

    def test_call_log_captured(self, sample_ideas):
        provider = SchemaAwareFakeProvider()
        scorer = FeasibilityScorer(provider)
        asyncio.run(scorer.score_feasibility(sample_ideas[0]))
        assert len(provider._call_log) == 1
        assert provider._call_log[0]["method"] == "structured_output"


class TestFeasibilityReport:
    def test_stores_all_fields(self):
        report = FeasibilityReport(
            overall_score=7.0,
            data_availability=8.0,
            computational_requirements=6.0,
            methodological_complexity=5.0,
            evaluation_plan=7.0,
            novelty_grounding=8.0,
            impact_potential=9.0,
            reasoning="Test reasoning",
            estimated_timeline="6 months",
            key_risks=["risk1", "risk2"],
        )
        assert report.overall_score == 7.0
        assert report.reasoning == "Test reasoning"
        assert report.key_risks == ["risk1", "risk2"]

    def test_key_risks_is_list(self):
        report = FeasibilityReport(
            overall_score=5.0,
            data_availability=5.0,
            computational_requirements=5.0,
            methodological_complexity=5.0,
            evaluation_plan=5.0,
            novelty_grounding=5.0,
            impact_potential=5.0,
            reasoning="",
            estimated_timeline="",
            key_risks=["a"],
        )
        assert isinstance(report.key_risks, list)

    def test_overall_score_is_float(self):
        report = FeasibilityReport(
            overall_score=5.0,
            data_availability=5.0,
            computational_requirements=5.0,
            methodological_complexity=5.0,
            evaluation_plan=5.0,
            novelty_grounding=5.0,
            impact_potential=5.0,
            reasoning="",
            estimated_timeline="",
            key_risks=[],
        )
        assert isinstance(report.overall_score, float)
