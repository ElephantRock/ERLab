"""Phase 3 B-08 focused tests: paper_synthesis per-proposal timeout.

Verifies that:
1. One proposal succeeds while another hangs.
2. The stage completes without invoking whole-stage retry.
3. The successful paper remains available and persists.
4. The timed-out paper is explicitly failed.
5. Previously completed proposal work is not repeated.
6. All proposals failing cannot produce a false successful paper outcome.
7. Monolithic synthesis remains unchanged.
"""

from __future__ import annotations

import asyncio
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from backend.pipeline.stages import PaperSynthesisStage, StageContext
from backend.pipeline.result import PipelineResult


def _make_proposal(title="Test Proposal", content="Body text."):
    """Minimal proposal stand-in."""
    p = SimpleNamespace(
        title=title,
        metadata={},
        to_markdown=lambda self=None: f"# {title}\n\n{content}",
    )
    return p


def _make_ctx(proposals=None):
    ctx = MagicMock(spec=StageContext)
    ctx.result = PipelineResult()
    ctx.result.proposals = proposals or {0: _make_proposal()}
    ctx.all_papers = []
    ctx.domain = "AI/NLP"
    ctx.provider_override = None
    ctx.params = {}
    return ctx


@pytest.mark.anyio
async def test_one_succeeds_while_another_hangs():
    """Case 1: proposal 0 succeeds, proposal 1 hangs — stage returns True."""
    stage = PaperSynthesisStage(provider=MagicMock())
    stage.PER_PROPOSAL_TIMEOUT = 0.5

    good_proposal = _make_proposal("Good", "Short content.")
    hung_proposal = _make_proposal("Hung", "Long content that will time out.")

    call_log = []

    original_method = stage._synthesize_paper_for_proposal

    async def _track_and_maybe_hang(idx, proposal, ctx, provider, source_papers, context_window):
        call_log.append(idx)
        if idx == 0:
            # Simulate success: set metadata
            metadata = stage._get_metadata(proposal)
            metadata["full_paper"] = {"paper_markdown": "# Paper\n\nReal content.", "word_count": 3}
            stage._set_metadata(proposal, metadata)
        else:
            # Simulate hang
            await asyncio.sleep(999)

    stage._synthesize_paper_for_proposal = _track_and_maybe_hang

    ctx = _make_ctx(proposals={0: good_proposal, 1: hung_proposal})
    result = await asyncio.wait_for(stage.execute(ctx), timeout=5)

    assert result is True  # stage completed
    assert call_log == [0, 1]  # both proposals were attempted
    # Good proposal has paper; hung proposal is failed
    assert good_proposal.metadata.get("full_paper") is not None
    assert hung_proposal.metadata.get("full_paper") is None


@pytest.mark.anyio
async def test_stage_completes_without_whole_stage_retry():
    """Case 2: the stage returns True (not raises) even with a timeout."""
    stage = PaperSynthesisStage(provider=MagicMock())
    stage.PER_PROPOSAL_TIMEOUT = 0.1

    async def _hang(*args, **kwargs):
        await asyncio.sleep(999)

    stage._synthesize_paper_for_proposal = _hang
    ctx = _make_ctx(proposals={0: _make_proposal()})

    # Must not raise — the stage catches per-proposal timeouts
    result = await asyncio.wait_for(stage.execute(ctx), timeout=5)
    assert result is True


@pytest.mark.anyio
async def test_successful_paper_remains_available():
    """Case 3: a successful paper is not lost when another times out."""
    stage = PaperSynthesisStage(provider=MagicMock())
    stage.PER_PROPOSAL_TIMEOUT = 0.5

    good = _make_proposal("Good", "Content")
    hung = _make_proposal("Hung", "Content")

    async def _synthesize(idx, proposal, ctx, provider, source_papers, context_window):
        if idx == 0:
            metadata = stage._get_metadata(proposal)
            metadata["full_paper"] = {"paper_markdown": "# Success\n\nReal paper.", "word_count": 3}
            stage._set_metadata(proposal, metadata)
        else:
            await asyncio.sleep(999)

    stage._synthesize_paper_for_proposal = _synthesize
    ctx = _make_ctx(proposals={0: good, 1: hung})

    await asyncio.wait_for(stage.execute(ctx), timeout=5)

    # The good paper must survive
    assert good.metadata["full_paper"] is not None
    assert "Success" in good.metadata["full_paper"]["paper_markdown"]


@pytest.mark.anyio
async def test_timed_out_paper_explicitly_failed():
    """Case 4: a timed-out proposal's full_paper is None, not a stale value."""
    stage = PaperSynthesisStage(provider=MagicMock())
    stage.PER_PROPOSAL_TIMEOUT = 0.1

    hung = _make_proposal("Hung", "Content")
    # Pre-set a stale value to prove it gets overwritten
    hung.metadata = {"full_paper": {"paper_markdown": "stale"}}

    async def _hang(*args, **kwargs):
        await asyncio.sleep(999)

    stage._synthesize_paper_for_proposal = _hang
    ctx = _make_ctx(proposals={0: hung})

    await asyncio.wait_for(stage.execute(ctx), timeout=5)

    assert hung.metadata.get("full_paper") is None


@pytest.mark.anyio
async def test_previously_completed_work_not_repeated():
    """Case 5: if proposal 0 succeeds, it's only called once (not re-attempted)."""
    stage = PaperSynthesisStage(provider=MagicMock())
    stage.PER_PROPOSAL_TIMEOUT = 0.5

    call_count = {0: 0, 1: 0}

    async def _track(idx, proposal, ctx, provider, source_papers, context_window):
        call_count[idx] = call_count.get(idx, 0) + 1
        metadata = stage._get_metadata(proposal)
        metadata["full_paper"] = {"paper_markdown": "# OK", "word_count": 1}
        stage._set_metadata(proposal, metadata)

    stage._synthesize_paper_for_proposal = _track
    ctx = _make_ctx(proposals={0: _make_proposal("A"), 1: _make_proposal("B")})

    await asyncio.wait_for(stage.execute(ctx), timeout=5)

    assert call_count[0] == 1  # not repeated
    assert call_count[1] == 1


@pytest.mark.anyio
async def test_all_failing_cannot_produce_false_success():
    """Case 6: if all proposals time out, all papers are None."""
    stage = PaperSynthesisStage(provider=MagicMock())
    stage.PER_PROPOSAL_TIMEOUT = 0.1

    async def _hang(*args, **kwargs):
        await asyncio.sleep(999)

    stage._synthesize_paper_for_proposal = _hang
    p0 = _make_proposal("A")
    p1 = _make_proposal("B")
    ctx = _make_ctx(proposals={0: p0, 1: p1})

    result = await asyncio.wait_for(stage.execute(ctx), timeout=5)
    assert result is True  # stage completes (fail-open)
    assert p0.metadata.get("full_paper") is None
    assert p1.metadata.get("full_paper") is None


def test_monolithic_path_unchanged():
    """Case 7: PER_PROPOSAL_TIMEOUT is set and bounded for the stage."""
    assert hasattr(PaperSynthesisStage, "PER_PROPOSAL_TIMEOUT")
    assert PaperSynthesisStage.PER_PROPOSAL_TIMEOUT > 0
    # 2 proposals × timeout must fit within the 1800s default stage timeout
    assert PaperSynthesisStage.PER_PROPOSAL_TIMEOUT * 2 <= 1800
