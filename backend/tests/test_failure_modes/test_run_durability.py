"""Phase 7: Run durability failure-mode tests.

Tests prove:
1. Worker crash → orphan detected by heartbeat timeout
2. Orphaned run can be resumed (new worker acquires lease)
3. Cancellation persists across service restart (new service instance)
4. SSE reconnect replays events from Last-Event-ID

Run: pytest backend/tests/test_failure_modes/test_run_durability.py -v
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.database import Base

# ── Test fixtures ───────────────────────────────────────────────


@pytest.fixture
def db_engine():
    """Create a fresh in-memory database for each test."""
    engine = create_engine("sqlite://", echo=False)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def run_service(db_engine):
    """Create a RunService backed by the test database."""
    test_session_factory = sessionmaker(bind=db_engine, expire_on_commit=False)

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

        from backend.api.run_service import RunService
        svc = RunService()
        yield svc


# ── 1. Worker crash → orphan detected ───────────────────────────


class TestWorkerCrashOrphanDetection:
    """Worker crash → stale heartbeat → orphan detected."""

    def test_stale_worker_marked_orphaned(self, run_service, db_engine):
        """A worker whose heartbeat expired is marked orphaned."""
        run_id = run_service.create_run(domain="AI/NLP")
        worker_id = run_service.acquire_worker(run_id)

        # Simulate crash: backdate the heartbeat far into the past
        with db_engine.connect() as conn:
            from sqlalchemy import text
            old_time = datetime.now(UTC) - timedelta(minutes=10)
            conn.execute(
                text("UPDATE run_workers SET last_heartbeat = :ts WHERE worker_id = :wid"),
                {"ts": old_time, "wid": worker_id},
            )
            conn.commit()

        orphaned = run_service.detect_orphans(threshold_seconds=60)
        assert run_id in orphaned

    def test_active_worker_not_orphaned(self, run_service):
        """Worker with recent heartbeat is NOT orphaned."""
        run_id = run_service.create_run(domain="AI/NLP")
        worker_id = run_service.acquire_worker(run_id)
        run_service.heartbeat(run_id, worker_id)

        orphaned = run_service.detect_orphans(threshold_seconds=120)
        assert run_id not in orphaned
        assert run_service.get_active_worker(run_id) == worker_id

    def test_orphaned_worker_releases_lease(self, run_service, db_engine):
        """After orphan detection, the run has no active worker."""
        run_id = run_service.create_run(domain="AI/NLP")
        worker_id = run_service.acquire_worker(run_id)

        # Crash simulation
        with db_engine.connect() as conn:
            from sqlalchemy import text
            old_time = datetime.now(UTC) - timedelta(minutes=10)
            conn.execute(
                text("UPDATE run_workers SET last_heartbeat = :ts WHERE worker_id = :wid"),
                {"ts": old_time, "wid": worker_id},
            )
            conn.commit()

        run_service.detect_orphans(threshold_seconds=60)
        assert run_service.get_active_worker(run_id) is None

    def test_orphaned_run_marked_failed(self, run_service, db_engine):
        """Orphaned run status changes to 'failed'."""
        run_id = run_service.create_run(domain="AI/NLP")
        run_service.acquire_worker(run_id)

        with db_engine.connect() as conn:
            from sqlalchemy import text
            old_time = datetime.now(UTC) - timedelta(minutes=10)
            conn.execute(
                text("UPDATE run_workers SET last_heartbeat = :ts WHERE run_id_str = :rid"),
                {"ts": old_time, "rid": run_id},
            )
            conn.commit()

        run_service.detect_orphans(threshold_seconds=60)

        # Verify run is marked failed
        events = run_service.get_events_since(run_id)
        # The run status should be 'failed'
        with db_engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(
                text("SELECT status, error_message FROM pipeline_runs WHERE run_id_str = :rid"),
                {"rid": run_id},
            ).fetchone()
            assert result[0] == "failed"
            assert "orphaned" in result[1].lower()


# ── 2. Orphaned run can be resumed ──────────────────────────────


class TestOrphanedRunResume:
    """Orphaned run can be re-acquired by a new worker."""

    def test_new_worker_acquires_orphaned_run(self, run_service, db_engine):
        run_id = run_service.create_run(domain="AI/NLP")
        old_worker = run_service.acquire_worker(run_id)

        # Crash the old worker
        with db_engine.connect() as conn:
            from sqlalchemy import text
            old_time = datetime.now(UTC) - timedelta(minutes=10)
            conn.execute(
                text("UPDATE run_workers SET last_heartbeat = :ts WHERE worker_id = :wid"),
                {"ts": old_time, "wid": old_worker},
            )
            conn.commit()

        run_service.detect_orphans(threshold_seconds=60)

        # New worker should be able to acquire
        new_worker = run_service.acquire_worker(run_id, worker_id="worker_recovery")
        assert new_worker == "worker_recovery"
        assert run_service.get_active_worker(run_id) == "worker_recovery"

    def test_heartbeat_from_new_worker(self, run_service, db_engine):
        """New worker can heartbeat after recovery."""
        run_id = run_service.create_run(domain="AI/NLP")
        old_worker = run_service.acquire_worker(run_id)

        with db_engine.connect() as conn:
            from sqlalchemy import text
            old_time = datetime.now(UTC) - timedelta(minutes=10)
            conn.execute(
                text("UPDATE run_workers SET last_heartbeat = :ts WHERE worker_id = :wid"),
                {"ts": old_time, "wid": old_worker},
            )
            conn.commit()

        run_service.detect_orphans(threshold_seconds=60)
        new_worker = run_service.acquire_worker(run_id)

        # Heartbeat should work
        assert run_service.heartbeat(run_id, new_worker) is True


# ── 3. Cancellation persists across restart ─────────────────────


class TestCancellationDurability:
    """Cancellation survives service restart."""

    def test_cancellation_visible_to_new_service_instance(self, run_service, db_engine):
        """A new RunService instance sees the cancellation from the old one."""
        run_id = run_service.create_run(domain="AI/NLP")
        assert run_service.request_cancellation(run_id, reason="user requested")
        assert run_service.is_cancelled(run_id)

        # Simulate restart: create a new service instance using same DB
        test_session_factory = sessionmaker(bind=db_engine, expire_on_commit=False)

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
            from backend.api.run_service import RunService
            new_svc = RunService()

            # The new instance must see the cancellation
            assert new_svc.is_cancelled(run_id)

    def test_double_cancellation_is_idempotent(self, run_service):
        """Requesting cancellation twice is safe — returns False on second."""
        run_id = run_service.create_run(domain="AI/NLP")
        assert run_service.request_cancellation(run_id) is True
        assert run_service.request_cancellation(run_id) is False

    def test_cancellation_emits_event(self, run_service):
        """Cancellation appends a 'cancelled' event to the outbox."""
        run_id = run_service.create_run(domain="AI/NLP")
        run_service.request_cancellation(run_id, reason="timeout")

        events = run_service.get_events_since(run_id)
        cancel_events = [e for e in events if e["event_type"] == "cancelled"]
        assert len(cancel_events) == 1
        assert cancel_events[0]["payload"]["reason"] == "timeout"


# ── 4. SSE reconnect replays events ──────────────────────────────


class TestSSEReplay:
    """SSE reconnect replays events from Last-Event-ID."""

    def test_replay_from_last_seq(self, run_service):
        """get_events_since returns only events after last_seq."""
        run_id = run_service.create_run(domain="AI/NLP")

        # Append 5 events
        for i in range(5):
            run_service.append_event(run_id, "progress", {"stage": f"stage_{i}"})

        # Replay from seq=2 → should get events 3, 4, 5
        replayed = run_service.get_events_since(run_id, last_seq=2)
        assert len(replayed) == 3
        assert [e["seq"] for e in replayed] == [3, 4, 5]

    def test_replay_from_zero_gets_all(self, run_service):
        run_id = run_service.create_run(domain="AI/NLP")
        run_service.append_event(run_id, "progress", {"s": 1})
        run_service.append_event(run_id, "progress", {"s": 2})

        all_events = run_service.get_events_since(run_id, last_seq=0)
        assert len(all_events) == 2

    def test_replay_with_no_events_returns_empty(self, run_service):
        run_id = run_service.create_run(domain="AI/NLP")
        events = run_service.get_events_since(run_id, last_seq=0)
        assert events == []

    def test_replay_preserves_order(self, run_service):
        """Events are returned in ascending sequence order."""
        run_id = run_service.create_run(domain="AI/NLP")
        for i in range(10):
            run_service.append_event(run_id, "test", {"index": i})

        events = run_service.get_events_since(run_id, last_seq=4)
        seqs = [e["seq"] for e in events]
        assert seqs == sorted(seqs)
        assert seqs == [5, 6, 7, 8, 9, 10]

    def test_latest_seq_tracks_append(self, run_service):
        run_id = run_service.create_run(domain="AI/NLP")
        assert run_service.get_latest_seq(run_id) == 0

        run_service.append_event(run_id, "progress", {})
        assert run_service.get_latest_seq(run_id) == 1

        run_service.append_event(run_id, "progress", {})
        assert run_service.get_latest_seq(run_id) == 2


# ── 5. Worker lease compare-and-set ─────────────────────────────


class TestWorkerLeaseCompareAndSet:
    """Worker lease uses compare-and-set: only one active owner."""

    def test_second_acquire_fails(self, run_service):
        run_id = run_service.create_run(domain="AI/NLP")
        w1 = run_service.acquire_worker(run_id, worker_id="w1")

        with pytest.raises(RuntimeError, match="already has active worker"):
            run_service.acquire_worker(run_id, worker_id="w2")

    def test_release_allows_reacquire(self, run_service):
        run_id = run_service.create_run(domain="AI/NLP")
        w1 = run_service.acquire_worker(run_id, worker_id="w1")
        run_service.release_worker(run_id, w1, status="completed")

        w2 = run_service.acquire_worker(run_id, worker_id="w2")
        assert w2 == "w2"

    def test_heartbeat_returns_false_for_wrong_worker(self, run_service):
        """Heartbeat from a worker that doesn't own the run returns False."""
        run_id = run_service.create_run(domain="AI/NLP")
        run_service.acquire_worker(run_id, worker_id="w1")

        assert run_service.heartbeat(run_id, "imposter") is False
