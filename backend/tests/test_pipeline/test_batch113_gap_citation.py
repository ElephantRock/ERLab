"""BATCH-113: Citation Grounding in Gap Analysis tests.

Validates that the gap analysis prompt includes citation integrity
instructions and paper summaries include author names and years.
"""
import logging
import pytest
from types import SimpleNamespace

from backend.pipeline.gap_analysis.gap_analyzer import (
    GAP_ANALYSIS_PROMPT,
    GapAnalyzer,
    _title_similarity,
)
from backend.pipeline.literature.models import Author, Paper


def _make_paper(title="Test Paper", authors=None, year=2024, abstract="Abstract text"):
    return Paper(
        id=f"paper-{title[:10]}",
        source="test",
        title=title,
        authors=[Author(name=a) for a in (authors or ["Smith", "Jones"])],
        year=year,
        abstract=abstract,
    )


# ── TEST-113-01-01: Prompt contains citation integrity ────────────

def test_113_01_01_citation_integrity_in_prompt():
    """GAP_ANALYSIS_PROMPT contains CITATION INTEGRITY instruction."""
    assert "CITATION INTEGRITY" in GAP_ANALYSIS_PROMPT, \
        "Prompt must contain CITATION INTEGRITY section header"


# ── TEST-113-01-02: Paper summaries include author names ──────────

def test_113_01_02_paper_summaries_include_authors():
    """_format_paper_summaries includes author names."""
    papers = [_make_paper("Neural Methods", ["Wei", "Chen", "Li"], 2024)]
    result = GapAnalyzer._format_paper_summaries(papers)
    assert "Wei" in result, f"Author 'Wei' not found in summary: {result}"
    assert "Chen" in result, f"Author 'Chen' not found in summary: {result}"


# ── TEST-113-01-03: Prompt works with empty papers (HB-01) ────────

def test_113_01_03_empty_papers_no_crash():
    """GapAnalyzer._format_paper_summaries works with empty list (HB-01)."""
    result = GapAnalyzer._format_paper_summaries([])
    assert result == "(No papers provided)" or result == "", \
        f"Expected empty message, got: {result}"


# ── TEST-113-01-04: Prompt instructs not to invent citations ──────

def test_113_01_04_no_invent_instruction():
    """Prompt explicitly tells LLM not to invent citations."""
    lower = GAP_ANALYSIS_PROMPT.lower()
    assert "do not" in lower and "invent" in lower or "only reference" in lower, \
        "Prompt must instruct not to invent or only reference provided papers"


# ── TEST-113-01-05: Paper summaries include year ──────────────────

def test_113_01_05_paper_summaries_include_year():
    """_format_paper_summaries includes the publication year."""
    papers = [_make_paper("Year Test", ["Author"], 2023)]
    result = GapAnalyzer._format_paper_summaries(papers)
    assert "2023" in result, f"Year 2023 not found in summary: {result}"


# ── TEST-113-01-06: GapAnalyzer initializes with provider ─────────

def test_113_01_06_analyzer_init():
    """GapAnalyzer initializes without error."""
    from unittest.mock import MagicMock
    mock_provider = MagicMock()
    analyzer = GapAnalyzer(mock_provider)
    assert analyzer._provider is mock_provider


# ── TEST-113-01-07: Paper summaries respect 30-paper limit ────────

def test_113_01_07_thirty_paper_limit():
    """_format_paper_summaries limits output to 30 papers."""
    papers = [_make_paper(f"Paper {i}", ["Author"], 2024) for i in range(50)]
    result = GapAnalyzer._format_paper_summaries(papers)
    # Count numbered entries (lines starting with a number)
    numbered = [l for l in result.split("\n") if l and l[0].isdigit()]
    assert len(numbered) <= 30, f"Expected ≤30 papers, got {len(numbered)}"


# ── TEST-113-01-08: Gap types are valid ────────────────────────────

def test_113_01_08_valid_gap_types():
    """Gap types must be from the allowed set."""
    allowed = {"methodological", "empirical", "theoretical", "cross-domain", "unknown"}
    # Check the prompt mentions the valid types
    for gap_type in ["methodological", "empirical", "theoretical", "cross-domain"]:
        assert gap_type in GAP_ANALYSIS_PROMPT, \
            f"Gap type '{gap_type}' not mentioned in prompt"
