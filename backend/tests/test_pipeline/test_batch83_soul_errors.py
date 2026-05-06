"""Tests for BATCH-83 — SOUL.md + Error Knowledge Store.

TASK-01: SOUL.md + SoulLoader (5 tests)
TASK-02: ErrorKnowledgeStore (5 tests)

AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

import os
import tempfile
import pytest

from backend.pipeline.soul_loader import load_soul, inject_soul, clear_cache
from backend.pipeline.knowledge.error_store import ErrorKnowledgeStore, FailureEntry


# ══════════════════════════════════════════════════════════
# TASK-01: SOUL.md + SoulLoader
# ══════════════════════════════════════════════════════════

def test_83_01_01_soul_md_exists():
    """SOUL.md exists in project root."""
    from pathlib import Path
    soul_path = Path("C:/Next-Era/elephant-rock-platform/SOUL.md")
    assert soul_path.exists()


def test_83_01_02_soul_md_is_human_readable():
    """SOUL.md is markdown, not code."""
    clear_cache()
    soul = load_soul()
    assert len(soul) > 100
    assert "##" in soul  # Markdown headers
    assert "def " not in soul  # No code
    assert "import " not in soul  # No imports


def test_83_01_03_inject_soul_prepends():
    """inject_soul() prepends philosophy to system prompt."""
    clear_cache()
    result = inject_soul("You are a helpful assistant.")
    assert "Research Philosophy" in result
    assert "helpful assistant" in result


def test_83_01_04_inject_soul_no_soul_returns_original():
    """When SOUL.md is empty, returns original prompt."""
    # Clear cache and set to empty
    import backend.pipeline.soul_loader as sl
    sl._SOUL_CACHE = ""
    result = inject_soul("Test prompt")
    assert result == "Test prompt"
    sl._SOUL_CACHE = None  # Reset


def test_83_01_05_soul_contains_key_values():
    """SOUL.md contains our core research values."""
    clear_cache()
    soul = load_soul()
    assert "Honesty" in soul or "honesty" in soul
    assert "Rigor" in soul or "rigor" in soul
    assert "Novel" in soul or "novel" in soul


# ══════════════════════════════════════════════════════════
# TASK-02: ErrorKnowledgeStore
# ══════════════════════════════════════════════════════════

@pytest.fixture
def tmp_error_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_errors.db")
        store = ErrorKnowledgeStore(db_path=db_path)
        yield store
        store.close()


def test_83_02_01_record_failure(tmp_error_store):
    """Recording a failure returns a row ID."""
    entry = FailureEntry(
        stage="synthesis",
        input_hash=ErrorKnowledgeStore.hash_input("test input"),
        reason="Proposal too short (< 500 chars)",
        suggestion="Generate longer proposals with more detail",
    )
    row_id = tmp_error_store.record(entry)
    assert row_id > 0


def test_83_02_02_query_by_stage(tmp_error_store):
    """Query by stage returns matching failures."""
    tmp_error_store.record(FailureEntry(
        stage="synthesis", input_hash="abc", reason="Too short"))
    tmp_error_store.record(FailureEntry(
        stage="gap_analysis", input_hash="def", reason="Gaps too generic"))
    synth_failures = tmp_error_store.query(stage="synthesis")
    assert len(synth_failures) == 1
    assert synth_failures[0]["stage"] == "synthesis"


def test_83_02_03_count(tmp_error_store):
    """Count returns correct failure count."""
    tmp_error_store.record(FailureEntry(stage="test", input_hash="a", reason="r1"))
    tmp_error_store.record(FailureEntry(stage="test", input_hash="b", reason="r2"))
    assert tmp_error_store.count() == 2
    assert tmp_error_store.count(stage="test") == 2


def test_83_02_04_hash_input_deterministic():
    """hash_input produces consistent hashes."""
    h1 = ErrorKnowledgeStore.hash_input("test input")
    h2 = ErrorKnowledgeStore.hash_input("test input")
    assert h1 == h2
    assert len(h1) == 16


def test_83_02_05_append_only_no_delete(tmp_error_store):
    """No delete method exists (HB-02)."""
    assert not hasattr(tmp_error_store, "delete")
    assert not hasattr(tmp_error_store, "remove")
