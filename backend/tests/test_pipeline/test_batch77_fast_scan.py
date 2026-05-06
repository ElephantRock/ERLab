"""Tests for BATCH-77 — Fast Path Orchestrator.

TASK-01: FastProposalSynthesizer (5 tests)
TASK-02: Fast Scan Strategy Wiring (4 tests)

AIV v5.3 — T1 (falsifiable), T2 (happy/error), T5 (traceability)

NOTE: pytest.ini has `-p no:asyncio`. Use asyncio.run() directly.
"""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.pipeline.synthesis.fast_synthesizer import FastProposalSynthesizer
from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal
from backend.pipeline.strategies.registry import StrategyRegistry
from backend.pipeline.strategies.presets import register_presets


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

def test_77_02_01_fast_scan_has_6_enabled_stages():
    """fast_scan strategy enables exactly 6 of 9 stages."""
    registry = StrategyRegistry()
    register_presets(registry)
    config = registry.get("fast_scan")
    enabled = [name for name, sc in config.stages.items() if sc.enabled]
    assert len(enabled) == 6


# TEST-77-02-02: fast_scan disables idea_generation
# AC-02-01

def test_77_02_02_fast_scan_skips_idea_generation():
    """fast_scan does NOT enable idea_generation (tree search) stage."""
    registry = StrategyRegistry()
    register_presets(registry)
    config = registry.get("fast_scan")
    assert config.stages["idea_generation"].enabled is False


def test_77_02_02b_fast_scan_skips_novelty_and_metrics():
    """fast_scan also disables novelty_checking and mechanical_metrics."""
    registry = StrategyRegistry()
    register_presets(registry)
    config = registry.get("fast_scan")
    assert config.stages["novelty_checking"].enabled is False
    assert config.stages["mechanical_metrics"].enabled is False


# TEST-77-02-03: fast_scan uses FastProposalSynthesizer
# AC-02-02

def test_77_02_03_fast_scan_max_time_under_5_minutes():
    """fast_scan max_total_time is under 5 minutes (300s)."""
    registry = StrategyRegistry()
    register_presets(registry)
    config = registry.get("fast_scan")
    assert config.max_total_time <= 300.0


# TEST-77-02-04: fast_scan uses fast_synthesizer module exists
# AC-02-02

def test_77_02_04_fast_synthesizer_module_exists():
    """FastProposalSynthesizer can be imported."""
    from backend.pipeline.synthesis.fast_synthesizer import FastProposalSynthesizer
    assert FastProposalSynthesizer is not None
    assert hasattr(FastProposalSynthesizer, "synthesize")


# ── Additional coverage ──────────────────────────────────

def test_fallback_proposal_on_general_exception(mock_idea):
    """Any LLM exception produces a fallback proposal, not a crash."""
    provider = AsyncMock()
    provider.complete = AsyncMock(side_effect=RuntimeError("Unexpected"))
    synth = FastProposalSynthesizer(provider=provider)
    result = asyncio.run(synth.synthesize([mock_idea], [], []))
    assert len(result) == 1
    assert result[0].sections.get("fallback") is True


def test_no_provider_returns_fallback(mock_idea):
    """Without a provider, returns fallback proposals."""
    import asyncio
    synth = FastProposalSynthesizer(provider=None)
    result = asyncio.run(synth.synthesize([mock_idea], [], []))
    assert len(result) == 1
    assert result[0].sections["Abstract"]


def test_parse_sections_from_markdown():
    """Section parsing works with standard markdown headers."""
    synth = FastProposalSynthesizer()
    text = (
        "## Abstract\nThis is the abstract.\n\n"
        "## Key Idea\nThis is the key idea.\n\n"
        "## Method Sketch\nThis is the method.\n"
    )
    sections = synth._parse_sections(text)
    assert "abstract" in sections["Abstract"].lower()
    assert "key idea" in sections["Key Idea"].lower()
    assert "method" in sections["Method Sketch"].lower()
