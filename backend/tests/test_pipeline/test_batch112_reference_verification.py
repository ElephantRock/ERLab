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
    """verify_references method exists on ResultProcessor (used by orchestrator)."""
    from backend.pipeline.orchestrator.result_processor import ResultProcessor
    assert hasattr(ResultProcessor, 'verify_references'), \
        "ResultProcessor must have verify_references method"


# ── TEST-112-01-02: Verification runs without crashing on empty input ──
