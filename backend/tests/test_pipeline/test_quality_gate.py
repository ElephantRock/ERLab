"""Tests for the proposal quality gate in ProposalSynthesizer._check_quality() (P13)."""

import sys
from unittest.mock import MagicMock

sys.modules.setdefault("chromadb", MagicMock())

from backend.pipeline.synthesis.proposal_synthesizer import ProposalSynthesizer, ResearchProposal


def _make_long_text(word_count: int) -> str:
    """Generate a string with approximately word_count words."""
    return " ".join(f"word{i}" for i in range(word_count))


def test_quality_passes_with_long_sections():
    """Abstract 50+ words, intro 100+, method 100+ passes quality gate."""
    proposal = ResearchProposal(
        abstract=_make_long_text(60),
        introduction=_make_long_text(120),
        proposed_method=_make_long_text(110),
    )
    passed, issues = ProposalSynthesizer._check_quality(proposal)
    assert passed is True
    assert issues == []


def test_quality_fails_with_short_abstract():
    """Abstract with fewer than 50 words fails quality gate."""
    proposal = ResearchProposal(
        abstract=_make_long_text(30),
        introduction=_make_long_text(120),
        proposed_method=_make_long_text(110),
    )
    passed, issues = ProposalSynthesizer._check_quality(proposal)
    assert passed is False
    assert any("abstract" in issue for issue in issues)


def test_quality_fails_with_multiple_short_sections():
    """Both intro and method short fails with 2 issues."""
    proposal = ResearchProposal(
        abstract=_make_long_text(60),
        introduction=_make_long_text(50),
        proposed_method=_make_long_text(40),
    )
    passed, issues = ProposalSynthesizer._check_quality(proposal)
    assert passed is False
    assert len(issues) == 2
    assert any("introduction" in issue for issue in issues)
    assert any("proposed_method" in issue for issue in issues)
