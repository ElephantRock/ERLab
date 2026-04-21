"""Tests for the ContextSummarizer."""

import asyncio

import pytest

from backend.pipeline.compaction.summarizer import ContextSummarizer
from backend.pipeline.gap_analysis.models import ResearchGap
from backend.pipeline.generation.models import Critique


class _FakeNoveltyReport:
    def __init__(self):
        self.overall_score = 0.75
        self.method_novelty = 0.8
        self.problem_novelty = 0.7
        self.domain_transfer = 0.6
        self.combination_novelty = 0.9
        self.novelty_arguments = "The method combines X with Y in a novel way."
        self.closest_matches = []


class _FakeFeasibilityReport:
    def __init__(self):
        self.overall_score = 7.5
        self.data_availability = 8.0
        self.computational_requirements = 7.0
        self.methodological_complexity = 6.0
        self.evaluation_plan = 8.0
        self.novelty_grounding = 7.0
        self.impact_potential = 8.0
        self.reasoning = "The approach is feasible given current resources."
        self.estimated_timeline = "6-12 months"
        self.key_risks = ["data quality", "compute costs", "reproducibility"]


class _BrokenProvider:
    """Provider that always raises, forcing fallback."""

    @property
    def provider_name(self):
        return "broken"

    @property
    def default_model(self):
        return "broken"

    async def complete(self, *a, **kw):
        raise RuntimeError("API down")

    async def complete_stream(self, *a, **kw):
        yield ""

    async def structured_output(self, *a, **kw):
        return {}

    async def embed(self, texts):
        return []


@pytest.fixture
def summarizer(fake_provider):
    return ContextSummarizer(fake_provider)


class TestSummarizeGaps:
    def test_returns_string(self, summarizer):
        gaps = [
            ResearchGap(title="Gap 1", description="Desc 1", gap_type="method", confidence=0.9),
            ResearchGap(title="Gap 2", description="Desc 2", gap_type="empirical", confidence=0.7),
        ]
        result = asyncio.run(summarizer.summarize_gaps(gaps))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_fallback_on_provider_error(self):
        summarizer = ContextSummarizer(_BrokenProvider())
        gaps = [ResearchGap(title="Gap", description="Desc", gap_type="test", confidence=0.5)]
        result = asyncio.run(summarizer.summarize_gaps(gaps))
        assert "Gap" in result

    def test_empty_gaps(self, summarizer):
        result = asyncio.run(summarizer.summarize_gaps([]))
        assert isinstance(result, str)


class TestSummarizeCritiques:
    def test_returns_compact_summary(self, summarizer):
        critiques = [
            Critique(
                idea_title="Idea A",
                weaknesses=["weak eval", "incremental"],
                suggestions=["add ablation", "try new domain"],
                overall_assessment="promising but needs work",
            ),
        ]
        result = asyncio.run(summarizer.summarize_critiques(critiques))
        assert isinstance(result, str)


class TestSummarizeReports:
    def test_returns_compact_summary(self, summarizer):
        result = asyncio.run(
            summarizer.summarize_reports(_FakeNoveltyReport(), _FakeFeasibilityReport())
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_fallback_includes_scores(self):
        summarizer = ContextSummarizer(_BrokenProvider())
        result = asyncio.run(
            summarizer.summarize_reports(_FakeNoveltyReport(), _FakeFeasibilityReport())
        )
        assert "0.75" in result
        assert "7.5" in result
