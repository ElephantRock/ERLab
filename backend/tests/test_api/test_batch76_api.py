"""Tests for BATCH-76/TASK-03 — API + Frontend Strategy Selection.

AIV v5.3 Test Integrity Protocol:
  - T1, T2, T5 apply
  - TASK-03 is High priority — T6 falsification applies
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.api.schemas import PipelineRunRequest


# ── TEST-76-03-01: POST accepts strategy field ──────────
# AC-03-01

def test_76_03_01_pipeline_run_request_accepts_strategy():
    """PipelineRunRequest accepts strategy field with valid value."""
    req = PipelineRunRequest(strategy="fast_scan")
    assert req.strategy == "fast_scan"


# ── TEST-76-03-02: Default strategy is deep_research ────
# AC-03-02

def test_76_03_02_default_strategy_is_deep_research():
    """PipelineRunRequest defaults strategy to deep_research."""
    req = PipelineRunRequest()
    assert req.strategy == "deep_research"


def test_76_03_02b_strategy_in_payload():
    """Strategy field appears in model dump."""
    req = PipelineRunRequest(strategy="academic_proposal")
    data = req.model_dump()
    assert "strategy" in data
    assert data["strategy"] == "academic_proposal"


# ── TEST-76-03-03: Response includes strategy ───────────
# AC-03-04 (schema level)

def test_76_03_03_strategy_in_all_valid_options():
    """All 4 valid strategy values are accepted."""
    for strategy in ["fast_scan", "deep_research", "academic_proposal", "literature_review"]:
        req = PipelineRunRequest(strategy=strategy)
        assert req.strategy == strategy


# ── TEST-76-03-04: Invalid strategy returns validation error
# Error path — AC-03-03

def test_76_03_04_invalid_strategy_returns_validation_error():
    """Invalid strategy string raises ValidationError."""
    with pytest.raises(ValidationError):
        PipelineRunRequest(strategy="nonexistent")


def test_76_03_04b_empty_strategy_returns_validation_error():
    """Empty string strategy raises ValidationError."""
    with pytest.raises(ValidationError):
        PipelineRunRequest(strategy="")


def test_76_03_04c_hack_strategy_returns_validation_error():
    """'hack' strategy raises ValidationError."""
    with pytest.raises(ValidationError):
        PipelineRunRequest(strategy="hack")


# ── TEST-76-03-05: Strategy regex validation ────────────
# AC-03-03

def test_76_03_05_strategy_field_pattern():
    """Strategy field only accepts the 4 valid values."""
    # Valid
    for s in ["fast_scan", "deep_research", "academic_proposal", "literature_review"]:
        req = PipelineRunRequest(strategy=s)
        assert req.strategy == s

    # Invalid
    for bad in ["FAST_SCAN", "deep-research", "academic", "lit_review", "deep_research "]:
        with pytest.raises(ValidationError):
            PipelineRunRequest(strategy=bad)
