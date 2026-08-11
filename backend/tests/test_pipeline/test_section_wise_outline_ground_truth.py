"""Regression tests for section-wise outline ground-truth precedence.

Reproduces the live VQLS -> logistic-regression/Iris control-point failure:
the proposal is adversarial, while experiment_context is authoritative.
"""

from unittest.mock import AsyncMock

import pytest

from backend.pipeline.synthesis.section_wise_synthesizer import (
    SectionDraft,
    SectionWiseSynthesizer,
)

PROPOSAL = """## Proposal: Variational Quantum Linear Solver for Hydrodynamic Lubrication

We propose a VQLS method for the Reynolds equation in mechanical bearings.
The Iris dataset is mentioned only as a downstream classification task.
"""

EXPERIMENT_CONTEXT = """## EXPERIMENT SPECIFICATION (the actual experiment this paper reports)
Research question: How well does logistic regression classify Iris?
Dataset: Iris
Analysis method: logistic regression
Task type: classification

## OBSERVED RESULTS (empirically measured — cite with [RESULT-N])
[RESULT-1] balanced_accuracy = 0.973
"""

RESULT_MARKERS = ["[RESULT-1] balanced_accuracy = 0.973"]


class CapturingProvider:
    def __init__(self) -> None:
        self.calls = []

    async def complete(self, messages, temperature=0.7, max_tokens=4096):
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return (
            "Abstract — Logistic Regression on Iris. "
            "Proposed Method — L2 logistic regression. "
            "Evaluation Plan — Iris classification."
        )


@pytest.mark.asyncio
async def test_outline_prompt_puts_ground_truth_before_conflicting_proposal():
    provider = CapturingProvider()
    synth = SectionWiseSynthesizer(provider)

    outline = await synth._generate_outline(
        PROPOSAL,
        "machine learning",
        experiment_context=EXPERIMENT_CONTEXT,
        result_markers=RESULT_MARKERS,
    )

    assert "Logistic Regression on Iris" in outline
    assert len(provider.calls) == 1

    messages = provider.calls[0]["messages"]
    system_prompt = messages[0]["content"]
    user_prompt = messages[1]["content"]

    assert "non-negotiable" in system_prompt.lower()
    assert "## Experiment Ground Truth" in user_prompt
    assert "GROUND-TRUTH PRECEDENCE" in user_prompt
    assert user_prompt.index("## Experiment Ground Truth") < user_prompt.index("Proposal summary:")
    assert "Analysis method: logistic regression" in user_prompt
    assert "Variational Quantum Linear Solver" in user_prompt


@pytest.mark.asyncio
async def test_synthesize_forwards_ground_truth_to_outline_and_sections(monkeypatch):
    provider = CapturingProvider()
    synth = SectionWiseSynthesizer(provider)

    outline_mock = AsyncMock(return_value="Grounded logistic-regression/Iris outline")
    section_mock = AsyncMock(
        return_value=SectionDraft(
            section_id="abstract",
            title="Abstract",
            content="Logistic regression on Iris [RESULT-1].",
            word_count=8,
            citations_used=[],
            model_used="test",
        )
    )
    monkeypatch.setattr(synth, "_generate_outline", outline_mock)
    monkeypatch.setattr(synth, "_generate_section", section_mock)

    await synth.synthesize(
        proposal_text=PROPOSAL,
        source_papers=[],
        domain="machine learning",
        experiment_context=EXPERIMENT_CONTEXT,
        result_markers=RESULT_MARKERS,
    )

    outline_mock.assert_awaited_once_with(
        PROPOSAL,
        "machine learning",
        experiment_context=EXPERIMENT_CONTEXT,
        result_markers=RESULT_MARKERS,
    )

    assert section_mock.await_count > 0
    for call in section_mock.await_args_list:
        assert call.kwargs["experiment_context"] == EXPERIMENT_CONTEXT
        assert call.kwargs["result_markers"] == RESULT_MARKERS
