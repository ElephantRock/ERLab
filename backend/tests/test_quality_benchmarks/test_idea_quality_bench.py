"""Idea quality score alignment benchmark.

Verifies that the scorer correctly ranks ideas with known quality levels:
high-quality ideas should score higher than medium, which should score
higher than low-quality ones.
"""

import asyncio

from backend.pipeline.evaluation.pipeline_evaluator import PipelineEvaluator
from backend.pipeline.evaluation.scorer import ScoreDimension


class _FakeProvider:
    """Returns scores based on target content to simulate quality ranking."""

    def __init__(self):
        self._call_log = []

    async def complete(self, messages, temperature=0.7, max_tokens=4096) -> str:
        self._call_log.append(messages)
        content = str(messages[-1].get("content", "")) if messages else ""
        if "excellent" in content.lower() or "novel" in content.lower():
            return "0.9"
        if "moderate" in content.lower():
            return "0.6"
        return "0.3"

    async def structured_output(self, messages, schema, temperature=0.3) -> dict:
        self._call_log.append(messages)
        content = str(messages[-1].get("content", "")) if messages else ""
        if "excellent" in content.lower():
            return {"score": 0.9, "strengths": ["Strong"], "weaknesses": []}
        if "moderate" in content.lower():
            return {"score": 0.6, "strengths": ["OK"], "weaknesses": ["Average"]}
        return {"score": 0.3, "strengths": [], "weaknesses": ["Weak"]}


class _FakeNovelty:
    async def check_novelty(self, idea):
        class R:
            overall_score = getattr(idea, "_quality", 0.5)
            method_novelty = overall_score
            problem_novelty = overall_score
            domain_transfer = overall_score
            combination_novelty = overall_score
            novelty_arguments = "Test"
            closest_matches = []
        return R()


class _FakeFeasibility:
    async def score_feasibility(self, idea, novelty_report=None):
        score = getattr(idea, "_quality", 0.5) * 10
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


class _FakeIdea:
    def __init__(self, title, quality):
        self.title = title
        self._quality = quality

    def __str__(self):
        labels = {0.9: "excellent novel breakthrough", 0.6: "moderate incremental", 0.3: "weak derivative"}
        return f"{self.title}: {labels.get(self._quality, 'unknown')}"


class TestIdeaQualityAlignment:
    """Verify scorer ranks ideas by quality correctly."""

    def test_high_medium_low_ranking(self):
        """High-quality ideas should score higher than medium, then low."""
        evaluator = PipelineEvaluator(
            provider=_FakeProvider(),
            novelty_checker=_FakeNovelty(),
            feasibility_scorer=_FakeFeasibility(),
        )
        high = _FakeIdea("Excellent Novel Approach", 0.9)
        med = _FakeIdea("Moderate Incremental Work", 0.6)
        low = _FakeIdea("Weak Derivative Idea", 0.3)

        results = asyncio.run(evaluator.evaluate_all(
            ideas=[high, med, low],
            novelty_reports={0: None, 1: None, 2: None},
            feasibility_reports={0: None, 1: None, 2: None},
        ))

        assert results[0].overall_score >= results[1].overall_score, (
            f"High ({results[0].overall_score}) should >= Medium ({results[1].overall_score})"
        )
        assert results[1].overall_score >= results[2].overall_score, (
            f"Medium ({results[1].overall_score}) should >= Low ({results[2].overall_score})"
        )

    def test_novelty_correlation(self):
        """Novelty scores should correlate with idea quality."""
        evaluator = PipelineEvaluator(
            provider=_FakeProvider(),
            novelty_checker=_FakeNovelty(),
            feasibility_scorer=_FakeFeasibility(),
        )
        high = _FakeIdea("Novel Idea", 0.9)
        low = _FakeIdea("Old Idea", 0.3)

        r_high = asyncio.run(evaluator.evaluate_idea(
            high, novelty_report=None, feasibility_report=None,
        ))
        r_low = asyncio.run(evaluator.evaluate_idea(
            low, novelty_report=None, feasibility_report=None,
        ))

        assert r_high.overall_score >= r_low.overall_score
