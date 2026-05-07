"""Tests for BATCH-111 — Verification subsystem (reference checker, deepener, evaluator).

Addresses reviewer concerns:
- Reference reliability: ReferenceVerifier flags hallucinated citations
- Proposal depth: ProposalDeepener adds architecture + toy examples + failure modes
- Pipeline evaluation: PipelineEvaluator computes precision/recall on gap detection

AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

import pytest

from backend.pipeline.verification.reference_verifier import ReferenceVerifier
from backend.pipeline.verification.proposal_deepener import ProposalDeepener, DeepenedProposal
from backend.pipeline.verification.pipeline_evaluator import PipelineEvaluator


# ══════════════════════════════════════════════════════════
# ReferenceVerifier
# ══════════════════════════════════════════════════════════

def test_111_01_verifier_extracts_citations():
    """Citations are extracted from proposal text."""
    verifier = ReferenceVerifier()
    text = "As shown by Besta et al., 2024, the GoT framework improves over Wei et al., 2022."
    citations = verifier._extract_citations(text)
    authors = [c.author for c in citations]
    assert "Besta et al." in authors or "Besta et al" in authors
    assert "Wei et al." in authors or "Wei et al" in authors


def test_111_01_verifier_flags_hallucinated():
    """Hallucinated citations are flagged as unverifiable."""
    verifier = ReferenceVerifier()
    proposal = "According to Smith et al., 2025, neuro-symbolic systems achieve 99% accuracy."
    corpus = [
        {"title": "Neuro-Symbolic AI", "authors": ["Jones"], "year": "2024"},
    ]
    report = verifier.verify(proposal, corpus)
    assert report.total_citations >= 1
    assert report.potentially_hallucinated >= 1
    assert report.trust_score < 1.0


def test_111_01_verifier_confirms_real():
    """Real citations are confirmed against corpus."""
    verifier = ReferenceVerifier()
    proposal = "Wei et al., 2022 introduced Chain-of-Thought prompting."
    corpus = [
        {"title": "Chain-of-Thought Prompting", "authors": ["Wei"], "year": "2022"},
    ]
    report = verifier.verify(proposal, corpus)
    assert report.verified >= 1
    assert report.trust_score == 1.0


def test_111_01_verifier_strips_unverified():
    """Unverified citations are replaced with [Citation needed] markers."""
    verifier = ReferenceVerifier()
    proposal = "According to FakeAuthor et al., 2099, everything is solved."
    report = verifier.verify(proposal, [])
    stripped = verifier.strip_unverified_citations(proposal, report)
    assert "Citation needed" in stripped


# ══════════════════════════════════════════════════════════
# ProposalDeepener
# ══════════════════════════════════════════════════════════

def test_111_02_deepener_template_mode():
    """Template mode generates structured deepening without LLM."""
    deepener = ProposalDeepener(provider=None)
    idea = {
        "id": 42,
        "title": "TestProposal: A Novel Method",
        "problem_statement": "Something is broken",
        "proposed_method": "Fix it with graphs",
    }
    result = deepener._deepen_template(idea)
    assert isinstance(result, DeepenedProposal)
    assert "Preliminary Architecture" in result.architecture
    assert "Working Example" in result.toy_example
    assert "Failure Mode" in result.failure_modes
    assert "Success Criteria" in result.success_criteria
    assert "Metric" in result.success_criteria


def test_111_02_deepener_has_all_sections():
    """Deepened proposal has all four required sections."""
    deepener = ProposalDeepener(provider=None)
    idea = {"id": 1, "title": "Test", "problem_statement": "P", "proposed_method": "M"}
    result = deepener._deepen_template(idea)
    assert result.architecture != ""
    assert result.toy_example != ""
    assert result.failure_modes != ""
    assert result.success_criteria != ""


def test_111_02_deepener_failure_modes_are_concrete():
    """Failure modes list specific scenarios."""
    deepener = ProposalDeepener(provider=None)
    idea = {"id": 1, "title": "Test", "problem_statement": "P", "proposed_method": "M"}
    result = deepener._deepen_template(idea)
    # Should contain root cause + mitigation
    assert "Root cause" in result.failure_modes
    assert "Mitigation" in result.failure_modes


# ══════════════════════════════════════════════════════════
# PipelineEvaluator
# ══════════════════════════════════════════════════════════

def test_111_03_evaluator_computes_recall():
    """Evaluator computes recall against known gaps."""
    evaluator = PipelineEvaluator(known_gaps=["cost efficiency reasoning", "explainability graph paths"])

    detected = [
        {"title": "Cost Efficiency in Structured Reasoning", "gap_type": "empirical"},
        {"title": "Unrelated Gap", "gap_type": "theoretical"},
    ]
    ideas = [
        {"title": "Idea 1", "novelty_score": 0.85},
    ]
    report = evaluator.evaluate(detected, ideas)
    # "Cost Efficiency" should overlap with known "cost efficiency reasoning"
    assert report.gap_recall > 0


def test_111_03_evaluator_computes_precision():
    """All detected gaps are counted as meaningful."""
    evaluator = PipelineEvaluator(known_gaps=[])
    detected = [
        {"title": "Gap 1", "gap_type": "theoretical"},
        {"title": "Gap 2", "gap_type": "empirical"},
    ]
    report = evaluator.evaluate(detected, [])
    assert report.gap_precision == 1.0  # All gaps are meaningful by default


def test_111_03_evaluator_novelty_rate():
    """Idea novelty rate is computed correctly."""
    evaluator = PipelineEvaluator()
    ideas = [
        {"title": "I1", "novelty_score": 0.9},
        {"title": "I2", "novelty_score": 0.5},
        {"title": "I3", "novelty_score": 0.85},
    ]
    report = evaluator.evaluate([], ideas)
    assert report.ideas_novel == 2  # Only 0.9 and 0.85 >= 0.7
    assert abs(report.idea_novelty_rate - 2/3) < 0.01


def test_111_03_evaluator_quality_score():
    """Overall quality score is in [0, 1]."""
    evaluator = PipelineEvaluator()
    detected = [{"title": "benchmark evaluation metrics", "gap_type": "empirical"}]
    ideas = [{"title": "I1", "novelty_score": 0.8}]
    report = evaluator.evaluate(detected, ideas)
    assert 0.0 <= report.pipeline_quality_score <= 1.0


def test_111_03_evaluator_report_str():
    """Report has human-readable string representation."""
    evaluator = PipelineEvaluator()
    report = evaluator.evaluate(
        [{"title": "Test", "gap_type": "theoretical"}],
        [{"title": "I1", "novelty_score": 0.9}],
    )
    report_str = str(report)
    assert "Gap precision" in report_str
    assert "Quality score" in report_str
