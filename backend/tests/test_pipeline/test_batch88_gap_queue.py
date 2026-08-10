"""Tests for BATCH-88 — Gap Queue.

AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

import os
import tempfile

import pytest

from backend.pipeline.knowledge.gap_queue import GapPriority, GapQueue, QueuedGap


@pytest.fixture
def tmp_queue():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_gap_queue.db")
        queue = GapQueue(db_path=db_path)
        yield queue
        queue.close()


def _make_gap(gap_id="gap-1", title="Test Gap", domain="AI", priority=GapPriority.HIGH):
    return QueuedGap(
        gap_id=gap_id,
        title=title,
        description="A test gap description",
        domain=domain,
        priority=priority,
    )


def test_88_01_enqueue_and_count(tmp_queue):
    """Can enqueue a gap and count it."""
    assert tmp_queue.enqueue(_make_gap()) is True
    assert tmp_queue.count() == 1


def test_88_01_duplicate_enqueue_ignored(tmp_queue):
    """Duplicate gap_id is silently ignored."""
    tmp_queue.enqueue(_make_gap("gap-1"))
    result = tmp_queue.enqueue(_make_gap("gap-1"))
    # INSERT OR IGNORE succeeds but doesn't add a duplicate
    assert tmp_queue.count() == 1


def test_88_02_dequeue_returns_uninvestigated(tmp_queue):
    """dequeue returns only uninvestigated gaps."""
    tmp_queue.enqueue(_make_gap("gap-1"))
    tmp_queue.enqueue(_make_gap("gap-2"))
    gaps = tmp_queue.dequeue(limit=10)
    assert len(gaps) == 2
    assert all(not g.investigated for g in gaps)


def test_88_02_dequeue_by_domain(tmp_queue):
    """dequeue filters by domain."""
    tmp_queue.enqueue(_make_gap("gap-1", domain="AI"))
    tmp_queue.enqueue(_make_gap("gap-2", domain="Biology"))
    gaps = tmp_queue.dequeue(limit=10, domain="AI")
    assert len(gaps) == 1
    assert gaps[0].domain == "AI"


def test_88_02_priority_ordering(tmp_queue):
    """High priority gaps come first."""
    tmp_queue.enqueue(_make_gap("gap-low", priority=GapPriority.LOW))
    tmp_queue.enqueue(_make_gap("gap-high", priority=GapPriority.HIGH))
    gaps = tmp_queue.dequeue()
    assert gaps[0].priority == GapPriority.HIGH


def test_88_03_mark_investigated(tmp_queue):
    """Can mark a gap as investigated."""
    tmp_queue.enqueue(_make_gap("gap-1"))
    assert tmp_queue.mark_investigated("gap-1") is True
    assert tmp_queue.count(investigated=True) == 1
    assert tmp_queue.count(investigated=False) == 0


def test_88_03_investigated_not_in_dequeue(tmp_queue):
    """Investigated gaps don't appear in dequeue."""
    tmp_queue.enqueue(_make_gap("gap-1"))
    tmp_queue.mark_investigated("gap-1")
    gaps = tmp_queue.dequeue()
    assert len(gaps) == 0
