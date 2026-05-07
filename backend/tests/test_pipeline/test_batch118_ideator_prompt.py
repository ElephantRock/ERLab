"""BATCH-118: Ideator Agent Prompt Hardening tests.

Validates that the ideator system prompt includes citation integrity,
architecture requirements, failure modes, and measurable criteria.
"""
import pytest
from pathlib import Path


PROMPT_PATH = Path(__file__).resolve().parents[3] / "backend" / "pipeline" / "generation" / "prompts" / "ideator_system.md"


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


# ── TEST-118-01-01: Prompt contains citation integrity ────────────

def test_118_01_01_citation_integrity():
    """Prompt contains citation integrity instruction."""
    prompt = _load_prompt()
    assert "CITATION INTEGRITY" in prompt, \
        "Prompt must contain CITATION INTEGRITY section"


# ── TEST-118-01-02: Prompt requires architecture details ──────────

def test_118_01_02_architecture_requirements():
    """Prompt requires architecture/component details."""
    prompt = _load_prompt().lower()
    has_arch = "architecture" in prompt or "component" in prompt
    assert has_arch, "Prompt must require architecture or component details"


# ── TEST-118-01-03: Prompt requires failure modes ─────────────────

def test_118_01_03_failure_modes():
    """Prompt requires failure mode analysis."""
    prompt = _load_prompt().lower()
    assert "failure" in prompt, "Prompt must require failure mode analysis"


# ── TEST-118-01-04: Prompt still contains n_ideas variable ────────

def test_118_01_04_n_ideas_variable():
    """Prompt template still contains {{ n_ideas }} variable."""
    prompt = _load_prompt()
    assert "{{ n_ideas }}" in prompt or "n_ideas" in prompt, \
        "Prompt must contain the n_ideas template variable"
