"""Regression tests for ground-truth re-injection in paper synthesis.

These tests lock in the phase-8 fix: experiment_context is no longer folded
into source_papers (where it was treated as supplementary literature and the
proposal narrative took primacy, producing scope-fabricated papers like the
"Quantum Solver" Iris fixture). It is now rendered as a dedicated
``## Experiment Ground Truth`` block at the top of the user prompt and
asserted as a non-negotiable invariant by the system prompt.

What this test proves:
  1. The ground-truth block appears at the top of the user prompt.
  2. The ground-truth content is NOT duplicated in the supporting literature.
  3. RESULT markers from experiment_context reach the prompt verbatim.
  4. The system prompt contains the GROUND TRUTH INVARIANTS section.
  5. Non-empirical synthesis (no experiment_context) does not emit the block.
  6. The SynthesisSession isolation wrapper passes inputs through correctly.

What this test does NOT prove (and cannot, against a stub provider):
  - That the live glm-5.2 model actually OBEYS the invariant. That requires a
    live run. The deterministic evidence layer (DeterministicFinalizer) is the
    real guarantee; this prompt change raises the floor, not the ceiling.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from backend.pipeline.synthesis.paper_synthesizer import (
    PaperSynthesizer,
    SynthesisSession,
)

SYSTEM_PROMPT_PATH = (
    Path(__file__).parent.parent.parent
    / "pipeline"
    / "synthesis"
    / "prompts"
    / "paper_synthesis_system.md"
)


class _CapturingProvider:
    """Stub provider that records the messages it was called with."""

    def __init__(self, response: str = "## Abstract\nStub response. [RESULT-1]"):
        self.default_model = "glm-5.2"
        self._response = response
        self.captured_messages: list[dict] | None = None

    async def complete(self, messages, **kwargs):
        self.captured_messages = messages
        return self._response


# ─── Prompt-structure tests (no provider call needed) ─────────────────────


class TestGroundTruthBlockRendering:
    def test_ground_truth_block_at_top_when_experiment_context_present(self):
        prompt = PaperSynthesizer._build_user_prompt(
            proposal_text="Proposal text.",
            source_papers=["[SOURCE-1] Smith 2020."],
            domain="ML",
            experiment_context="Method: logistic regression\n[RESULT-1] acc=0.95",
        )
        assert prompt.startswith("## Experiment Ground Truth")
        # Ground truth must appear BEFORE the supporting literature section
        gt_pos = prompt.find("## Experiment Ground Truth")
        lit_pos = prompt.find("## Supporting Literature")
        assert gt_pos < lit_pos

    def test_ground_truth_content_not_duplicated_into_sources(self):
        """The phase-8 bug was experiment_context appearing once as a source.
        With the fix it appears exactly once, as a ground-truth block."""
        unique_marker = "UNIQUE_GT_MARKER_42"
        prompt = PaperSynthesizer._build_user_prompt(
            proposal_text="Proposal.",
            source_papers=["[SOURCE-1] Smith 2020."],
            domain="ML",
            experiment_context=f"{unique_marker} [RESULT-1] x=0.9",
        )
        assert prompt.count(unique_marker) == 1

    def test_result_markers_reach_prompt_verbatim(self):
        prompt = PaperSynthesizer._build_user_prompt(
            proposal_text="Proposal.",
            source_papers=["[SOURCE-1]"],
            domain="ML",
            experiment_context="[RESULT-1] a=0.9\n[RESULT-2] b=0.5\n[RESULT-3] c=0.7",
        )
        assert "[RESULT-1]" in prompt
        assert "[RESULT-2]" in prompt
        assert "[RESULT-3]" in prompt

    def test_no_ground_truth_block_when_experiment_context_absent(self):
        """Non-empirical synthesis must not emit the block."""
        prompt = PaperSynthesizer._build_user_prompt(
            proposal_text="Proposal.",
            source_papers=["[SOURCE-1]"],
            domain="NLP",
            experiment_context=None,
        )
        assert "## Experiment Ground Truth" not in prompt

    def test_no_ground_truth_block_when_experiment_context_empty(self):
        prompt = PaperSynthesizer._build_user_prompt(
            proposal_text="Proposal.",
            source_papers=["[SOURCE-1]"],
            domain="NLP",
            experiment_context="   ",
        )
        assert "## Experiment Ground Truth" not in prompt

    def test_non_empirical_closer_absent_without_ground_truth(self):
        prompt = PaperSynthesizer._build_user_prompt(
            proposal_text="Proposal.",
            source_papers=["[SOURCE-1]"],
            domain="NLP",
            experiment_context=None,
        )
        # The closer references the ground-truth block; it must not appear
        # in the non-empirical variant.
        assert "The Experiment Ground Truth block above is authoritative" not in prompt


# ─── System prompt content tests ──────────────────────────────────────────


class TestSystemPromptInvariants:
    def test_system_prompt_contains_ground_truth_invariants_section(self):
        """The system prompt must assert ground-truth invariants. This is the
        contract that makes the user-prompt block non-negotiable."""
        content = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        assert "## GROUND TRUTH INVARIANTS" in content
        # The four invariants from the plan
        assert "Subject identity" in content
        assert "Marker fidelity" in content
        assert "Ground truth wins over proposal" in content
        assert "No fabrication of results" in content

    def test_ground_truth_section_above_critical_rules(self):
        """The invariants must be the first thing the model reads, above the
        existing critical-rules section."""
        content = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        gt_pos = content.find("## GROUND TRUTH INVARIANTS")
        rules_pos = content.find("## CRITICAL RULES")
        assert gt_pos != -1
        assert rules_pos != -1
        assert gt_pos < rules_pos


# ─── End-to-end wiring tests (stub provider) ──────────────────────────────


class TestSynthesisWiring:
    def test_synthesize_passes_experiment_context_to_prompt(self):
        """synthesize() with experiment_context must produce a prompt that
        contains the ground-truth block."""
        provider = _CapturingProvider()
        synth = PaperSynthesizer(provider)

        asyncio.run(
            synth.synthesize(
                proposal_text="Proposal.",
                source_papers=["[SOURCE-1]"],
                domain="ML",
                experiment_context="Method: logistic regression\n[RESULT-1] acc=0.9",
            )
        )

        user_msg = next(
            m["content"] for m in provider.captured_messages if m["role"] == "user"
        )
        assert "## Experiment Ground Truth" in user_msg
        assert "[RESULT-1]" in user_msg

    def test_synthesize_session_routes_through_isolation_contract(self):
        """The SynthesisSession entry point must deliver the same prompt
        structure as the legacy signature."""
        provider = _CapturingProvider()
        synth = PaperSynthesizer(provider)

        session = SynthesisSession(
            proposal_text="Proposal.",
            source_papers=("[SOURCE-1]",),
            domain="ML",
            experiment_context="Method: random forest\n[RESULT-1] acc=0.8",
        )
        asyncio.run(synth.synthesize_session(session))

        user_msg = next(
            m["content"] for m in provider.captured_messages if m["role"] == "user"
        )
        assert "## Experiment Ground Truth" in user_msg
        assert "random forest" in user_msg


# ─── SynthesisSession dataclass tests ─────────────────────────────────────


class TestSynthesisSessionContract:
    def test_session_permitted_field_set_is_exactly_the_approved_contract(self):
        """The approved isolation contract enumerates exactly five fields:
        proposal_text, source_papers, experiment_context, result_markers,
        domain. venue and proposal_id are deliberately NOT here — they are
        result-metadata, not prompt inputs. This test pins the contract so
        future additions are deliberate, not accidental channel-widening.
        """
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(SynthesisSession)}
        assert field_names == {
            "proposal_text", "source_papers", "experiment_context",
            "result_markers", "domain",
        }, (
            "SynthesisSession field set drifted from the approved contract. "
            f"Got: {field_names}. If adding a field, document its prompt-level "
            "necessity and update this test deliberately."
        )

    def test_session_is_frozen(self):
        """Isolation contract: a session must not be mutable after construction."""
        session = SynthesisSession(proposal_text="x")
        with pytest.raises(Exception):
            session.proposal_text = "mutated"  # type: ignore[misc]

    def test_source_papers_coerced_to_tuple(self):
        """Lists are accepted at construction but frozen to tuples."""
        session = SynthesisSession(
            proposal_text="x", source_papers=["[SOURCE-1]", "[SOURCE-2]"]  # type: ignore[arg-type]
        )
        assert isinstance(session.source_papers, tuple)
        assert len(session.source_papers) == 2

    def test_result_markers_coerced_to_tuple(self):
        """List-form markers are accepted but frozen to tuples."""
        session = SynthesisSession(
            proposal_text="x",
            result_markers=["[RESULT-1] a=0.9", "[RESULT-2] b=0.5"],  # type: ignore[arg-type]
        )
        assert isinstance(session.result_markers, tuple)
        assert len(session.result_markers) == 2

    def test_session_default_omits_ground_truth(self):
        """A session with no experiment_context is a non-empirical synthesis."""
        session = SynthesisSession(proposal_text="x")
        assert session.experiment_context is None
        assert session.result_markers == ()


# ─── result_markers rendering tests ───────────────────────────────────────


class TestResultMarkersRendering:
    def test_markers_rendered_as_authorized_list_when_present(self):
        """result_markers must render as a verbatim authorized-marker list
        inside the ground-truth block, not as prose."""
        prompt = PaperSynthesizer._build_user_prompt(
            proposal_text="Proposal.",
            source_papers=["[SOURCE-1]"],
            domain="ML",
            experiment_context="Method: logistic regression",
            result_markers=["[RESULT-1] acc=0.95", "[RESULT-2] baseline=0.50"],
        )
        assert "### Authorized result markers" in prompt
        assert "[RESULT-1] acc=0.95" in prompt
        assert "[RESULT-2] baseline=0.50" in prompt

    def test_markers_render_without_experiment_context(self):
        """Markers without prose context still surface as their own ground-truth
        sub-block — they are authoritative for marker fidelity regardless."""
        prompt = PaperSynthesizer._build_user_prompt(
            proposal_text="Proposal.",
            source_papers=["[SOURCE-1]"],
            domain="ML",
            experiment_context=None,
            result_markers=["[RESULT-1] acc=0.9"],
        )
        assert "## Experiment Ground Truth" in prompt
        assert "[RESULT-1] acc=0.9" in prompt

    def test_no_marker_list_when_absent(self):
        """Non-empirical synthesis (no markers, no context) must not emit
        the authorized-marker list."""
        prompt = PaperSynthesizer._build_user_prompt(
            proposal_text="Proposal.",
            source_papers=["[SOURCE-1]"],
            domain="NLP",
        )
        assert "### Authorized result markers" not in prompt

    def test_synthesize_session_passes_markers_into_prompt(self):
        provider = _CapturingProvider()
        synth = PaperSynthesizer(provider)
        session = SynthesisSession(
            proposal_text="Proposal.",
            source_papers=("[SOURCE-1]",),
            domain="ML",
            result_markers=("[RESULT-1] acc=0.95",),
        )
        asyncio.run(synth.synthesize_session(session))
        user_msg = next(
            m["content"] for m in provider.captured_messages if m["role"] == "user"
        )
        assert "[RESULT-1] acc=0.95" in user_msg
        assert "### Authorized result markers" in user_msg
