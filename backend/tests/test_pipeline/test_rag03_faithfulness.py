"""Tests for BATCH-RAG-03: Faithfulness Scorer.

Tests cover:
  1. FaithfulnessReport and ClaimAssessment data models
  2. Heuristic scoring (no LLM) — keyword overlap
  3. LLM parsing — JSON response parsing
  4. Graceful degradation on failures
  5. Edge cases: empty text, no sources
"""

import asyncio
import json

import pytest

from backend.pipeline.evaluation.faithfulness_scorer import (
    ClaimAssessment,
    FaithfulnessReport,
    FaithfulnessScorer,
)


# ── Model Tests ────────────────────────────────────────────────────────

def test_claim_assessment():
    """ClaimAssessment stores all fields."""
    ca = ClaimAssessment(
        claim="The model achieves 95% accuracy",
        score=0.8,
        supported=True,
        reasoning="Claim matches experimental results in source",
        source_id="paper-1",
    )
    assert ca.score == 0.8
    assert ca.supported is True


def test_faithfulness_report_support_rate():
    """FaithfulnessReport.support_rate computes correctly."""
    report = FaithfulnessReport(
        assessed_claims=10,
        supported_claims=7,
    )
    assert report.support_rate == 0.7


def test_faithfulness_report_support_rate_zero():
    """FaithfulnessReport.support_rate is 0 for no claims."""
    report = FaithfulnessReport(assessed_claims=0, supported_claims=0)
    assert report.support_rate == 0.0


def test_faithfulness_report_to_dict():
    """FaithfulnessReport serializes correctly."""
    report = FaithfulnessReport(
        proposal_id="p1",
        proposal_title="Test Proposal",
        overall_faithfulness=0.85,
        overall_relevance=0.90,
        overall_grounding=0.80,
        assessed_claims=5,
        supported_claims=4,
        reasoning="Good grounding",
    )
    d = report.to_dict()
    assert d["faithfulness"] == 0.85
    assert d["support_rate"] == 0.8
    assert d["proposal_id"] == "p1"


# ── Heuristic Scoring Tests ────────────────────────────────────────────

def test_heuristic_high_overlap():
    """Heuristic scorer gives high score when proposal uses source keywords."""
    scorer = FaithfulnessScorer(provider=None)
    report = asyncio.run(scorer.score_proposal(
        proposal_text="We propose a transformer-based attention mechanism for "
        "neural machine translation using self-attention layers",
        proposal_title="Transformer Attention",
        proposal_id="p1",
        source_texts=[
            "We introduce the transformer, a new neural network architecture "
            "based solely on attention mechanisms. Self-attention layers compute "
            "representations for machine translation."
        ],
    ))
    assert report.overall_faithfulness > 0.5
    assert report.overall_relevance > 0.5


def test_heuristic_low_overlap():
    """Heuristic scorer gives lower score with unrelated content."""
    scorer = FaithfulnessScorer(provider=None)
    report = asyncio.run(scorer.score_proposal(
        proposal_text="We study the mating habits of Antarctic penguins "
        "and their impact on ice sheet formation",
        proposal_title="Penguin Study",
        proposal_id="p2",
        source_texts=[
            "We introduce BERT for bidirectional transformer representations "
            "in natural language processing tasks."
        ],
    ))
    # Low overlap should give moderate scores (heuristic has floor)
    assert report.overall_faithfulness < 0.8


def test_heuristic_empty_sources():
    """Heuristic scorer handles empty sources gracefully."""
    scorer = FaithfulnessScorer(provider=None)
    report = asyncio.run(scorer.score_proposal(
        proposal_text="Some proposal text",
        proposal_id="p3",
        source_texts=[],
    ))
    assert report.overall_faithfulness == 0.5  # Default for no sources


def test_heuristic_empty_proposal():
    """Heuristic scorer handles empty proposal text."""
    scorer = FaithfulnessScorer(provider=None)
    report = asyncio.run(scorer.score_proposal(
        proposal_text="",
        proposal_id="p4",
        source_texts=["Some source text"],
    ))
    assert report.overall_faithfulness == 0.5  # Default for empty


# ── LLM Response Parsing Tests ─────────────────────────────────────────

def test_parse_valid_json_response():
    """Scorer correctly parses a valid LLM JSON response."""
    scorer = FaithfulnessScorer(provider=None)

    # Simulate parsing by calling _parse_response directly
    response = json.dumps({
        "faithfulness_score": 0.85,
        "relevance_score": 0.90,
        "grounding_score": 0.75,
        "reasoning": "Claims are well-supported by sources",
    })
    report = scorer._parse_response(response, "p1", "Test")
    assert report.overall_faithfulness == 0.85
    assert report.overall_relevance == 0.90
    assert report.overall_grounding == 0.75


def test_parse_json_with_markdown_fences():
    """Scorer strips markdown code fences before parsing."""
    scorer = FaithfulnessScorer(provider=None)

    response = '```json\n{"faithfulness_score": 0.7, "relevance_score": 0.8, "grounding_score": 0.6, "reasoning": "test"}\n```'
    report = scorer._parse_response(response, "p2", "Test")
    assert report.overall_faithfulness == 0.7


def test_parse_malformed_response():
    """Scorer handles malformed JSON gracefully."""
    scorer = FaithfulnessScorer(provider=None)

    response = "This is not JSON at all"
    report = scorer._parse_response(response, "p3", "Test")
    # Should default to 0.5
    assert report.overall_faithfulness == 0.5


# ── Claim Scoring Tests ────────────────────────────────────────────────

def test_claim_scoring_no_llm():
    """Claim scoring without LLM returns default scores."""
    scorer = FaithfulnessScorer(provider=None)
    assessment = asyncio.run(scorer.score_claim(
        claim="The model achieves 95% accuracy",
        source_text="Our experiments show 95% accuracy on the benchmark",
        source_id="paper-1",
    ))
    assert assessment.score == 0.5  # Default without LLM
    assert assessment.supported is True


def test_claim_response_parsing():
    """Claim scoring correctly parses LLM response."""
    scorer = FaithfulnessScorer(provider=None)
    response = json.dumps({
        "score": 0.9,
        "supported": True,
        "reasoning": "Exact match with experimental results",
    })
    assessment = scorer._parse_claim_response(response, "claim text", "p1")
    assert assessment.score == 0.9
    assert assessment.supported is True
