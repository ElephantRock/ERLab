"""Tests for BATCH-89 — Anti-Fabrication Guard.

AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

import pytest

from backend.pipeline.safety.anti_fabrication import (
    AntiFabricationGuard,
    GuardResult,
)


@pytest.fixture
def guard():
    return AntiFabricationGuard()


def test_89_01_clean_proposal_passes(guard):
    """A clean proposal gets confidence 1.0 and no warnings."""
    result = guard.check_proposal(
        "We propose a novel method for analyzing neural network interpretability "
        "using attention weight decomposition. Our approach builds on existing work "
        "by Vaswani et al. (2017) and extends it with multi-scale analysis."
    )
    assert result.passed is True
    assert result.confidence_score == 1.0
    assert len(result.warnings) == 0


def test_89_01_suspicious_doi_detected(guard):
    """Fabricated DOI triggers CRITICAL warning."""
    result = guard.check_proposal(
        "See our results at doi:10.9999/fake-paper for details."
    )
    assert result.has_critical
    assert any(w.category == "suspicious_doi" for w in result.warnings)


def test_89_01_high_statistic_flagged(guard):
    """99.7% improvement claim triggers CAUTION warning."""
    result = guard.check_proposal(
        "Our method shows an improvement of 99.7% over baseline."
    )
    assert any(w.category == "unsupported_statistic" for w in result.warnings)


def test_89_01_fabricated_author_detected(guard):
    """Dr. Test Name triggers CRITICAL warning."""
    result = guard.check_proposal(
        "Following the work of Dr. Test Smith, we propose..."
    )
    assert any(w.category == "fabricated_author" for w in result.warnings)


def test_89_01_generic_claim_flagged(guard):
    """'Our method outperforms' triggers INFO warning."""
    result = guard.check_proposal(
        "Our method outperforms all existing approaches."
    )
    assert any(w.category == "generic_claim" for w in result.warnings)


def test_89_02_fail_open_always_passes(guard):
    """Guard never rejects — always passes (HB-01)."""
    result = guard.check_proposal(
        "Dr. Fake Author claims 99.9% improvement at doi:10.9999/test. "
        "Our method outperforms everything."
    )
    assert result.passed is True


def test_89_02_does_not_modify_content(guard):
    """Guard does not modify the input text (HB-02)."""
    text = "Original text with 99.5% improvement claims."
    result = guard.check_proposal(text)
    assert isinstance(result, GuardResult)
    assert isinstance(result.warnings, list)
    # GuardResult doesn't contain modified text


def test_89_02_confidence_decreases_with_warnings(guard):
    """More warnings → lower confidence."""
    clean_result = guard.check_proposal("A reasonable proposal with evidence.")
    dirty_result = guard.check_proposal(
        "Dr. Test claims 99.9% at doi:10.9999/fake. Our method outperforms."
    )
    assert dirty_result.confidence_score < clean_result.confidence_score


def test_89_02_empty_text_passes(guard):
    """Empty text passes with confidence 1.0."""
    result = guard.check_proposal("")
    assert result.passed is True
    assert result.confidence_score == 1.0


def test_89_02_known_dois_not_flagged():
    """DOIs in known set are not flagged."""
    guard = AntiFabricationGuard(known_dois={"10.1234/real-paper"})
    result = guard.check_proposal("See 10.1234/real-paper for details.")
    # This DOI is not in the suspicious pattern so it passes
    assert len(result.warnings) == 0
