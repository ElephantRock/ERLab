"""Unit tests for idea generation agents and orchestrator."""

import asyncio

from backend.pipeline.generation.agent_orchestrator import AgentOrchestrator
from backend.pipeline.generation.critic_agent import CriticAgent
from backend.pipeline.generation.ideator_agent import IdeatorAgent
from backend.pipeline.generation.models import Critique, IdeaCandidate, ResearchIdea
from backend.pipeline.generation.refiner_agent import RefinerAgent
from backend.pipeline.literature.models import Paper
from backend.tests.test_pipeline.conftest import SchemaAwareFakeProvider


def _many_context_papers(n=10):
    return [
        Paper(
            id=f"p{i}",
            source="test",
            title=f"Context Paper {i}",
            abstract=f"Abstract for context paper {i}",
            year=2024,
        )
        for i in range(n)
    ]


class TestIdeatorAgent:
    def test_generate_ideas(self, sample_gaps, sample_papers):
        agent = IdeatorAgent(SchemaAwareFakeProvider())
        ideas = asyncio.run(agent.generate_ideas(sample_gaps, sample_papers, n_ideas=3))
        assert isinstance(ideas, list)
        for idea in ideas:
            assert isinstance(idea, IdeaCandidate)
            assert idea.title
            assert idea.proposed_method

    def test_llm_failure_empty(self, sample_gaps, sample_papers):
        provider = SchemaAwareFakeProvider()

        async def _fail(*args, **kwargs):
            raise RuntimeError("fail")

        provider.structured_output = _fail
        agent = IdeatorAgent(provider)
        ideas = asyncio.run(agent.generate_ideas(sample_gaps, sample_papers))
        assert ideas == []

    def test_build_context(self, sample_gaps, sample_papers):
        context = IdeatorAgent._build_context(sample_gaps, sample_papers)
        assert "Test Gap 1" in context
        assert "Test Paper 1" in context
        assert "Research Gaps" in context

    def test_with_prior_critique(self, sample_gaps, sample_papers):
        provider = SchemaAwareFakeProvider()
        agent = IdeatorAgent(provider)
        asyncio.run(
            agent.generate_ideas(
                sample_gaps, sample_papers, prior_critique=["Previous feedback"]
            )
        )
        assert len(provider._call_log) == 1


class TestCriticAgent:
    def test_critique_ideas(self, sample_candidates, sample_papers):
        agent = CriticAgent(SchemaAwareFakeProvider())
        critiques = asyncio.run(agent.critique_ideas(sample_candidates, sample_papers))
        assert isinstance(critiques, list)
        for c in critiques:
            assert isinstance(c, Critique)
            assert c.idea_title
            assert isinstance(c.weaknesses, list)
            assert isinstance(c.suggestions, list)

    def test_llm_failure_fallback(self, sample_candidates, sample_papers):
        provider = SchemaAwareFakeProvider()

        async def _fail(*args, **kwargs):
            raise RuntimeError("fail")

        provider.structured_output = _fail
        agent = CriticAgent(provider)
        critiques = asyncio.run(agent.critique_ideas(sample_candidates, sample_papers))
        assert len(critiques) == len(sample_candidates)
        assert "Critique failed" in critiques[0].overall_assessment

    def test_format_mechanical_flags(self, sample_candidates):
        flags = CriticAgent._format_mechanical_flags(sample_candidates)
        # Flags may be empty if candidates pass all checks — just verify no crash
        assert isinstance(flags, str)

    def test_format_ideas(self, sample_candidates):
        result = CriticAgent._format_ideas(sample_candidates)
        assert "Candidate A" in result
        assert "Candidate B" in result
        assert "Method A" in result


class TestRefinerAgent:
    def test_refine_ideas(self, sample_candidates, sample_critiques, sample_papers):
        agent = RefinerAgent(SchemaAwareFakeProvider())
        refined = asyncio.run(
            agent.refine_ideas(sample_candidates, sample_critiques, sample_papers)
        )
        assert isinstance(refined, list)
        for idea in refined:
            assert isinstance(idea, ResearchIdea)
            assert idea.title
            assert 0 <= idea.score <= 1.0
        if len(refined) > 1:
            for i in range(len(refined) - 1):
                assert refined[i].score >= refined[i + 1].score

    def test_llm_failure_fallback(self, sample_candidates, sample_critiques, sample_papers):
        provider = SchemaAwareFakeProvider()

        async def _fail(*args, **kwargs):
            raise RuntimeError("fail")

        provider.structured_output = _fail
        agent = RefinerAgent(provider)
        refined = asyncio.run(
            agent.refine_ideas(sample_candidates, sample_critiques, sample_papers)
        )
        assert len(refined) == len(sample_candidates)
        assert all(idea.score == 0.3 for idea in refined)

    def test_format_critiques(self, sample_critiques):
        result = RefinerAgent._format_critiques(sample_critiques)
        assert "Critique of: Idea A" in result
        assert "Weaknesses" in result
        assert "Suggestions" in result

    def test_sets_round_number(self, sample_candidates, sample_critiques, sample_papers):
        agent = RefinerAgent(SchemaAwareFakeProvider())
        refined = asyncio.run(
            agent.refine_ideas(
                sample_candidates, sample_critiques, sample_papers, round_num=3
            )
        )
        assert all(idea.round_generated == 3 for idea in refined)


class TestAgentOrchestrator:
    def test_run_single_round(self, sample_gaps):
        papers = _many_context_papers()
        orch = AgentOrchestrator(SchemaAwareFakeProvider())
        ideas = asyncio.run(
            orch.run(sample_gaps, papers, rounds=1, ideas_per_round=2)
        )
        assert isinstance(ideas, list)
        assert len(ideas) >= 1

    def test_run_multiple_rounds(self, sample_gaps):
        papers = _many_context_papers()
        orch = AgentOrchestrator(SchemaAwareFakeProvider())
        ideas = asyncio.run(
            orch.run(sample_gaps, papers, rounds=2, ideas_per_round=2)
        )
        assert isinstance(ideas, list)
        assert len(ideas) >= 1

    def test_run_convergence_breaks_early(self, sample_gaps):
        papers = _many_context_papers()
        orch = AgentOrchestrator(SchemaAwareFakeProvider())
        ideas = asyncio.run(
            orch.run(sample_gaps, papers, rounds=3, ideas_per_round=2)
        )
        assert isinstance(ideas, list)

    def test_run_empty_ideation_skips_round(self, sample_gaps):
        provider = SchemaAwareFakeProvider()
        call_count = 0
        original = provider.structured_output

        async def _structured_once(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"ideas": []}
            return await original(*args, **kwargs)

        provider.structured_output = _structured_once
        papers = _many_context_papers()
        orch = AgentOrchestrator(provider)
        ideas = asyncio.run(orch.run(sample_gaps, papers, rounds=2, ideas_per_round=2))
        assert isinstance(ideas, list)

    def test_quality_gate_filters_low_scores(self, sample_gaps):
        papers = _many_context_papers()
        orch = AgentOrchestrator(SchemaAwareFakeProvider())
        ideas = asyncio.run(
            orch.run(sample_gaps, papers, rounds=1, ideas_per_round=3)
        )
        for idea in ideas:
            assert idea.score >= 0.3

    def test_with_borda(self, sample_gaps):
        papers = _many_context_papers()
        orch = AgentOrchestrator(SchemaAwareFakeProvider())
        ideas = asyncio.run(
            orch.run(sample_gaps, papers, rounds=2, ideas_per_round=2, use_borda=True)
        )
        assert isinstance(ideas, list)
