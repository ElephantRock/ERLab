"""Tests for the durable RunService.

These tests verify:
1. UUID-based run ID generation with no collision
2. Event append produces monotonic sequences
3. SSE replay via get_events_since works correctly
4. Cancellation is durable and idempotent
5. Worker lease uses compare-and-set (only one owner)
6. Stale worker becomes orphaned
7. Orphaned run can be re-acquired

All tests use an in-memory SQLite database for isolation.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.api.run_service import (
    WORKER_STALE_THRESHOLD_SECONDS,
    RunService,
)
from backend.db.database import Base
from backend.db.models import (
    RunWorker,
)


@pytest.fixture
def run_service(tmp_path):
    """Create a RunService backed by a fresh in-memory database."""
    # Create an in-memory SQLite engine for each test
    engine = create_engine("sqlite://", echo=False)
    Base.metadata.create_all(bind=engine)

    # Patch the session factory to use our test engine
    test_session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with patch("backend.api.run_service.get_session") as mock_get_session:
        from contextlib import contextmanager

        @contextmanager
        def test_session():
            session = test_session_factory()
            try:
                yield session
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        mock_get_session.side_effect = test_session

        service = RunService()
        yield service


class TestRunIdGeneration:
    """Run IDs are UUID-based, not timestamp-based."""

    def test_run_id_format(self, run_service):
        run_id = run_service.generate_run_id()
        assert run_id.startswith("run_")
        assert len(run_id) == 16  # "run_" + 12 hex chars

    def test_two_run_ids_are_different(self, run_service):
        id1 = run_service.generate_run_id()
        id2 = run_service.generate_run_id()
        assert id1 != id2


class TestCreateRun:
    """create_run inserts a PipelineRun record."""

    def test_create_returns_run_id(self, run_service):
        run_id = run_service.create_run(domain="AI/NLP", strategy="deep_research")
        assert run_id.startswith("run_")

    def test_create_run_status_is_pending(self, run_service):
        run_id = run_service.create_run(domain="AI/NLP")
        # Verify the run exists and is pending by acquiring a worker
        worker_id = run_service.acquire_worker(run_id)
        assert worker_id is not None


class TestEventOutbox:
    """Events are append-only with monotonic sequence."""

    def test_append_event_returns_sequence(self, run_service):
        run_id = run_service.create_run()
        seq1 = run_service.append_event(run_id, "stage_progress", {"stage": "search"})
        assert seq1 == 1

        seq2 = run_service.append_event(run_id, "stage_progress", {"stage": "generation"})
        assert seq2 == 2

    def test_events_ordered_by_sequence(self, run_service):
        run_id = run_service.create_run()
        run_service.append_event(run_id, "stage_progress", {"stage": "a"})
        run_service.append_event(run_id, "stage_progress", {"stage": "b"})
        run_service.append_event(run_id, "completed", {})

        events = run_service.get_events_since(run_id, last_seq=0)
        assert len(events) == 3
        assert events[0]["payload"]["stage"] == "a"
        assert events[1]["payload"]["stage"] == "b"
        assert events[2]["event_type"] == "completed"

    def test_replay_from_last_seq(self, run_service):
        """SSE reconnect replays only missed events."""
        run_id = run_service.create_run()
        run_service.append_event(run_id, "stage_progress", {"stage": "a"})
        run_service.append_event(run_id, "stage_progress", {"stage": "b"})
        run_service.append_event(run_id, "stage_progress", {"stage": "c"})

        # Client saw up to seq=1, reconnect from seq=1 → gets seq 2 and 3
        events = run_service.get_events_since(run_id, last_seq=1)
        assert len(events) == 2
        assert events[0]["payload"]["stage"] == "b"
        assert events[1]["payload"]["stage"] == "c"

        # Client saw up to seq=2, reconnect from seq=2 → gets seq 3 only
        events = run_service.get_events_since(run_id, last_seq=2)
        assert len(events) == 1
        assert events[0]["payload"]["stage"] == "c"

    def test_replay_from_zero_returns_all(self, run_service):
        run_id = run_service.create_run()
        run_service.append_event(run_id, "stage_progress", {"stage": "a"})
        run_service.append_event(run_id, "completed", {})

        events = run_service.get_events_since(run_id, last_seq=0)
        assert len(events) == 2

    def test_get_events_for_nonexistent_run(self, run_service):
        events = run_service.get_events_since("run_doesnotexist")
        assert events == []

    def test_get_latest_seq(self, run_service):
        run_id = run_service.create_run()
        assert run_service.get_latest_seq(run_id) == 0

        run_service.append_event(run_id, "stage_progress", {"stage": "a"})
        assert run_service.get_latest_seq(run_id) == 1

        run_service.append_event(run_id, "completed", {})
        assert run_service.get_latest_seq(run_id) == 2


class TestCancellation:
    """Cancellation is durable and idempotent."""

    def test_request_cancellation(self, run_service):
        run_id = run_service.create_run()
        assert run_service.is_cancelled(run_id) is False

        result = run_service.request_cancellation(run_id, reason="user requested")
        assert result is True
        assert run_service.is_cancelled(run_id) is True

    def test_cancellation_is_idempotent(self, run_service):
        run_id = run_service.create_run()
        run_service.request_cancellation(run_id)

        # Second request returns False (already cancelled)
        result = run_service.request_cancellation(run_id)
        assert result is False

    def test_cancellation_appends_event(self, run_service):
        run_id = run_service.create_run()
        run_service.append_event(run_id, "stage_progress", {"stage": "a"})
        run_service.request_cancellation(run_id, reason="testing")

        events = run_service.get_events_since(run_id, last_seq=0)
        cancelled_events = [e for e in events if e["event_type"] == "cancelled"]
        assert len(cancelled_events) == 1
        assert cancelled_events[0]["payload"]["reason"] == "testing"

    def test_cancel_nonexistent_run_returns_false(self, run_service):
        result = run_service.request_cancellation("run_nonexistent")
        assert result is False


class TestWorkerLease:
    """Worker lease uses compare-and-set ownership."""

    def test_acquire_worker_succeeds(self, run_service):
        run_id = run_service.create_run()
        worker_id = run_service.acquire_worker(run_id, worker_id="w1")
        assert worker_id == "w1"

    def test_second_acquire_fails(self, run_service):
        """Only one worker can own a run."""
        run_id = run_service.create_run()
        run_service.acquire_worker(run_id, worker_id="w1")

        with pytest.raises(RuntimeError, match="already has active worker"):
            run_service.acquire_worker(run_id, worker_id="w2")

    def test_get_active_worker(self, run_service):
        run_id = run_service.create_run()
        run_service.acquire_worker(run_id, worker_id="w1")

        assert run_service.get_active_worker(run_id) == "w1"

    def test_release_worker(self, run_service):
        run_id = run_service.create_run()
        run_service.acquire_worker(run_id, worker_id="w1")

        run_service.release_worker(run_id, "w1", status="completed")
        assert run_service.get_active_worker(run_id) is None

    def test_release_then_reacquire(self, run_service):
        """After release, a new worker can acquire the run."""
        run_id = run_service.create_run()
        run_service.acquire_worker(run_id, worker_id="w1")
        run_service.release_worker(run_id, "w1", status="completed")

        # New worker can acquire
        worker2 = run_service.acquire_worker(run_id, worker_id="w2")
        assert worker2 == "w2"

    def test_heartbeat_refreshes(self, run_service):
        run_id = run_service.create_run()
        run_service.acquire_worker(run_id, worker_id="w1")

        result = run_service.heartbeat(run_id, "w1")
        assert result is True

    def test_heartbeat_for_wrong_worker_fails(self, run_service):
        run_id = run_service.create_run()
        run_service.acquire_worker(run_id, worker_id="w1")

        result = run_service.heartbeat(run_id, "w2")
        assert result is False


class TestOrphanDetection:
    """Stale workers become orphaned."""

    def test_detect_orphans_marks_stale_worker(self, run_service):
        run_id = run_service.create_run()
        run_service.acquire_worker(run_id, worker_id="w1")

        # Backdate the worker heartbeat past the real threshold
        from sqlalchemy import update as sa_update

        old_time = datetime.now(UTC) - timedelta(seconds=WORKER_STALE_THRESHOLD_SECONDS + 60)

        import backend.api.run_service as svc_mod
        mock_get_session = svc_mod.get_session

        with mock_get_session.side_effect() as session:
            session.execute(
                sa_update(RunWorker)
                .where(RunWorker.worker_id == "w1")
                .values(last_heartbeat=old_time)
            )
            session.commit()

        orphaned = run_service.detect_orphans(threshold_seconds=WORKER_STALE_THRESHOLD_SECONDS)
        assert run_id in orphaned
        assert run_service.get_active_worker(run_id) is None

    def test_orphaned_run_can_be_reacquired(self, run_service):
        """After orphan detection, a new worker can acquire the run."""
        run_id = run_service.create_run()
        run_service.acquire_worker(run_id, worker_id="w1")

        # Manually backdate the heartbeat to ensure it is stale
        from contextlib import contextmanager

        from sqlalchemy import update as sa_update

        old_time = datetime.now(UTC) - timedelta(seconds=WORKER_STALE_THRESHOLD_SECONDS + 60)

        # Access the patched session factory directly
        import backend.api.run_service as svc_mod
        mock_get_session = svc_mod.get_session

        @contextmanager
        def temp_session():
            session = mock_get_session.__wrapped__() if hasattr(mock_get_session, '__wrapped__') else None
            # Fall back to creating our own session
            # Use the same in-memory DB by finding the engine from the fixture
            # Actually simpler: use the patched context manager directly
            with mock_get_session.side_effect() as s:
                yield s

        # Backdate the worker heartbeat but keep status as active
        # so detect_orphans can find it
        with mock_get_session.side_effect() as session:
            session.execute(
                sa_update(RunWorker)
                .where(RunWorker.worker_id == "w1")
                .values(last_heartbeat=old_time)
            )
            session.commit()

        # Now detect_orphans should find it
        orphaned = run_service.detect_orphans(threshold_seconds=WORKER_STALE_THRESHOLD_SECONDS)
        assert run_id in orphaned

        # New worker can acquire
        worker2 = run_service.acquire_worker(run_id, worker_id="w2")
        assert worker2 == "w2"

    def test_no_orphans_when_all_fresh(self, run_service):
        run_id = run_service.create_run()
        run_service.acquire_worker(run_id, worker_id="w1")
        run_service.heartbeat(run_id, "w1")

        orphaned = run_service.detect_orphans(threshold_seconds=300)
        assert len(orphaned) == 0
