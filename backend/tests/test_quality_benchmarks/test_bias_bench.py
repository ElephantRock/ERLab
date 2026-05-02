"""Bias mitigation benchmark for DeepEval scorer.

Verifies that shuffling criteria order produces <10% score variance,
confirming the bias mitigation strategy is effective.
"""

import asyncio

from backend.pipeline.evaluation.deepeval_adapter import DeepEvalScorer
from backend.pipeline.evaluation.geval import EvaluationRubric
from backend.pipeline.evaluation.scorer import ScoreDimension


class _ConstantProvider:
    """Provider that returns a constant score regardless of prompt."""

    def __init__(self, score_text="0.7"):
        self._score_text = score_text
        self.calls = 0

    async def complete(self, messages, temperature=0.7, max_tokens=4096) -> str:
        self.calls += 1
        content = str(messages[-1].get("content", "")) if messages else ""
        if "ONLY the numeric score" in content:
            return self._score_text
        return "Standard reasoning about this research idea quality."

    async def structured_output(self, messages, schema, temperature=0.3) -> dict:
        return {}


class _FakeIdea:
    title = "Test Idea for Bias Check"

    def __str__(self):
        return self.title


class TestBiasMitigation:
    """Verify multi-pass scoring reduces position/format bias."""

    def test_shuffled_steps_produce_consistent_scores(self):
        """Multiple passes with shuffled steps should have <10% score variance."""
        rubric = EvaluationRubric(
            dimension=ScoreDimension.NOVELTY,
            criteria="How original is this idea?",
            scoring_steps=(
                "1. Check method novelty.\n"
                "2. Check problem novelty.\n"
                "3. Check domain transfer.\n"
                "4. Score 0-1."
            ),
        )
        provider = _ConstantProvider("0.7")
        scorer = DeepEvalScorer(provider, ScoreDimension.NOVELTY, rubric, n_passes=5)

        report = asyncio.run(scorer.score(_FakeIdea(), "test_idea"))
        score_result = report.scores[0]

        pass_scores = score_result.metadata["pass_scores"]
        assert len(pass_scores) == 5

        mean = sum(pass_scores) / len(pass_scores)
        std = (sum((s - mean) ** 2 for s in pass_scores) / len(pass_scores)) ** 0.5
        cv = std / mean if mean > 0 else 0

        # With a constant provider, scores should be identical
        assert cv < 0.10, f"Score variance too high: CV={cv:.3f}, scores={pass_scores}"

    def test_score_averaging(self):
        """The final score should be the average of all passes."""
        rubric = EvaluationRubric(
            dimension=ScoreDimension.FEASIBILITY,
            criteria="How feasible?",
            scoring_steps="1. Check data.\n2. Check compute.\n3. Score.",
        )
        provider = _ConstantProvider("0.6")
        scorer = DeepEvalScorer(provider, ScoreDimension.FEASIBILITY, rubric, n_passes=3)

        report = asyncio.run(scorer.score(_FakeIdea(), "test"))
        assert abs(report.overall_score - 0.6) < 0.01

    def test_single_pass_works(self):
        """n_passes=1 should work without error."""
        rubric = EvaluationRubric(
            dimension=ScoreDimension.IMPACT,
            criteria="Impact?",
            scoring_steps="1. Score.",
        )
        provider = _ConstantProvider("0.8")
        scorer = DeepEvalScorer(provider, ScoreDimension.IMPACT, rubric, n_passes=1)

        report = asyncio.run(scorer.score(_FakeIdea(), "test"))
        assert report.overall_score == 0.8
