"""Tests for BATCH-RAG-05: Token Budget Guard."""

import pytest

from backend.pipeline.knowledge.token_budget import (
    DEFAULT_STAGE_BUDGETS,
    BudgetReport,
    ScoredChunk,
    TokenBudgetGuard,
    TokenCounter,
)

# ── TokenCounter Tests ─────────────────────────────────────────────────

def test_token_counter_counts_text():
    """TokenCounter returns positive count for non-empty text."""
    counter = TokenCounter()
    count = counter.count("Hello world, this is a test of token counting.")
    assert count > 0


def test_token_counter_empty_text():
    """TokenCounter returns 0 for empty text."""
    counter = TokenCounter()
    assert counter.count("") == 0


def test_token_counter_longer_text_more_tokens():
    """TokenCounter gives higher count for longer text."""
    counter = TokenCounter()
    short = counter.count("Short text")
    long = counter.count("This is a much longer piece of text that should have significantly more tokens than the short one.")
    assert long > short


def test_token_counter_messages():
    """TokenCounter counts tokens in chat messages."""
    counter = TokenCounter()
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the Transformer architecture?"},
    ]
    total = counter.count_messages(messages)
    assert total > 0


# ── ScoredChunk Tests ──────────────────────────────────────────────────

def test_scored_chunk():
    """ScoredChunk stores all fields."""
    chunk = ScoredChunk(text="Hello", score=0.9, source_id="p1")
    assert chunk.text == "Hello"
    assert chunk.score == 0.9


# ── BudgetReport Tests ─────────────────────────────────────────────────

def test_budget_report_savings():
    """BudgetReport computes savings percentage."""
    report = BudgetReport(
        original_tokens=10000,
        trimmed_tokens=4000,
        budget=4000,
        dropped=5,
    )
    assert report.savings_pct == pytest.approx(0.6)


def test_budget_report_zero_original():
    """BudgetReport handles zero original tokens."""
    report = BudgetReport()
    assert report.savings_pct == 0.0


# ── TokenBudgetGuard Tests ─────────────────────────────────────────────

def test_trim_no_trimming_needed():
    """Guard returns all chunks when within budget."""
    guard = TokenBudgetGuard(budget=1000)
    chunks = [
        ScoredChunk(text="Short text", score=0.9),
        ScoredChunk(text="Another short", score=0.8),
    ]
    kept, report = guard.trim(chunks)
    assert len(kept) == 2
    assert report.dropped == 0


def test_trim_drops_low_score():
    """Guard drops lowest-scoring chunks when over budget."""
    counter = TokenCounter()
    # Use longer texts to generate meaningful token counts
    long_text_a = "The transformer architecture revolutionized natural language processing by introducing self-attention mechanisms that allow models to weigh the importance of different parts of the input sequence. " * 3
    long_text_b = "BERT introduced bidirectional pre-training for language representations, achieving state-of-the-art results on many NLP benchmarks. The model processes text in both directions simultaneously. " * 3
    long_text_c = "GPT-3 demonstrated that scaling language models to billions of parameters enables few-shot learning without task-specific fine-tuning, showing emergent capabilities. " * 5
    t_a = counter.count(long_text_a)
    t_b = counter.count(long_text_b)
    t_c = counter.count(long_text_c)
    budget = t_a + t_b  # Only fits first two
    guard = TokenBudgetGuard(budget=budget, counter=counter)
    chunks = [
        ScoredChunk(text=long_text_a, score=0.9),
        ScoredChunk(text=long_text_b, score=0.8),
        ScoredChunk(text=long_text_c, score=0.3),
    ]
    kept, report = guard.trim(chunks)
    assert len(kept) < 3
    assert report.dropped > 0


def test_trim_empty_input():
    """Guard handles empty input gracefully."""
    guard = TokenBudgetGuard(budget=1000)
    kept, report = guard.trim([])
    assert len(kept) == 0
    assert report.original_chunks == 0


def test_trim_preserves_high_scores():
    """Guard keeps highest-scoring chunks when budget forces drops."""
    counter = TokenCounter()
    # All same length text, budget fits 2 of 3
    text = "The quick brown fox jumps over the lazy dog. " * 20  # ~160 tokens each
    t = counter.count(text)
    budget = t * 2 + 1  # Fits exactly 2
    guard = TokenBudgetGuard(budget=budget, counter=counter)
    chunks = [
        ScoredChunk(text=text, score=0.1),   # Low score → dropped
        ScoredChunk(text=text, score=0.95),   # High score → kept
        ScoredChunk(text=text, score=0.5),    # Mid score → kept
    ]
    kept, report = guard.trim(chunks)
    assert len(kept) == 2
    kept_scores = sorted([c.score for c in kept], reverse=True)
    assert 0.95 in kept_scores
    assert 0.1 not in kept_scores  # Lowest score dropped


def test_trim_texts_convenience():
    """trim_texts works with plain string lists."""
    guard = TokenBudgetGuard(budget=1000)
    texts = ["First text", "Second text", "Third text"]
    kept, report = guard.trim_texts(texts)
    assert len(kept) == 3
    assert report.dropped == 0


def test_trim_texts_with_scores():
    """trim_texts respects scores for ordering."""
    guard = TokenBudgetGuard(budget=20)
    texts = ["A" * 200, "B" * 20, "C" * 200]
    scores = [0.9, 0.5, 0.1]
    kept, report = guard.trim_texts(texts, scores)
    assert len(kept) <= 3


def test_trim_for_stage():
    """trim_for_stage uses stage-specific budget."""
    guard = TokenBudgetGuard()
    texts = ["Short text"] * 50  # 50 chunks
    kept, report = guard.trim_for_stage(texts, "gap_analysis")
    assert report.stage == "gap_analysis"
    assert report.budget == DEFAULT_STAGE_BUDGETS["gap_analysis"]


def test_trim_for_stage_override():
    """trim_for_stage accepts override budget."""
    guard = TokenBudgetGuard()
    texts = ["Text"] * 10
    kept, report = guard.trim_for_stage(texts, "gap_analysis", override_budget=500)
    assert report.budget == 500


def test_default_stage_budgets():
    """DEFAULT_STAGE_BUDGETS covers key stages."""
    assert "gap_analysis" in DEFAULT_STAGE_BUDGETS
    assert "proposal_synthesis" in DEFAULT_STAGE_BUDGETS
    assert "idea_generation" in DEFAULT_STAGE_BUDGETS
    # Synthesis gets the largest budget
    assert DEFAULT_STAGE_BUDGETS["proposal_synthesis"] >= DEFAULT_STAGE_BUDGETS["gap_analysis"]
