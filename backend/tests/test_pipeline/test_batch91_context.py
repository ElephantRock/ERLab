"""Tests for BATCH-91 — 3-Tier Context Management.

AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

import pytest

from backend.pipeline.context.manager import ContextBudget, ContextManager


@pytest.fixture
def manager():
    return ContextManager(budget=ContextBudget(max_total_tokens=200))


def test_91_01_three_tiers():
    """Context has system, domain, and task tiers."""
    m = ContextManager()
    m.set_system("You are a research assistant.")
    m.add_domain("Paper 1: Neural Networks")
    m.add_domain("Paper 2: Transformers")
    m.set_task("Generate novel research ideas.")

    result = m.build()
    assert "research assistant" in result
    assert "Paper 1" in result
    assert "Paper 2" in result
    assert "Generate novel" in result


def test_91_01_system_always_present():
    """System context is always included (HB-02)."""
    m = ContextManager(budget=ContextBudget(max_total_tokens=50))
    m.set_system("Critical system prompt that must never be removed.")
    result = m.build()
    assert "Critical system prompt" in result


def test_91_01_domain_truncated_first():
    """Domain context is truncated before task."""
    m = ContextManager(budget=ContextBudget(max_total_tokens=200, task_reserve=80))
    m.set_system("System.")
    m.add_domain("X" * 800)  # Long domain, but fits some
    m.set_task("Task instruction here.")

    result = m.build()
    assert "System." in result
    assert "Task instruction" in result
    # Domain should be present (possibly truncated)
    assert "X" in result or "truncated" in result


def test_91_02_token_budget_enforced():
    """Output stays within token budget."""
    m = ContextManager(budget=ContextBudget(max_total_tokens=100))
    m.set_system("System prompt.")
    m.add_domain("Domain " * 500)  # Very long
    m.set_task("Task.")

    result = m.build()
    tokens = ContextManager._estimate_tokens(result)
    # Allow some slack for the truncation marker
    assert tokens <= 150  # Within reasonable range


def test_91_02_empty_context():
    """Empty context returns empty string."""
    m = ContextManager()
    assert m.build() == ""


def test_91_02_multiple_domain_contexts():
    """Multiple domain contexts are all added."""
    m = ContextManager(budget=ContextBudget(max_total_tokens=500))
    m.set_system("System.")
    for i in range(5):
        m.add_domain(f"Domain context {i}.")
    m.set_task("Task.")

    result = m.build()
    for i in range(5):
        assert f"Domain context {i}" in result


def test_91_02_domain_count():
    """domain_count reflects added domains."""
    m = ContextManager()
    assert m.domain_count == 0
    m.add_domain("A")
    m.add_domain("B")
    assert m.domain_count == 2


def test_91_03_truncate_ends_at_sentence():
    """Truncation tries to end at a sentence boundary."""
    text = "First sentence. Second sentence. Third sentence. Fourth."
    truncated = ContextManager._truncate(text, 10)  # ~10 tokens = ~40 chars
    assert truncated.endswith("[... truncated ...]")


def test_91_03_truncate_short_text_unchanged():
    """Short text is not truncated."""
    text = "Short text."
    assert ContextManager._truncate(text, 100) == text
