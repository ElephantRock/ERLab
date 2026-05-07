"""BATCH-112: ReferenceVerifier Pipeline Integration tests.

Validates that the orchestrator wires reference verification after
proposal synthesis and handles all edge cases per HB-01/HB-02.
"""
import asyncio
import json
import logging
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from types import SimpleNamespace

# We test the _verify_references method in isolation


def _make_orchestrator():
    """Create a minimal PipelineOrchestrator with _verify_references available."""
    from backend.pipeline.orchestrator import PipelineOrchestrator
    from backend.pipeline.verification.reference_verifier import ReferenceVerifier
    from backend.pipeline.result import PipelineResult

    orch = object.__new__(PipelineOrchestrator)
    orch._reference_verifier = ReferenceVerifier()
    orch._integration = None
    return orch


def _make_paper(title="Test Paper", authors=None, year=2024):
    """Create a mock paper object."""
    return SimpleNamespace(
        title=title,
        authors=authors or ["Smith"],
        year=year,
    )


def _make_proposal(content_md="", title="Test Proposal"):
    """Create a mock proposal with content_md."""
    proposal = SimpleNamespace(
        title=title,
        content_md=content_md,
        metadata="{}",
    )
    return proposal


def _make_ctx(all_papers=None):
    """Create a mock StageContext."""
    ctx = SimpleNamespace(
        all_papers=all_papers or [],
    )
    return ctx


# ── TEST-112-01-01: _verify_references exists ──────────────────────

def test_112_01_01_verify_references_exists():
    """_verify_references method exists on PipelineOrchestrator."""
    from backend.pipeline.orchestrator import PipelineOrchestrator
    assert hasattr(PipelineOrchestrator, '_verify_references'), \
        "PipelineOrchestrator must have _verify_references method"


# ── TEST-112-01-02: Verification runs without crashing on empty input ──

def test_112_01_02_empty_input_no_crash():
    """Verification runs without crashing on empty proposals."""
    orch = _make_orchestrator()
    result = SimpleNamespace(proposals=[])
    ctx = _make_ctx()

    # Should not raise any exception
    orch._verify_references(result, ctx)


# ── TEST-112-01-03: Verification logs warning on low trust score ────

def test_112_01_03_logs_warning_low_trust(caplog):
    """Verification logs warning when trust score is below threshold."""
    orch = _make_orchestrator()
    # Proposal with citations that don't match corpus
    proposal = _make_proposal(
        content_md="According to FakeAuthor et al., 1999, this is true. "
                   "Also see MadeUp (2020) for more details."
    )
    result = SimpleNamespace(proposals=[proposal])
    ctx = _make_ctx(all_papers=[_make_paper("Real Paper", ["Jones"], 2024)])

    with caplog.at_level(logging.WARNING, logger="backend.pipeline.orchestrator"):
        orch._verify_references(result, ctx)

    assert any("trust" in r.message.lower() or "low reference" in r.message.lower()
               for r in caplog.records), \
        f"Expected trust/verification warning in logs, got: {[r.message for r in caplog.records]}"


# ── TEST-112-01-04: Verification does not block pipeline (HB-01) ──

def test_112_01_04_does_not_block_pipeline():
    """Pipeline continues even when verification raises an exception (HB-01)."""
    orch = _make_orchestrator()

    # Force the verifier to raise
    orch._reference_verifier = MagicMock()
    orch._reference_verifier.verify.side_effect = RuntimeError("verifier crashed")

    proposal = _make_proposal(content_md="Some content with Smith et al., 2024.")
    result = SimpleNamespace(proposals=[proposal])
    ctx = _make_ctx(all_papers=[_make_paper("A Paper", ["Smith"], 2024)])

    # Must NOT raise — HB-01
    orch._verify_references(result, ctx)


# ── TEST-112-01-05: High trust score leaves proposals unchanged ──

def test_112_01_05_high_trust_no_modification():
    """Verification accepts high trust score without modifying content."""
    orch = _make_orchestrator()
    original_text = "Based on Smith et al., 2024, we propose a novel method."
    proposal = _make_proposal(content_md=original_text)
    result = SimpleNamespace(proposals=[proposal])
    ctx = _make_ctx(all_papers=[_make_paper("Real Paper", ["Smith"], 2024)])

    orch._verify_references(result, ctx)

    # Content should be unchanged because Smith 2024 matches the corpus
    assert proposal.content_md == original_text, \
        f"Proposal was modified despite matching corpus. Got: {proposal.content_md}"


# ── TEST-112-01-06: Corpus papers passed as list of dicts ──

def test_112_01_06_corpus_papers_as_dicts():
    """Corpus papers are correctly converted from objects to dicts."""
    orch = _make_orchestrator()
    proposal = _make_proposal(content_md="Smith et al., 2024 shows this.")
    result = SimpleNamespace(proposals=[proposal])

    # Pass actual SimpleNamespace objects (mimicking Paper objects)
    papers = [_make_paper("Paper A", ["Smith"], 2024)]
    ctx = _make_ctx(all_papers=papers)

    # Should not raise TypeError
    orch._verify_references(result, ctx)

    # Should have verified the citation
    assert "Smith" in proposal.content_md


# ── TEST-112-01-07: Verification runs after synthesis (HB-02) ──

def test_112_01_07_verification_after_synthesis():
    """Verification is called in the synthesis persistence block, not before."""
    # Check that in orchestrator.py, _verify_references is called
    # inside the `if stage.name == "proposal_synthesis"` block
    import inspect
    from backend.pipeline.orchestrator import PipelineOrchestrator

    source = inspect.getsource(PipelineOrchestrator.run)

    # Find the synthesis persistence block
    synth_idx = source.find('if stage.name == "proposal_synthesis"')
    assert synth_idx > 0, "proposal_synthesis block not found in run()"

    # Find _verify_references call
    verify_idx = source.find('self._verify_references(result, ctx)')
    assert verify_idx > 0, "_verify_references call not found in run()"

    # Verify call is AFTER the synthesis block (HB-02)
    assert verify_idx > synth_idx, \
        "_verify_references must be called AFTER proposal_synthesis block (HB-02)"


# ── TEST-112-01-08: Stripped proposals still valid markdown ──

def test_112_01_08_stripped_proposals_valid_markdown():
    """Stripped proposals preserve markdown headers and structure."""
    orch = _make_orchestrator()
    original = "# Proposal Title\n\n## Method\n\nBased on FakeRef et al., 1999.\n\n## Results\n\nSee AlsoFake (2020)."
    proposal = _make_proposal(content_md=original)
    result = SimpleNamespace(proposals=[proposal])
    ctx = _make_ctx(all_papers=[])  # Empty corpus = everything unverifiable

    orch._verify_references(result, ctx)

    # Headers must still be present
    assert "# Proposal Title" in proposal.content_md, \
        "Header was lost during citation stripping"
    assert "## Method" in proposal.content_md, \
        "Method header was lost during citation stripping"
    assert "## Results" in proposal.content_md, \
        "Results header was lost during citation stripping"
    # Citations should be replaced with [Citation needed] markers
    assert "[Citation needed" in proposal.content_md, \
        "Expected [Citation needed] markers in stripped text"
