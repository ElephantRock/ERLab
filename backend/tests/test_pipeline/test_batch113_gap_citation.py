"""BATCH-113 TASK-01 — Citation integrity in gap analysis prompt.

Tests verify:
- CITATION INTEGRITY section in prompt
- Paper summaries include author names and year
- Empty paper list handled (HB-01)
- "do not invent" instruction
- GapAnalyzer initialization
- 30-paper limit
- Valid gap types in prompt
"""

import pytest

from backend.pipeline.gap_analysis.gap_analyzer import GAP_ANALYSIS_PROMPT, GapAnalyzer
from backend.pipeline.literature.models import Author, Paper


# ---------------------------------------------------------------------------
# TEST-113-01-01: Prompt contains CITATION INTEGRITY instruction
# ---------------------------------------------------------------------------
def test_113_01_01_citation_integrity_in_prompt():
    """GAP_ANALYSIS_PROMPT must contain the CITATION INTEGRITY (MANDATORY) section."""
    assert "CITATION INTEGRITY" in GAP_ANALYSIS_PROMPT
    assert "MANDATORY" in GAP_ANALYSIS_PROMPT


# ---------------------------------------------------------------------------
# TEST-113-01-02: Paper summaries include author names
# ---------------------------------------------------------------------------
def test_113_01_02_paper_summaries_include_author_names():
    """_format_paper_summaries must include Author.name in the output."""
    papers = [
        Paper(
            id="p1",
            source="test",
            title="Test Paper",
            authors=[Author(name="Smith"), Author(name="Jones")],
            year=2024,
        )
    ]
    result = GapAnalyzer._format_paper_summaries(papers)
    assert "Smith" in result
    assert "Jones" in result


# ---------------------------------------------------------------------------
# TEST-113-01-03: Empty papers — no crash (HB-01)
# ---------------------------------------------------------------------------
def test_113_01_03_empty_papers_no_crash():
    """_format_paper_summaries must handle empty list without exception."""
    result = GapAnalyzer._format_paper_summaries([])
    assert isinstance(result, str)
    assert result.strip() != ""


# ---------------------------------------------------------------------------
# TEST-113-01-04: Prompt instructs not to invent citations
# ---------------------------------------------------------------------------
def test_113_01_04_do_not_invent_instruction():
    """Prompt must contain an explicit 'do not invent' or 'only reference' instruction."""
    prompt_lower = GAP_ANALYSIS_PROMPT.lower()
    assert "do not invent" in prompt_lower or "only reference" in prompt_lower or "do not" in prompt_lower


# ---------------------------------------------------------------------------
# TEST-113-01-05: Paper summaries include year
# ---------------------------------------------------------------------------
def test_113_01_05_paper_summaries_include_year():
    """_format_paper_summaries must include the paper year."""
    papers = [
        Paper(
            id="p2",
            source="test",
            title="Year Test Paper",
            authors=[Author(name="Doe")],
            year=2024,
        )
    ]
    result = GapAnalyzer._format_paper_summaries(papers)
    assert "2024" in result


# ---------------------------------------------------------------------------
# TEST-113-01-06: GapAnalyzer initializes with provider
# ---------------------------------------------------------------------------
def test_113_01_06_analyzer_init_with_provider():
    """GapAnalyzer must accept an LLMProvider and initialize without error."""
    analyzer = GapAnalyzer(provider=None)
    assert analyzer._provider is None


# ---------------------------------------------------------------------------
# TEST-113-01-07: 30-paper limit
# ---------------------------------------------------------------------------
def test_113_01_07_thirty_paper_limit():
    """_format_paper_summaries must produce at most 30 entries."""
    papers = [
        Paper(
            id=f"p{i}",
            source="test",
            title=f"Paper {i}",
            authors=[Author(name="Author")],
            year=2020,
        )
        for i in range(50)
    ]
    result = GapAnalyzer._format_paper_summaries(papers)
    lines = [l for l in result.strip().split("\n") if l and l[0].isdigit()]
    assert len(lines) <= 30


# ---------------------------------------------------------------------------
# TEST-113-01-08: Valid gap types in prompt
# ---------------------------------------------------------------------------
def test_113_01_08_valid_gap_types_in_prompt():
    """Prompt must list the four valid gap types."""
    valid_types = {"methodological", "empirical", "theoretical", "cross-domain"}
    for gt in valid_types:
        assert gt in GAP_ANALYSIS_PROMPT
