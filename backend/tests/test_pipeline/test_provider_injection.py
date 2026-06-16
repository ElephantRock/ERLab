"""Regression tests: provider injection does not mutate shared service state.

These tests prove that calling a service's entry-point with a provider
keyword argument does not mutate the service's _provider attribute.
This guards against reintroduction of the _override_provider mutation pattern.

The contract: provider injection is method-scoped — the service accepts
an optional provider kwarg, uses it for that call, and never writes to
self._provider.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.pipeline.gap_analysis.gap_analyzer import GapAnalyzer
from backend.pipeline.feasibility.feasibility_scorer import FeasibilityScorer
from backend.pipeline.synthesis.proposal_synthesizer import ProposalSynthesizer
from backend.pipeline.generation.agent_orchestrator import AgentOrchestrator
from backend.providers.base import LLMProvider


class FakeProvider:
    """Minimal provider for testing."""

    def __init__(self, name: str = "default"):
        self.name = name

    async def complete(self, **kwargs):
        return '{"test": true}'

    async def structured_output(self, **kwargs):
        return {"test": True}


class OverrideProvider:
    """A second distinct provider for override testing."""

    def __init__(self, name: str = "override"):
        self.name = name

    async def complete(self, **kwargs):
        return '{"overridden": true}'

    async def structured_output(self, **kwargs):
        return {"overridden": True}


class TestGapAnalyzerNoMutation:
    def test_provider_not_mutated(self):
        """GapAnalyzer._provider must be unchanged after analyze() with provider kwarg."""
        original = FakeProvider("original")
        override = OverrideProvider("override")
        analyzer = GapAnalyzer(provider=original)

        # Mock cluster_service to avoid needing real papers
        analyzer._cluster_service = MagicMock()
        analyzer._cluster_service.cluster_papers = AsyncMock(
            return_value=MagicMock(clusters=[], paper_count=0)
        )

        # Call with override — the method will use override.complete()
        # but must NOT change analyzer._provider
        try:
            asyncio.run(analyzer.analyze([], provider=override))
        except Exception:
            pass  # We don't care about the result, only about mutation

        assert analyzer._provider is original, (
            "GapAnalyzer._provider was mutated — provider injection must be "
            "method-scoped, not a mutation of shared service state"
        )

    def test_override_provider_is_used(self):
        """When provider kwarg is given, GapAnalyzer uses it, not self._provider."""
        original = FakeProvider("original")
        override = OverrideProvider("override")

        # Track which provider gets called
        call_log: list[str] = []

        async def spy_complete(**kwargs):
            call_log.append("called")
            return '{"gaps": [], "reasoning": "test"}'

        override.complete = spy_complete  # type: ignore

        analyzer = GapAnalyzer(provider=original)
        analyzer._cluster_service = MagicMock()
        analyzer._cluster_service.cluster_papers = AsyncMock(
            return_value=MagicMock(clusters=[], paper_count=0)
        )

        try:
            asyncio.run(analyzer.analyze([], provider=override))
        except Exception:
            pass

        assert len(call_log) > 0, "Override provider was not used"


class TestFeasibilityScorerNoMutation:
    def test_provider_not_mutated(self):
        """FeasibilityScorer._provider must be unchanged after score_feasibility() with provider kwarg."""
        original = FakeProvider("original")
        override = OverrideProvider("override")
        scorer = FeasibilityScorer(provider=original)

        idea = MagicMock()
        try:
            asyncio.run(scorer.score_feasibility(idea, provider=override))
        except Exception:
            pass

        assert scorer._provider is original, (
            "FeasibilityScorer._provider was mutated"
        )


class TestProposalSynthesizerNoMutation:
    def test_provider_not_mutated(self):
        """ProposalSynthesizer._provider must be unchanged after synthesize() with provider kwarg."""
        original = FakeProvider("original")
        override = OverrideProvider("override")
        synthesizer = ProposalSynthesizer(provider=original)

        idea = MagicMock()
        try:
            asyncio.run(synthesizer.synthesize(idea, provider=override))
        except Exception:
            pass

        assert synthesizer._provider is original, (
            "ProposalSynthesizer._provider was mutated"
        )


class TestAgentOrchestratorNoMutation:
    def test_provider_not_mutated(self):
        """AgentOrchestrator._provider must be unchanged after run() with provider kwarg."""
        original = FakeProvider("original")
        override = OverrideProvider("override")
        orchestrator = AgentOrchestrator(provider=original)

        try:
            asyncio.run(
                orchestrator.run(
                    gaps=[],
                    context_papers=[],
                    rounds=1,
                    ideas_per_round=1,
                    provider=override,
                )
            )
        except Exception:
            pass

        assert orchestrator._provider is original, (
            "AgentOrchestrator._provider was mutated"
        )

    def test_sub_agents_not_mutated(self):
        """When provider override is given, original sub-agents keep their providers."""
        original = FakeProvider("original")
        override = OverrideProvider("override")
        orchestrator = AgentOrchestrator(provider=original)

        # Capture references before the call
        ideator_provider_before = orchestrator._ideator._provider
        critic_provider_before = orchestrator._critic._provider

        try:
            asyncio.run(
                orchestrator.run(
                    gaps=[],
                    context_papers=[],
                    rounds=1,
                    ideas_per_round=1,
                    provider=override,
                )
            )
        except Exception:
            pass

        # Sub-agents must keep their original providers
        assert orchestrator._ideator._provider is ideator_provider_before
        assert orchestrator._critic._provider is critic_provider_before


class TestNoOverrideProviderRemains:
    """Verify _override_provider is fully removed from the codebase."""

    def test_no_import_or_reference(self):
        """_override_provider must not exist anywhere in pipeline stages."""
        import backend.pipeline.stages as stages_mod

        assert not hasattr(stages_mod, "_override_provider"), (
            "_override_provider must be removed — use method-level provider injection"
        )
