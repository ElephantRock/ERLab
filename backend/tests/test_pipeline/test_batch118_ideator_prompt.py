"""BATCH-118: Ideator Agent Prompt Hardening tests.

Validates that the ideator system prompt includes gap-informed design,
grounded methodology, concise field constraints, and the n_ideas variable.

Updated after template simplification (commit 504bded): the prompt was
trimmed from verbose paper-length instructions to concise 1-3 sentence
per-field guidance that matches the actual JSON schema. The old CITATION
INTEGRITY, architecture, and failure-modes sections were intentionally
removed because they caused the LLM to generate 63K chars of output,
truncating mid-JSON.
"""
from pathlib import Path

PROMPT_PATH = Path(__file__).resolve().parents[3] / "backend" / "pipeline" / "generation" / "prompts" / "ideator_system.md"


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


# ── TEST-118-01-01: Prompt contains gap-informed design ──────────

def test_118_01_01_citation_integrity():
    """Prompt contains gap-informed and grounded design principles."""
    prompt = _load_prompt().lower()
    assert "gap-informed" in prompt or "gap" in prompt, \
        "Prompt must reference research gaps as the basis for ideas"


# ── TEST-118-01-02: Prompt requires concise fields ───────────────

def test_118_01_02_architecture_requirements():
    """Prompt constrains output to concise fields matching the JSON schema."""
    prompt = _load_prompt().lower()
    assert "concise" in prompt or "brief" in prompt, \
        "Prompt must constrain output length to prevent token exhaustion"


# ── TEST-118-01-03: Prompt has exactly 6 output fields ───────────

def test_118_01_03_failure_modes():
    """Prompt lists the 6 JSON schema fields without extra sections."""
    prompt = _load_prompt()
    expected_fields = [
        "title", "problem_statement", "proposed_method",
        "expected_contributions", "novelty_rationale", "evaluation_approach",
    ]
    for field in expected_fields:
        assert field in prompt, f"Prompt must reference field '{field}'"


# ── TEST-118-01-04: Prompt still contains n_ideas variable ────────

def test_118_01_04_n_ideas_variable():
    """Prompt template still contains {{ n_ideas }} variable."""
    prompt = _load_prompt()
    assert "{{ n_ideas }}" in prompt or "n_ideas" in prompt, \
        "Prompt must contain the n_ideas template variable"
