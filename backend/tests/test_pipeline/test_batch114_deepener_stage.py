"""BATCH-114: ProposalDeepenerStage tests.

Validates that the ProposalDeepeningStage is wired into the pipeline,
produces all 4 deepening sections, and respects HB-01/HB-02.
"""
import asyncio
import json
import logging
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock

from backend.pipeline.stages import ProposalDeepeningStage, StageContext


def _make_proposal(title="Test Proposal", content_md="# Proposal\n\nMethod here."):
    return SimpleNamespace(
        title=title,
        content_md=content_md,
        problem_statement="Test problem",
        proposed_method="Test method",
        metadata="{}",
    )


def _make_ctx(proposals=None):
    from backend.pipeline.result import PipelineResult
    result = PipelineResult()
    if proposals:
        result.proposals = proposals
    ctx = StageContext(result=result)
    return ctx


# ── TEST-114-01-01: Class exists ──────────────────────────────────

def test_114_01_01_class_exists():
    """ProposalDeepeningStage can be imported."""
    from backend.pipeline.stages import ProposalDeepeningStage
    stage = ProposalDeepeningStage()
    assert stage is not None


# ── TEST-114-01-02: Stage runs without crashing (HB-01) ──────────

def test_114_01_02_hb01_non_blocking():
    """Pipeline continues even when deepener raises (HB-01)."""
    # Force the deepener to fail
    broken_deepener = MagicMock()
    broken_deepener.deepen = AsyncMock(side_effect=RuntimeError("LLM down"))

    stage = ProposalDeepeningStage(deepener=broken_deepener)
    proposals = {0: _make_proposal()}
    ctx = _make_ctx(proposals)

    # Must not raise
    result = asyncio.run(stage.execute(ctx))
    assert result is True, "Stage must return True (continue pipeline)"


# ── TEST-114-01-03: Template mode produces all 4 sections ─────────

def test_114_01_03_template_four_sections():
    """Template mode produces architecture, toy_example, failure_modes, success_criteria."""
    stage = ProposalDeepeningStage()
    proposals = {0: _make_proposal("Neuro-Symbolic Reasoning")}
    ctx = _make_ctx(proposals)

    asyncio.run(stage.execute(ctx))

    meta = json.loads(proposals[0].metadata)
    assert "deepened" in meta, "Missing 'deepened' key in metadata"
    d = meta["deepened"]
    assert len(d["architecture"]) > 50, f"Architecture section too short: {d['architecture'][:50]}"
    assert len(d["toy_example"]) > 50, f"Toy example section too short"
    assert len(d["failure_modes"]) > 50, f"Failure modes section too short"
    assert len(d["success_criteria"]) > 50, f"Success criteria section too short"


# ── TEST-114-01-04: Deepened content stored in metadata ──────────

def test_114_01_04_metadata_stored():
    """Deepened content is stored in proposal metadata."""
    stage = ProposalDeepeningStage()
    proposals = {1: _make_proposal("Test Idea")}
    ctx = _make_ctx(proposals)

    asyncio.run(stage.execute(ctx))

    meta = json.loads(proposals[1].metadata)
    assert "deepened" in meta, "Deepened data not stored in metadata"
    assert "architecture" in meta["deepened"], "Missing architecture in deepened"


# ── TEST-114-01-05: Original proposal text unchanged (HB-02) ─────

def test_114_01_05_hb02_original_unchanged():
    """Original proposal content_md is not overwritten (HB-02)."""
    stage = ProposalDeepeningStage()
    original_md = "# Original Proposal\n\nThis is the original text."
    proposals = {0: _make_proposal(content_md=original_md)}
    ctx = _make_ctx(proposals)

    asyncio.run(stage.execute(ctx))

    assert proposals[0].content_md == original_md, \
        f"HB-02 violation: original content was modified to: {proposals[0].content_md[:100]}"


# ── TEST-114-01-06: _STAGE_ORDER includes deepening ──────────────

def test_114_01_06_stage_order_includes_deepening():
    """_STAGE_ORDER includes 'proposal_deepening'."""
    from backend.pipeline.orchestrator import PipelineOrchestrator
    assert "proposal_deepening" in PipelineOrchestrator._STAGE_ORDER, \
        "'proposal_deepening' not in _STAGE_ORDER"


# ── TEST-114-01-07: Stage positioned after synthesis ─────────────

def test_114_01_07_after_synthesis():
    """proposal_deepening comes after proposal_synthesis in _STAGE_ORDER."""
    from backend.pipeline.orchestrator import PipelineOrchestrator
    order = PipelineOrchestrator._STAGE_ORDER
    synth_idx = order.index("proposal_synthesis")
    deepen_idx = order.index("proposal_deepening")
    assert deepen_idx > synth_idx, \
        f"proposal_deepening (idx={deepen_idx}) must come after proposal_synthesis (idx={synth_idx})"
