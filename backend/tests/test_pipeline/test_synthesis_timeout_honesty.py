"""Commissioning remediation: synthesis timeout must not become content.

Reproduces the 2026-09-12 commissioning-run defect: a 300s synthesis
timeout was persisted as ``abstract="Synthesis timed out after 300s"`` /
``introduction="Timed out"`` and shipped in exports. The repaired stage
retries once and, on persistent timeout, stores EMPTY sections with an
explicit ``synthesis_status`` marker instead of error strings.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from backend.pipeline.stages import ProposalSynthesisStage, StageContext
from backend.pipeline.result import PipelineResult
from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal


def _idea() -> ResearchIdea:
    return ResearchIdea(
        title="Durable Infinite Context",
        problem_statement="p",
        proposed_method="m",
        expected_contributions="c",
        novelty_rationale="",
        evaluation_approach="",
        domain="AI/NLP",
        round_generated=1,
        score=5.0,
        supporting_papers=[],
        source_gap_ids=[],
    )


def _ctx() -> StageContext:
    result = PipelineResult()
    result.ideas = [_idea()]
    ctx = StageContext(result=result)
    ctx.all_papers = []
    return ctx


class _HangingSynthesizer:
    """Simulates a provider that never finishes inside the timeout."""

    def __init__(self):
        self.calls = 0

    async def synthesize(self, **kwargs):
        self.calls += 1
        await asyncio.sleep(30)


class _OkSynthesizer:
    def __init__(self):
        self.calls = 0

    async def synthesize(self, **kwargs):
        self.calls += 1
        return ResearchProposal(
            title="T",
            abstract="A proper abstract.",
            introduction="A proper introduction.",
            proposed_method="M",
        )


def _stage(synthesizer) -> ProposalSynthesisStage:
    return ProposalSynthesisStage(
        synthesizer=synthesizer,
        governance_validator=None,
        governance_audit=None,
        ref_validator=None,
    )


@pytest.fixture
def tiny_timeout(monkeypatch):
    from backend.config import get_settings

    monkeypatch.setattr(get_settings(), "per_proposal_timeout", 0.05, raising=False)


@pytest.mark.anyio
async def test_timeout_persists_empty_sections_not_error_strings(tiny_timeout):
    synth = _HangingSynthesizer()
    stage = _stage(synth)
    ctx = _ctx()

    ok = await stage.execute(ctx)

    assert ok is True  # the run continues by design...
    proposal = ctx.result.proposals[0]
    assert proposal.abstract == ""  # ...but NO fabricated error-string content
    assert proposal.sections.get("introduction") == ""
    assert "timed out after" not in (proposal.abstract or "").lower()
    assert "timed out" not in (proposal.sections.get("introduction") or "").lower()
    assert proposal.sections.get("synthesis_status") == "timeout"
    assert synth.calls == 2  # one retry before honest failure


@pytest.mark.anyio
async def test_success_path_unmarked(tiny_timeout):
    synth = _OkSynthesizer()
    stage = _stage(synth)
    ctx = _ctx()

    await stage.execute(ctx)

    proposal = ctx.result.proposals[0]
    assert proposal.abstract == "A proper abstract."
    assert "synthesis_status" not in proposal.sections
    assert synth.calls == 1  # no retry on success
