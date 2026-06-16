"""Durable Run Service — replaces process-local globals with DB-backed state.

This service is the single owner of:
- Run ID generation (UUID-based, collision-protected)
- Event append (append-only outbox for SSE/WS replay)
- Cancellation requests (durable, survives restart)
- Worker lease (compare-and-set ownership, heartbeat, orphan detection)

Design principles:
1. No module-level mutable state. All state lives in the database.
2. Run IDs are UUID-based with a uniqueness constraint.
3. Events are append-only with a per-run monotonic sequence.
4. Worker ownership uses compare-and-set: only one worker can acquire a run.
5. Stale heartbeat (>threshold) marks a worker orphaned.
6. SSE/WS replay reads from the event outbox using Last-Event-ID.

Usage::

    service = RunService()

    # Start a run
    run_id = await service.create_run(domain="AI/NLP", strategy="deep_research")

    # Acquire worker lease
    worker = await service.acquire_worker(run_id)

    # Append progress events
    await service.append_event(run_id, "stage_progress", {"stage": "generation", ...})

    # Request cancellation
    await service.request_cancellation(run_id, reason="user requested")

    # Check cancellation
    cancelled = await service.is_cancelled(run_id)

    # SSE replay from last event
    events = await service.get_events_since(run_id, last_seq=42)
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update, func, desc
from sqlalchemy.orm import Session

from backend.db.database import get_session
from backend.db.models import (
    PipelineRun,
    RunCancellation,
    RunEvent,
    RunWorker,
)

logger = logging.getLogger(__name__)

# Heartbeat timeout: if a worker hasn't sent a heartbeat in this long,
# it's considered orphaned (crashed, OOM-killed, etc.).
WORKER_STALE_THRESHOLD_SECONDS = 120  # 2 minutes


class RunService:
    """Durable run state service backed by the database.

    All methods are synchronous (DB calls are fast for SQLite/PostgreSQL).
    The service does not hold any mutable module-level state — all state
    is queried from and written to the database.
    """

    # ── Run ID Generation ───────────────────────────────────────

    def generate_run_id(self) -> str:
        """Generate a unique run ID.

        Uses UUID hex for practically negligible collision risk.
        The DB uniqueness constraint provides the final safety net.
        """
        return f"run_{uuid.uuid4().hex[:12]}"

    def create_run(
        self,
        domain: str = "AI/NLP",
        strategy: str = "deep_research",
        session_id: str | None = None,
        config: dict | None = None,
    ) -> str:
        """Create a new pipeline run record and return the run_id string.

        The run starts in 'pending' status. A worker must acquire it
        via ``acquire_worker`` before execution begins.
        """
        run_id_str = self.generate_run_id()

        with get_session() as session:
            run = PipelineRun(
                run_id_str=run_id_str,
                status="pending",
                domain=domain,
                config_json=json.dumps(config or {}),
                session_id=session_id,
            )
            session.add(run)
            session.flush()  # Get the PK
            db_id = run.id
            session.commit()

        logger.info("Created run %s (db_id=%d, domain=%s)", run_id_str, db_id, domain)
        return run_id_str

    # ── Event Outbox ────────────────────────────────────────────

    def append_event(
        self,
        run_id_str: str,
        event_type: str,
        payload: dict | None = None,
    ) -> int:
        """Append an event to the run's event outbox.

        Returns the sequence number of the appended event.

        The sequence is per-run monotonic. SSE clients use
        ``Last-Event-ID`` to resume from a specific sequence.
        """
        with get_session() as session:
            # Find the DB run
            run = self._get_run_by_str(session, run_id_str)
            if run is None:
                raise ValueError(f"Run '{run_id_str}' not found")

            # Get next sequence number
            max_seq = session.scalar(
                select(func.max(RunEvent.seq))
                .where(RunEvent.run_id == run.id)
            ) or 0

            event = RunEvent(
                run_id=run.id,
                seq=max_seq + 1,
                event_type=event_type,
                payload=json.dumps(payload) if payload else None,
            )
            session.add(event)
            session.commit()

            return event.seq

    def get_events_since(
        self,
        run_id_str: str,
        last_seq: int = 0,
    ) -> list[dict]:
        """Get events after the given sequence number.

        Used for SSE replay with ``Last-Event-ID``.
        Returns events ordered by sequence ascending.
        """
        with get_session() as session:
            run = self._get_run_by_str(session, run_id_str)
            if run is None:
                return []

            stmt = (
                select(RunEvent)
                .where(RunEvent.run_id == run.id, RunEvent.seq > last_seq)
                .order_by(RunEvent.seq)
            )
            events = session.execute(stmt).scalars().all()

            return [
                {
                    "seq": e.seq,
                    "event_type": e.event_type,
                    "payload": json.loads(e.payload) if e.payload else None,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in events
            ]

    def get_latest_seq(self, run_id_str: str) -> int:
        """Get the latest event sequence number for a run."""
        with get_session() as session:
            run = self._get_run_by_str(session, run_id_str)
            if run is None:
                return 0
            return session.scalar(
                select(func.max(RunEvent.seq))
                .where(RunEvent.run_id == run.id)
            ) or 0

    # ── Cancellation ────────────────────────────────────────────

    def request_cancellation(
        self,
        run_id_str: str,
        reason: str = "user requested",
    ) -> bool:
        """Request cancellation of a run.

        This is durable — it survives process restart. The orchestrator
        checks ``is_cancelled`` periodically during stage execution.

        Returns True if the cancellation was recorded, False if the
        run was already cancelled.
        """
        with get_session() as session:
            run = self._get_run_by_str(session, run_id_str)
            if run is None:
                return False

            # Check if already cancelled
            existing = session.scalar(
                select(RunCancellation)
                .where(RunCancellation.run_id == run.id)
                .limit(1)
            )
            if existing:
                return False

            cancel = RunCancellation(
                run_id=run.id,
                run_id_str=run_id_str,
                reason=reason,
            )
            session.add(cancel)

            # Append cancellation event
            max_seq = session.scalar(
                select(func.max(RunEvent.seq))
                .where(RunEvent.run_id == run.id)
            ) or 0
            event = RunEvent(
                run_id=run.id,
                seq=max_seq + 1,
                event_type="cancelled",
                payload=json.dumps({"reason": reason}),
            )
            session.add(event)
            session.commit()

            logger.info("Cancellation requested for run %s: %s", run_id_str, reason)
            return True

    def is_cancelled(self, run_id_str: str) -> bool:
        """Check if a run has been cancelled."""
        with get_session() as session:
            run = self._get_run_by_str(session, run_id_str)
            if run is None:
                return False
            return session.scalar(
                select(func.count())
                .select_from(RunCancellation)
                .where(RunCancellation.run_id == run.id)
            ) > 0

    # ── Worker Lease ────────────────────────────────────────────

    def acquire_worker(
        self,
        run_id_str: str,
        worker_id: str | None = None,
    ) -> str:
        """Acquire a worker lease for a run.

        Uses compare-and-set: only succeeds if no active worker exists.
        Returns the worker_id of the new lease.

        Raises:
            RuntimeError: If another active worker already owns this run.
        """
        worker_id = worker_id or f"worker_{uuid.uuid4().hex[:8]}"

        with get_session() as session:
            run = self._get_run_by_str(session, run_id_str)
            if run is None:
                raise ValueError(f"Run '{run_id_str}' not found")

            # Check for existing active worker
            active = session.scalar(
                select(RunWorker)
                .where(
                    RunWorker.run_id == run.id,
                    RunWorker.status == "active",
                )
                .limit(1)
            )
            if active:
                raise RuntimeError(
                    f"Run '{run_id_str}' already has active worker '{active.worker_id}'"
                )

            worker = RunWorker(
                run_id=run.id,
                run_id_str=run_id_str,
                worker_id=worker_id,
                status="active",
            )
            session.add(worker)

            # Update run status to running
            run.status = "running"
            session.commit()

            logger.info("Worker '%s' acquired run '%s'", worker_id, run_id_str)
            return worker_id

    def heartbeat(self, run_id_str: str, worker_id: str) -> bool:
        """Refresh worker ownership.

        Returns True if the heartbeat was recorded, False if the
        worker no longer owns the run (e.g., was orphaned).
        """
        now = datetime.now(timezone.utc)
        with get_session() as session:
            result = session.execute(
                update(RunWorker)
                .where(
                    RunWorker.run_id_str == run_id_str,
                    RunWorker.worker_id == worker_id,
                    RunWorker.status == "active",
                )
                .values(last_heartbeat=now)
            )
            session.commit()
            return result.rowcount > 0

    def release_worker(
        self,
        run_id_str: str,
        worker_id: str,
        status: str = "completed",
    ) -> None:
        """Release worker ownership. Called when a run finishes."""
        now = datetime.now(timezone.utc)
        with get_session() as session:
            session.execute(
                update(RunWorker)
                .where(
                    RunWorker.run_id_str == run_id_str,
                    RunWorker.worker_id == worker_id,
                )
                .values(status=status, completed_at=now)
            )
            session.commit()

    def detect_orphans(
        self,
        threshold_seconds: int = WORKER_STALE_THRESHOLD_SECONDS,
    ) -> list[str]:
        """Find runs with stale workers and mark them orphaned.

        Returns list of run_id_str values that were orphaned.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=threshold_seconds)
        orphaned_ids: list[str] = []

        with get_session() as session:
            stale = session.execute(
                select(RunWorker)
                .where(
                    RunWorker.status == "active",
                    RunWorker.last_heartbeat < cutoff,
                )
            ).scalars().all()

            for worker in stale:
                worker.status = "orphaned"
                orphaned_ids.append(worker.run_id_str)

                # Mark run as failed if it was running
                run = session.get(PipelineRun, worker.run_id)
                if run and run.status == "running":
                    run.status = "failed"
                    run.error_message = f"Worker '{worker.worker_id}' became orphaned (heartbeat timeout)"

            session.commit()

        if orphaned_ids:
            logger.warning(
                "Detected %d orphaned workers: %s",
                len(orphaned_ids), orphaned_ids,
            )
        return orphaned_ids

    def get_active_worker(self, run_id_str: str) -> str | None:
        """Get the active worker_id for a run, if any."""
        with get_session() as session:
            worker = session.scalar(
                select(RunWorker)
                .where(
                    RunWorker.run_id_str == run_id_str,
                    RunWorker.status == "active",
                )
                .limit(1)
            )
            return worker.worker_id if worker else None

    # ── Internal ────────────────────────────────────────────────

    def _get_run_by_str(self, session: Session, run_id_str: str) -> PipelineRun | None:
        """Look up a PipelineRun by its run_id_str field."""
        return session.scalar(
            select(PipelineRun).where(PipelineRun.run_id_str == run_id_str)
        )


# ── Module-level singleton ────────────────────────────────────

_run_service: RunService | None = None


def get_run_service() -> RunService:
    """Get the global RunService singleton."""
    global _run_service
    if _run_service is None:
        _run_service = RunService()
    return _run_service


def reset_run_service() -> None:
    """Reset the singleton (for testing)."""
    global _run_service
    _run_service = None
