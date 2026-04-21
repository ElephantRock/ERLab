"""Tests for adapter wrappers that normalize existing scorers."""

import asyncio

from backend.pipeline.evaluation.normalizers import (
    FeasibilityScorerAdapter,
    MechanicalCheckAdapter,
    NoveltyScorerAdapter,
)
from backend.pipeline.evaluation.scorer import ScoreDimension
from backend.pipeline.generation.models import IdeaCandidate


class FakeNoveltyChecker:
    async def check_novelty(self, idea):
        class Report:
            overall_score = 0.75
            method_novelty = 0.8
            problem_novelty = 0.7
            domain_transfer = 0.6
            combination_novelty = 0.9
            novelty_arguments = "Novel combination of techniques"
            closest_matches = []
        return Report()


class FakeFeasibilityScorer:
    async def score_feasibility(self, idea, novelty_report=None):
        class Report:
            overall_score = 7.5  # 0-10 scale
            data_availability = 8.0
            computational_requirements = 7.0
            methodological_complexity = 6.0
            evaluation_plan = 8.0
            novelty_grounding = 7.0
            impact_potential = 9.0
            reasoning = "Feasible within 3-6 months"
            estimated_timeline = "3-6 months"
            key_risks = ["Data collection may take time"]
        return Report()


class TestNoveltyScorerAdapter:
    def test_pass_through_scores(self):
        adapter = NoveltyScorerAdapter(FakeNoveltyChecker())
        report = asyncio.run(adapter.score("fake idea", "id1"))
        assert report.overall_score == 0.75
        assert len(report.scores) == 1
        assert report.scores[0].dimension == ScoreDimension.NOVELTY
        assert report.scores[0].metadata["method_novelty"] == 0.8


class TestFeasibilityScorerAdapter:
    def test_normalizes_0_10_to_0_1(self):
        adapter = FeasibilityScorerAdapter(FakeFeasibilityScorer())
        report = asyncio.run(adapter.score(("idea", None), "id2"))
        assert report.overall_score == 0.75  # 7.5 / 10
        assert report.scores[0].dimension == ScoreDimension.FEASIBILITY
        assert report.scores[0].metadata["timeline"] == "3-6 months"

    def test_sub_dimensions_normalized(self):
        adapter = FeasibilityScorerAdapter(FakeFeasibilityScorer())
        report = asyncio.run(adapter.score(("idea", None), "id3"))
        meta = report.scores[0].metadata
        assert meta["data_availability"] == 0.8  # 8.0 / 10


class TestMechanicalCheckAdapter:
    def test_scores_idea_candidate(self):
        candidate = IdeaCandidate(
            title="A Novel Method for Evaluating AI Agent Frameworks",
            problem_statement="Current evaluation methods are insufficient for measuring agent quality and reliability in production environments",
            proposed_method="We propose a multi-dimensional evaluation framework with rubric-based scoring and deterministic heuristics",
        )
        adapter = MechanicalCheckAdapter()
        report = asyncio.run(adapter.score(candidate, "id4"))
        assert report.scores[0].dimension == ScoreDimension.SOUNDNESS
        assert 0.0 <= report.overall_score <= 1.0
