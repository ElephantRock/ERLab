"""Tests for BATCH-92 — Concurrency Safety Flags.

AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

import pytest

from backend.pipeline.concurrency import (
    ConcurrencyManager, ConcurrencySafety, StageConcurrency,
    DEFAULT_STAGE_CONCURRENCY,
)


def test_92_01_default_is_exclusive():
    """Default safety is EXCLUSIVE (HB-01)."""
    stage = StageConcurrency(stage_name="test")
    assert stage.safety == ConcurrencySafety.EXCLUSIVE
    assert stage.is_exclusive is True


def test_92_01_exclusive_cannot_run_concurrent():
    """Exclusive stages cannot run with anything."""
    mgr = ConcurrencyManager()
    mgr.register(StageConcurrency("a", ConcurrencySafety.EXCLUSIVE))
    mgr.register(StageConcurrency("b", ConcurrencySafety.SAFE_TO_PARALLEL))
    assert mgr.can_run_concurrent("a", "b") is False


def test_92_01_safe_stages_can_run_concurrent():
    """Two SAFE stages can run concurrently."""
    mgr = ConcurrencyManager()
    mgr.register(StageConcurrency("a", ConcurrencySafety.SAFE_TO_PARALLEL))
    mgr.register(StageConcurrency("b", ConcurrencySafety.SAFE_TO_PARALLEL))
    assert mgr.can_run_concurrent("a", "b") is True


def test_92_02_same_resource_group_blocks():
    """Same resource_group blocks concurrent execution."""
    mgr = ConcurrencyManager()
    mgr.register(StageConcurrency("a", ConcurrencySafety.SAFE_TO_PARALLEL, resource_group="llm"))
    mgr.register(StageConcurrency("b", ConcurrencySafety.SAFE_TO_PARALLEL, resource_group="llm"))
    assert mgr.can_run_concurrent("a", "b") is False


def test_92_02_unknown_stage_treated_as_exclusive():
    """Unknown stages are treated as exclusive (HB-01)."""
    mgr = ConcurrencyManager()
    assert mgr.can_run_concurrent("unknown_a", "unknown_b") is False


def test_92_03_resolve_groups_creates_waves():
    """resolve_groups creates sequential waves."""
    mgr = ConcurrencyManager()
    mgr.register(StageConcurrency("search", ConcurrencySafety.SAFE_TO_PARALLEL, resource_group="network"))
    mgr.register(StageConcurrency("ingest", ConcurrencySafety.SAFE_TO_PARALLEL, resource_group="network"))
    mgr.register(StageConcurrency("analyze", ConcurrencySafety.EXCLUSIVE, resource_group="llm"))

    waves = mgr.resolve_groups(["search", "ingest", "analyze"])
    assert len(waves) >= 2
    # search and ingest share resource_group, so they're in separate waves
    # analyze is exclusive, so it's alone


def test_92_03_empty_stages_returns_empty():
    """Empty stages list returns empty waves."""
    mgr = ConcurrencyManager()
    assert mgr.resolve_groups([]) == []


def test_92_04_default_concurrency_declared():
    """All 9 pipeline stages have default concurrency declarations."""
    assert len(DEFAULT_STAGE_CONCURRENCY) == 9
    expected = ["literature_search", "ingestion", "gap_analysis", "idea_generation",
                "novelty_checking", "feasibility_scoring", "mechanical_metrics",
                "proposal_synthesis", "export"]
    for stage in expected:
        assert stage in DEFAULT_STAGE_CONCURRENCY
