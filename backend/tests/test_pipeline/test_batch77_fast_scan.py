"""Tests for BATCH-77 — Fast Path Orchestrator.

TASK-01: FastProposalSynthesizer (5 tests)
TASK-02: Fast Scan Strategy Wiring (4 tests)

AIV v5.3 — T1 (falsifiable), T2 (happy/error), T5 (traceability)

NOTE: pytest.ini has `-p no:asyncio`. Use asyncio.run() directly.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.pipeline.synthesis.fast_synthesizer import FastProposalSynthesizer

# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def mock_idea():
    idea = MagicMock()
    idea.title = "Test Idea: Neural Architecture for Sparse Data"
    idea.description = "A novel approach using sparse attention mechanisms."
    idea.domain = "AI/NLP"
    return idea


@pytest.fixture
def mock_gap():
    gap = MagicMock()
    gap.title = "No efficient sparse attention for small datasets"
    gap.description = "Existing sparse attention methods require large training sets."
    gap.name = gap.title
    return gap


@pytest.fixture
def mock_paper():
    paper = MagicMock()
    paper.title = "Sparse Transformers"
    paper.year = 2019
    return paper


@pytest.fixture
def mock_provider():
    provider = AsyncMock()
    provider.complete = AsyncMock(return_value=(
        "## Abstract\n"
        "We propose a sparse attention mechanism for small datasets.\n\n"
        "## Key Idea\n"
        "Use adaptive sparse masks that learn from data distribution.\n\n"
        "## Method Sketch\n"
        "1. Train sparse mask on small dataset. 2. Evaluate on benchmarks.\n"
    ))
    return provider


# ══════════════════════════════════════════════════════════
# TASK-01: FastProposalSynthesizer Tests
# ══════════════════════════════════════════════════════════

# TEST-77-01-01: Empty input → empty output
# AC-01-01

def test_77_01_01_empty_input_returns_empty_list():
    """FastProposalSynthesizer returns empty list for empty input."""
    synth = FastProposalSynthesizer()
    result = asyncio.run(synth.synthesize([], [], []))
    assert result == []


# TEST-77-01-02: 3 sections present
# AC-01-01

def test_77_01_02_three_sections_in_proposal(mock_provider, mock_idea, mock_gap, mock_paper):
    """Each proposal has exactly 3 sections: Abstract, Key Idea, Method Sketch."""
    synth = FastProposalSynthesizer(provider=mock_provider)
    result = asyncio.run(synth.synthesize([mock_idea], [mock_gap], [mock_paper]))
    assert len(result) == 1
    proposal = result[0]
    assert "Abstract" in proposal.sections
    assert "Key Idea" in proposal.sections
    assert "Method Sketch" in proposal.sections


# TEST-77-01-03: Under 3000 chars
# AC-01-02

def test_77_01_03_proposal_under_3000_chars(mock_provider, mock_idea, mock_gap):
    """Total proposal text stays under 3000 chars."""
    synth = FastProposalSynthesizer(provider=mock_provider)
    result = asyncio.run(synth.synthesize([mock_idea], [mock_gap], []))
    total_chars = sum(len(v) for v in result[0].sections.values() if isinstance(v, str))
    assert total_chars < FastProposalSynthesizer.MAX_TOTAL_CHARS


# TEST-77-01-04: Provider called
# AC-01-01

def test_77_01_04_provider_called(mock_provider, mock_idea, mock_gap):
    """FastProposalSynthesizer calls the LLM provider."""
    synth = FastProposalSynthesizer(provider=mock_provider)
    asyncio.run(synth.synthesize([mock_idea], [mock_gap], []))
    assert mock_provider.complete.called


# TEST-77-01-05: Graceful timeout handling
# AC-01-03

def test_77_01_05_handles_llm_timeout_gracefully(mock_idea, mock_gap):
    """When LLM times out, returns fallback proposal."""
    provider = AsyncMock()
    provider.complete = AsyncMock(side_effect=TimeoutError("LLM timeout"))
    synth = FastProposalSynthesizer(provider=provider)
    result = asyncio.run(synth.synthesize([mock_idea], [mock_gap], []))
    assert len(result) == 1
    assert result[0].sections["Abstract"]  # Has content
    assert result[0].sections.get("fallback") is True


# ══════════════════════════════════════════════════════════
# TASK-02: Fast Scan Strategy Wiring Tests
# ══════════════════════════════════════════════════════════

# TEST-77-02-01: fast_scan has 6 enabled stages
# AC-02-01
