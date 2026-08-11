"""Phase 3 B-05 focused tests: adversarial_review per-proposal timeout.

Verifies that the adversarial_review stage's per-proposal timeout prevents
a single slow proposal from blocking the entire stage, and that a timeout
is caught and marked as skipped (fail-open) rather than raising.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.pipeline.result import PipelineResult
from backend.pipeline.stages import AdversarialReviewStage, StageContext


def _make_proposal(title="Test Proposal"):
    """Minimal proposal stand-in with the attributes AdversarialReviewStage reads."""
    return SimpleNamespace(
        title=title,
        metadata={},
        to_markdown=lambda self=None: f"# {title}\n\nBody text.",
    )


def _make_ctx(proposals=None):
    ctx = MagicMock(spec=StageContext)
    ctx.result = PipelineResult()
    ctx.result.proposals = proposals or {0: _make_proposal()}
    ctx.all_papers = []
    return ctx


@pytest.mark.anyio
async def test_adversarial_review_per_proposal_timeout_is_caught():
    """B-05: a per-proposal review that exceeds PER_PROPOSAL_TIMEOUT is
    caught and marked skipped, not raised — the stage is fail-open."""
    stage = AdversarialReviewStage(
        reviewer=MagicMock(),
        synthesizer=MagicMock(),
        generation_provider=MagicMock(),
        thinking_provider=MagicMock(),
    )

    # Make _review_proposal hang forever by patching it to sleep
    async def _hang(*args, **kwargs):
        await asyncio.sleep(999)

    stage._review_proposal = _hang
    # Set a very short timeout for the test
    stage.PER_PROPOSAL_TIMEOUT = 0.1

    ctx = _make_ctx()
    # The stage should complete (return True) even though the proposal review
    # times out — it's fail-open per-proposal.
    result = await asyncio.wait_for(stage.execute(ctx), timeout=5)
    assert result is True


@pytest.mark.anyio
async def test_adversarial_review_skips_when_no_proposals():
    """The stage returns True immediately when there are no proposals."""
    stage = AdversarialReviewStage(
        reviewer=MagicMock(),
        synthesizer=MagicMock(),
        generation_provider=MagicMock(),
        thinking_provider=MagicMock(),
    )
    ctx = _make_ctx(proposals={})
    result = await stage.execute(ctx)
    assert result is True


@pytest.mark.anyio
async def test_adversarial_review_per_proposal_timeout_marks_skipped():
    """B-05: when a proposal review times out, the metadata records 'skipped'."""
    stage = AdversarialReviewStage(
        reviewer=MagicMock(),
        synthesizer=MagicMock(),
        generation_provider=MagicMock(),
        thinking_provider=MagicMock(),
    )

    async def _hang(*args, **kwargs):
        await asyncio.sleep(999)

    stage._review_proposal = _hang
    stage.PER_PROPOSAL_TIMEOUT = 0.1

    proposal = _make_proposal()
    ctx = _make_ctx(proposals={0: proposal})

    await asyncio.wait_for(stage.execute(ctx), timeout=5)

    # The proposal's metadata should contain a skipped adversarial_review
    meta = proposal.metadata
    ar = meta.get("adversarial_review", {})
    assert ar.get("status") == "skipped" or "skipped" in str(ar.get("reason", ""))


def test_per_proposal_timeout_is_bounded():
    """The PER_PROPOSAL_TIMEOUT constant is set and reasonable."""
    assert hasattr(AdversarialReviewStage, "PER_PROPOSAL_TIMEOUT")
    assert AdversarialReviewStage.PER_PROPOSAL_TIMEOUT > 0
    # Must be short enough that 2 proposals fit inside the default 1800s stage timeout
    assert AdversarialReviewStage.PER_PROPOSAL_TIMEOUT * 2 <= 1800
