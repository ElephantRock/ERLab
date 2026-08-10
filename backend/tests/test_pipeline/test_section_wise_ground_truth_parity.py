"""Parity tests: section-wise fallback must honor the same ground-truth
contract as the monolithic synthesizer.

Context: the monolithic path was given ground-truth re-injection (phase-8 fix)
via ``experiment_context`` and ``result_markers`` rendered as a dedicated
``## Experiment Ground Truth`` block at the top of the prompt. The section-wise
fallback path — which fires when monolithic times out or returns short output,
i.e. the expected hot path under glm-5.2 — did not receive these inputs. This
is the same scope-fabrication failure mode (phase 8) re-opened on fallback.

This test file locks in the parity fix:
  1. ``_render_ground_truth_block`` produces the correct block in all cases.
  2. ``_generate_section`` prepends the block to the structured-attempt prompt.
  3. ``_generate_section`` prepends the block to the prose-fallback prompt.
  4. ``synthesize`` forwards both args through to ``_generate_section``.
  5. Non-empirical synthesis (no ground truth) omits the block — backward compat.

What this test does NOT prove:
  - That the live glm-5.2 model OBEYS the invariant. The system prompt's
    GROUND TRUTH INVARIANTS section is a prompt-level floor; the deterministic
    evidence layer (DeterministicFinalizer) remains the ceiling.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.pipeline.synthesis.section_wise_synthesizer import (
    SectionWiseSynthesizer,
)

# ─── _render_ground_truth_block unit tests ────────────────────────────────


class TestRenderGroundTruthBlock:
    def test_empty_when_no_ground_truth(self):
        """Non-empirical synthesis must produce no block (backward compat)."""
        block = SectionWiseSynthesizer._render_ground_truth_block(None, None)
        assert block == ""

    def test_empty_when_both_blank(self):
        block = SectionWiseSynthesizer._render_ground_truth_block("   ", [])
        assert block == ""

    def test_renders_header_when_context_present(self):
        block = SectionWiseSynthesizer._render_ground_truth_block(
            experiment_context="Method: logistic regression",
            result_markers=None,
        )
        assert "## Experiment Ground Truth" in block
        assert "logistic regression" in block

    def test_renders_marker_list_when_markers_present(self):
        block = SectionWiseSynthesizer._render_ground_truth_block(
            experiment_context=None,
            result_markers=["[RESULT-1] acc=0.9", "[RESULT-2] b=0.5"],
        )
        assert "## Experiment Ground Truth" in block
        assert "### Authorized result markers" in block
        assert "[RESULT-1] acc=0.9" in block
        assert "[RESULT-2] b=0.5" in block

    def test_renders_both_context_and_markers(self):
        block = SectionWiseSynthesizer._render_ground_truth_block(
            experiment_context="Method: random forest",
            result_markers=["[RESULT-1] acc=0.8"],
        )
        assert "random forest" in block
        assert "[RESULT-1] acc=0.8" in block


# ─── _generate_section prompt parity (stub provider captures the prompt) ──


def _make_capturing_provider(response_text: str = "Generated section text."):
    """Provider mock that records the user-message content it was called with."""
    provider = AsyncMock()
    provider.default_model = "glm-5.2"
    provider.complete = AsyncMock(return_value=response_text)
    # _generate_section tries gateway.structured_complete first; ensure it
    # falls through to provider.complete by giving the mock no _gateway.
    provider._gateway = None
    return provider


class TestGenerateSectionPromptParity:
    @pytest.mark.asyncio
    async def test_structured_attempt_prompt_contains_ground_truth(self):
        """The first prompt attempt (structured) must include the ground-truth
        block when experiment_context is present."""
        provider = _make_capturing_provider()
        synth = SectionWiseSynthesizer(provider, context_window=8192)

        await synth._generate_section(
            section_id="abstract",
            section_title="Abstract",
            target_words=300,
            outline="Outline.",
            proposal_summary="Summary.",
            relevant_sources="[SOURCE-1] Smith.",
            domain="ML",
            experiment_context="Method: logistic regression\nDataset: Iris",
            result_markers=["[RESULT-1] acc=0.95"],
        )

        # provider.complete is the prose fallback path; the structured path
        # calls _structured_complete_with_schema which, with no gateway, also
        # routes to provider.complete. Either way the captured user prompt
        # must contain the ground-truth block. We check the user message
        # specifically (not the system prompt, which references the block
        # name in its GROUND TRUTH INVARIANTS section regardless of inputs).
        assert provider.complete.called, "provider.complete was never invoked"
        user_msg_contents: list[str] = []
        for call in provider.complete.call_args_list:
            messages = call.kwargs.get("messages") or (call.args[0] if call.args else [])
            for m in messages:
                if isinstance(m, dict) and m.get("role") == "user":
                    user_msg_contents.append(m["content"])
        joined = "\n".join(user_msg_contents)
        assert "## Experiment Ground Truth" in joined
        assert "logistic regression" in joined
        assert "[RESULT-1] acc=0.95" in joined

    @pytest.mark.asyncio
    async def test_non_empirical_section_omits_ground_truth_block(self):
        """When no ground truth is provided, the user message must not contain
        a ground-truth block. (The system prompt legitimately references the
        block by name in its GROUND TRUTH INVARIANTS section — we check the
        user message specifically, not the whole call.)"""
        provider = _make_capturing_provider()
        synth = SectionWiseSynthesizer(provider, context_window=8192)

        await synth._generate_section(
            section_id="abstract",
            section_title="Abstract",
            target_words=300,
            outline="Outline.",
            proposal_summary="Summary.",
            relevant_sources="[SOURCE-1]",
            domain="NLP",
            experiment_context=None,
            result_markers=None,
        )

        for call in provider.complete.call_args_list:
            messages = call.kwargs.get("messages") or (call.args[0] if call.args else [])
            user_msgs = [
                m["content"] for m in messages if isinstance(m, dict) and m.get("role") == "user"
            ]
            for um in user_msgs:
                # The user message must not START with the ground-truth block
                # (the block is always prepended when present).
                assert not um.startswith("## Experiment Ground Truth"), (
                    "Ground-truth block leaked into user message in non-empirical mode"
                )


# ─── synthesize() forwarding ──────────────────────────────────────────────


class TestSynthesizeForwardsGroundTruth:
    @pytest.mark.asyncio
    async def test_synthesize_forwards_ground_truth_to_every_section(self):
        """synthesize() must forward experiment_context and result_markers
        into each _generate_section call. Verified by monkeypatching
        _generate_section to capture what it received."""
        provider = _make_capturing_provider("Section prose.")
        synth = SectionWiseSynthesizer(provider, context_window=8192)

        captured: list[dict] = []

        async def _capture_generate(**kwargs):
            captured.append(kwargs)
            # Return a minimal valid SectionDraft-like result
            from backend.pipeline.synthesis.section_wise_synthesizer import SectionDraft
            return SectionDraft(
                section_id=kwargs["section_id"],
                title=kwargs["section_title"],
                content="Generated.",
                word_count=1,
                citations_used=[],
                model_used="glm-5.2",
            )

        synth._generate_section = _capture_generate  # type: ignore[assignment]
        # Also stub the outline call to avoid an LLM round-trip
        synth._generate_outline = AsyncMock(return_value="Outline.")  # type: ignore[assignment]

        await synth.synthesize(
            proposal_text="Proposal.",
            source_papers=["[SOURCE-1]"],
            domain="ML",
            experiment_context="Method: random forest",
            result_markers=["[RESULT-1] acc=0.8"],
        )

        assert len(captured) > 0, "_generate_section was never called"
        for kwargs in captured:
            assert kwargs.get("experiment_context") == "Method: random forest"
            assert kwargs.get("result_markers") == ["[RESULT-1] acc=0.8"], (
                f"result_markers not forwarded to section {kwargs.get('section_id')}"
            )

    @pytest.mark.asyncio
    async def test_synthesize_backward_compat_no_ground_truth(self):
        """synthesize() with no ground-truth args must still work (legacy callers)."""
        provider = _make_capturing_provider("Section prose.")
        synth = SectionWiseSynthesizer(provider, context_window=8192)

        captured: list[dict] = []

        async def _capture_generate(**kwargs):
            captured.append(kwargs)
            from backend.pipeline.synthesis.section_wise_synthesizer import SectionDraft
            return SectionDraft(
                section_id=kwargs["section_id"],
                title=kwargs["section_title"],
                content="Generated.",
                word_count=1,
                citations_used=[],
                model_used="glm-5.2",
            )

        synth._generate_section = _capture_generate  # type: ignore[assignment]
        synth._generate_outline = AsyncMock(return_value="Outline.")  # type: ignore[assignment]

        # Legacy call: only the original 4 positional args + proposal_id
        result = await synth.synthesize(
            "Proposal.", ["[SOURCE-1]"], "NLP", "Generic", 0,
        )

        assert result is not None
        assert len(captured) > 0
        for kwargs in captured:
            assert kwargs.get("experiment_context") is None
            assert kwargs.get("result_markers") is None
