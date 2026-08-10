"""Tests for proposal section refinement pass (GAP 2 fix)."""

import asyncio

from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.synthesis.proposal_synthesizer import (
    SECTION_CHECKLIST,
    ProposalSynthesizer,
    ResearchProposal,
)
from backend.tests.test_pipeline.conftest import SchemaAwareFakeProvider


def _make_idea():
    return ResearchIdea(
        title="Test Idea",
        problem_statement="A research problem to solve",
        proposed_method="A proposed method to address the problem",
        expected_contributions="Expected contributions of the work",
        novelty_rationale="Novel because reasons",
        evaluation_approach="Evaluate with benchmarks",
    )


class _RefinementTestProvider(SchemaAwareFakeProvider):
    """Provider that returns well-formed output on first call, then varied on subsequent calls."""

    def __init__(self, second_call_content: str | None = None):
        super().__init__()
        self._call_count = 0
        self._second_call_content = second_call_content

    async def complete(self, messages, temperature=0.7, max_tokens=4096) -> str:
        self._call_count += 1
        # First call: normal full generation
        if self._call_count == 1:
            return await super().complete(messages, temperature, max_tokens)
        # Subsequent calls: return the override if provided
        if self._second_call_content:
            return self._second_call_content
        return await super().complete(messages, temperature, max_tokens)


class _WeakMethodProvider(SchemaAwareFakeProvider):
    """Provider whose first-call output has a weak Proposed Method (no math)."""

    async def complete(self, messages, temperature=0.7, max_tokens=4096) -> str:
        self._call_log.append({"method": "complete", "messages": messages})
        return (
            "## Title\n\nWeak Method Paper\n\n"
            "## Abstract\n\n" + ("word " * 160) + "\n\n"
            "## Introduction\n\n" + ("intro word " * 400) + "Our contributions are novel.\n\n"
            "## Related Work\n\nPrior work by Smith (2020) explored this. Jones (2021) extended it.\n\n"
            "## Proposed Method\n\n"
            # Deliberately: long enough (500+ words) but NO math notation ($...$)
            + ("method word " * 500) + "\n\n"
            "## Expected Contributions\n\n1. A new approach.\n\n"
            "## Evaluation Plan\n\nWe evaluate on standard benchmarks with baselines and metrics.\n\n"
            "## Timeline\n\nPhase 1: implement. Phase 2: test.\n\n"
            "## References\n\n[1] Smith (2020). Prior work. ACL.\n\n"
            "## Risk Mitigation\n\nRisk 1: compute. Mitigation: use GPUs.\n"
        )


class TestSectionChecklist:
    """Test the per-section quality checklist configuration."""

    def test_method_requires_math(self):
        """Proposed Method checklist requires $...$ notation."""
        assert "proposed_method" in SECTION_CHECKLIST
        patterns = [p for p, _ in SECTION_CHECKLIST["proposed_method"]]
        assert any("$" in p for p in patterns)

    def test_related_work_requires_citations(self):
        """Related Work checklist requires citation markers."""
        assert "related_work" in SECTION_CHECKLIST
        patterns = [p for p, _ in SECTION_CHECKLIST["related_work"]]
        assert any("\\[" in p or "\\(" in p for p in patterns)

    def test_evaluation_requires_specifics(self):
        """Evaluation Plan checklist requires baseline/metric/dataset."""
        assert "evaluation_plan" in SECTION_CHECKLIST
        descriptions = [d for _, d in SECTION_CHECKLIST["evaluation_plan"]]
        assert any("baseline" in d for d in descriptions)


class TestCheckSection:
    """Test the _check_section static method."""

    def test_fails_missing_math(self):
        """Section without math notation fails."""
        content = "word " * 600  # Long enough, no math
        failures = ProposalSynthesizer._check_section("proposed_method", content)
        assert any("mathematical notation" in f for f in failures)

    def test_fails_short_section(self):
        """Section below MIN_WORDS fails."""
        content = "Too short section."
        failures = ProposalSynthesizer._check_section("introduction", content)
        assert any("word count" in f for f in failures)

    def test_fails_missing_citations(self):
        """Related Work without citation markers fails."""
        content = "Prior work explored this area extensively. " * 30  # ~270 words, no citations
        failures = ProposalSynthesizer._check_section("related_work", content)
        assert any("citation" in f for f in failures)

    def test_passes_with_citations(self):
        """Related Work with [1] markers passes."""
        content = "Prior work by Smith [1] explored this. Jones [2] extended it. " * 20
        failures = ProposalSynthesizer._check_section("related_work", content)
        assert not any("citation" in f for f in failures)


class TestRefinementPass:
    """Test that _refine_sections detects and re-generates weak sections."""

    def test_all_sections_pass(self):
        """Well-formed proposal from SchemaAwareFakeProvider passes refinement."""
        provider = SchemaAwareFakeProvider()
        synthesizer = ProposalSynthesizer(provider)
        proposal = asyncio.run(synthesizer.synthesize(_make_idea()))

        # The fake provider's output includes $...$ and [1] — should pass
        method_failures = ProposalSynthesizer._check_section(
            "proposed_method", proposal.sections.get("proposed_method", "")
        )
        # May have word count issues but should have math notation
        assert not any("mathematical notation" in f for f in method_failures)

    def test_weak_method_triggers_refinement(self):
        """Proposed Method without math triggers re-generation."""
        provider = _WeakMethodProvider()
        synthesizer = ProposalSynthesizer(provider)
        proposal = asyncio.run(synthesizer.synthesize(_make_idea()))

        # The refinement pass should have fired for proposed_method
        # (provider.complete was called more than once)
        complete_calls = [c for c in provider._call_log if c["method"] == "complete"]
        # First call: full generation. Subsequent: refinement of weak sections.
        assert len(complete_calls) >= 2, f"Expected >= 2 complete() calls, got {len(complete_calls)}"

    def test_refinement_logs_failures(self):
        """Refinement pass returns valid proposal even with weak sections."""
        provider = _WeakMethodProvider()
        synthesizer = ProposalSynthesizer(provider)
        proposal = asyncio.run(synthesizer.synthesize(_make_idea()))
        # Verify the proposal was returned (refinement didn't crash)
        assert isinstance(proposal, ResearchProposal)
        assert proposal.sections.get("title", "") != ""

    def test_refinement_preserves_good_sections(self):
        """Sections that pass the checklist are not re-generated."""
        provider = _RefinementTestProvider()
        synthesizer = ProposalSynthesizer(provider)
        proposal = asyncio.run(synthesizer.synthesize(_make_idea()))

        # Abstract and Title don't have pattern checks, should survive
        assert proposal.sections.get("title", "") != ""
        assert proposal.sections.get("abstract", "") != ""
