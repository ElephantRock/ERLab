"""Tests for BATCH-97 — BibTeX Export.

AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

from backend.pipeline.export.bibtex_exporter import (
    paper_to_bibtex,
    papers_to_bibtex,
    proposal_to_bibtex,
)
from backend.pipeline.literature.models import Author, Paper


def _make_paper(title="Test Paper", year=2024, doi="10.1234/test", venue="Nature"):
    return Paper(
        id="test:1", title=title, abstract="Abstract text", year=year,
        authors=[Author(name="Jane Smith"), Author(name="John Doe")],
        doi=doi, url="https://example.com", source="test",
        citation_count=10, venue=venue,
    )


def test_97_01_paper_to_bibtex():
    """Paper converts to valid BibTeX."""
    paper = _make_paper()
    bibtex = paper_to_bibtex(paper)
    assert bibtex.startswith("@article{")
    assert "title = {Test Paper}" in bibtex
    assert "Jane Smith and John Doe" in bibtex
    assert "year = {2024}" in bibtex
    assert "doi = {10.1234/test}" in bibtex
    assert bibtex.endswith("}")


def test_97_01_bibtex_has_citation_key():
    """BibTeX entry has a valid citation key."""
    paper = _make_paper()
    bibtex = paper_to_bibtex(paper)
    first_line = bibtex.split("\n")[0]
    assert first_line.startswith("@article{")
    assert "," in first_line


def test_97_01_papers_to_bibtex_multiple():
    """Multiple papers produce multiple entries."""
    papers = [_make_paper(title="Paper A"), _make_paper(title="Paper B")]
    bibtex = papers_to_bibtex(papers)
    assert bibtex.count("@article{") == 2
    assert "Paper A" in bibtex
    assert "Paper B" in bibtex


def test_97_02_proposal_to_bibtex():
    """Proposal generates BibTeX entry."""
    bibtex = proposal_to_bibtex("Novel AI Architecture", domain="AI", year=2026)
    assert "@misc{" in bibtex
    assert "Elephant Rock Research Platform" in bibtex
    assert "2026" in bibtex


def test_97_02_empty_paper():
    """Paper with minimal fields still produces valid BibTeX."""
    paper = Paper(id="test:2", title="Minimal", source="test")
    bibtex = paper_to_bibtex(paper)
    assert "@article{" in bibtex
    assert "Minimal" in bibtex


def test_97_02_long_abstract_truncated():
    """Very long abstract is truncated in BibTeX."""
    paper = Paper(
        id="test:3", title="Test", source="test",
        abstract="A" * 1000,
    )
    bibtex = paper_to_bibtex(paper)
    # Abstract should be truncated
    assert "..." in bibtex
    assert len(bibtex) < 800
