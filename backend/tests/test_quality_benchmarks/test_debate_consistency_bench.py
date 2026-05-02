"""Debate consistency benchmark.

Runs adversarial debate multiple times on the same idea and verifies
that score variance stays within acceptable bounds (<15%).
"""

import asyncio

from backend.pipeline.evaluation.adversarial_debate import AdversarialDebate


class _DeterministicProvider:
    """Provider that returns deterministic structured outputs for debate."""

    def __init__(self, base_score=0.7):
        self._base_score = base_score
        self._call_count = 0

    async def complete(self, messages, temperature=0.7, max_tokens=4096) -> str:
        return "0.7"

    async def structured_output(self, messages, schema, temperature=0.3) -> dict:
        self._call_count += 1
        props = schema.get("properties", {})
        if "proposal" in props:
            return {"proposal": f"Argument {self._call_count}", "reasoning": "Test reasoning"}
        if "critique" in props:
            return {"critique": "Test critique", "severity": "medium"}
        if "scores" in props:
            return {
                "scores": {"proposal-0": self._base_score},
                "reasoning": "Consistent scoring",
            }
        if "synthesized_proposal" in props:
            return {"synthesized_proposal": "Synthesized", "reasoning": "Test"}
        return {}


class _FakeIdea:
    title = "Test Research Idea"
    problem_statement = "Test problem"
    proposed_method = "Test method"

    def __str__(self):
        return f"{self.title}: {self.problem_statement}"


class TestDebateConsistency:
    """Verify debate produces consistent scores across runs."""

    def test_score_variance_under_threshold(self):
        """Run debate 5x on same idea, verify <15% score variance."""
        scores = []
        for i in range(5):
            provider = _DeterministicProvider(base_score=0.7)
            debate = AdversarialDebate(provider, rounds=1)
            result = asyncio.run(debate.debate(_FakeIdea()))
            scores.append(result.consensus_score)

        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        std_dev = variance ** 0.5
        coeff_var = std_dev / mean if mean > 0 else 0

        assert coeff_var < 0.15, (
            f"Score variance too high: CV={coeff_var:.3f}, scores={scores}"
        )

    def test_debate_result_structure(self):
        """Verify debate returns all expected fields."""
        provider = _DeterministicProvider()
        debate = AdversarialDebate(provider, rounds=1)
        result = asyncio.run(debate.debate(_FakeIdea()))

        assert result.idea_title == "Test Research Idea"
        assert 0.0 <= result.consensus_score <= 1.0
        assert result.rounds_completed == 1
        assert isinstance(result.optimist_arguments, list)
        assert isinstance(result.skeptic_arguments, list)
        assert isinstance(result.contrarian_arguments, list)

    def test_consensus_in_range(self):
        """Consensus score should be within [min, max] of individual scores."""
        provider = _DeterministicProvider(base_score=0.7)
        debate = AdversarialDebate(provider, rounds=1)
        result = asyncio.run(debate.debate(_FakeIdea()))

        individual = [result.optimist_score, result.skeptic_score, result.contrarian_score]
        assert min(individual) - 0.1 <= result.consensus_score <= max(individual) + 0.1
