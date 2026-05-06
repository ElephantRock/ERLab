"""Tests for BATCH-105 — Budget/Time Controls + Domain Prompts.

AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

import time
import pytest

from backend.pipeline.budget_guard import BudgetGuard, BudgetConfig, BudgetAction
from backend.pipeline.prompts.domain_loader import load_domain_prompt, list_available_domains


# ══════════════════════════════════════════════════════════
# TASK-01: BudgetGuard
# ══════════════════════════════════════════════════════════

def test_105_01_no_limits_always_continue():
    """No limits set → always CONTINUE."""
    guard = BudgetGuard(BudgetConfig(max_time_s=0, max_cost_usd=0))
    guard.start()
    status = guard.check()
    assert status.action == BudgetAction.CONTINUE


def test_105_01_time_limit_triggers_stop():
    """Exceeding time limit triggers STOP."""
    guard = BudgetGuard(BudgetConfig(max_time_s=0.1))  # 100ms
    guard.start()
    time.sleep(0.15)
    status = guard.check()
    assert status.action == BudgetAction.STOP


def test_105_01_cost_limit_triggers_stop():
    """Exceeding cost limit triggers STOP."""
    guard = BudgetGuard(BudgetConfig(max_cost_usd=1.0))
    guard.start()
    guard.update_cost(1.5)
    status = guard.check()
    assert status.action == BudgetAction.STOP


def test_105_01_degrade_at_threshold():
    """Approaching limit triggers DEGRADE."""
    guard = BudgetGuard(BudgetConfig(max_time_s=1.0, degrade_threshold=0.5))
    guard.start()
    time.sleep(0.55)
    status = guard.check("novelty_checking")
    assert status.action == BudgetAction.DEGRADE
    assert status.should_skip_stage is True


def test_105_01_degrade_skips_optional_only():
    """DEGRADE only skips optional stages."""
    guard = BudgetGuard(BudgetConfig(max_time_s=1.0, degrade_threshold=0.5))
    guard.start()
    time.sleep(0.55)
    status = guard.check("gap_analysis")  # NOT optional
    assert status.action == BudgetAction.DEGRADE
    assert status.should_skip_stage is False


def test_105_01_not_started_returns_continue():
    """Guard not started returns CONTINUE."""
    guard = BudgetGuard(BudgetConfig(max_time_s=10))
    status = guard.check()
    assert status.action == BudgetAction.CONTINUE


# ══════════════════════════════════════════════════════════
# TASK-02: Domain Prompts
# ══════════════════════════════════════════════════════════

def test_105_02_load_cs_domain():
    """CS domain prompt loads successfully."""
    prompt = load_domain_prompt("machine learning")
    assert "NLP" in prompt or "Transformer" in prompt or "benchmark" in prompt


def test_105_02_load_bio_domain():
    """Biology domain prompt loads successfully."""
    prompt = load_domain_prompt("biomedical research")
    assert "Biology" in prompt or "clinical" in prompt or "model organisms" in prompt


def test_105_02_load_social_domain():
    """Social science domain prompt loads successfully."""
    prompt = load_domain_prompt("psychology")
    assert "Social" in prompt or "WEIRD" in prompt or "survey" in prompt


def test_105_02_unknown_domain_returns_empty():
    """Unknown domain returns empty string."""
    prompt = load_domain_prompt("cooking recipes")
    assert prompt == ""


def test_105_02_list_available_domains():
    """list_available_domains returns domain names."""
    domains = list_available_domains()
    assert len(domains) >= 3
    assert "computer_science" in domains
    assert "biology" in domains
    assert "social_science" in domains
