"""Execution lifecycle recorder for literature search (P0.2.2).

Owns the source-attempt lifecycle: creates ``SearchQueryExecution`` rows,
observes every outbound provider request via ``DatabaseAttemptObserver``,
validates transitions and outcome invariants, persists each transition in a
short transaction independent of corpus persistence, and treats terminal
rows as immutable.

Transaction policy (frozen):
    Each state transition uses its own short ``get_session()`` -> ``commit()``.
    This is deliberately separate from ``persist_search_results``' governed
    transaction so that failed, timed-out, and skipped attempts remain
    visible even when no candidates are persisted.

Replay policy (frozen):
    pending/running -> may continue or complete per recovery rules
    terminal -> immutable -> duplicate lifecycle call does not invoke the
    adapter again; timestamps, status, attempt_count, error_detail unchanged.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker

from backend.pipeline.literature.contracts import (
    TERMINAL_STATUSES,
    AttemptObserver,
    AttemptOutcome,
    VALID_TRANSITIONS,
    SourceSearchOutcome,
    validate_outcome,
)

logger = logging.getLogger(__name__)

# Maximum length for stored error_detail.
_MAX_ERROR_DETAIL_LEN = 500

# Regex patterns for sanitization (conservative -- strips, does not allowlist).
_CREDENTIAL_PAIR = re.compile(r"[a-zA-Z0-9._~%-]+:[a-zA-Z0-9._~%-]+@")
_QUERY_STRING = re.compile(r"\?[^\s'\"]*")
_AUTH_HEADER = re.compile(
    r"(?i)(authorization|bearer|api[_-]?key|token|secret)\s*[=:]\s*\S+",
)
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def sanitize_error_detail(raw: str | None) -> str | None:
    """Conservatively sanitize an error string for storage.

    Strips URL credentials, query strings, auth/token/api-key values, and
    control characters. Truncates to ``_MAX_ERROR_DETAIL_LEN``. Never stores
    ``repr(response)`` or a complete request URL -- the caller should pass an
    exception's ``str()``, not a response repr.
    """
    if not raw:
        return None
    s = str(raw)
    s = _CREDENTIAL_PAIR.sub("[creds]@", s)
    s = _QUERY_STRING.sub("[query]", s)
    s = _AUTH_HEADER.sub("[auth]", s)
    s = _CONTROL_CHARS.sub("", s)
    s = s.strip()
    if len(s) > _MAX_ERROR_DETAIL_LEN:
        s = s[: _MAX_ERROR_DETAIL_LEN - 3] + "..."
    return s if s else None


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Database-backed attempt observer ─────────────────────────────────


class DatabaseAttemptObserver:
    """Observes outbound requests and drives execution-row transitions.

    The first ``attempt_started()`` atomically claims the execution:
    ``UPDATE ... SET status='running', attempt_count=1, attempted_at=now
    WHERE id=:id AND status='pending'``. Only the invocation receiving
    ``rowcount == 1`` owns the execution. Subsequent callbacks increment
    ``attempt_count``.

    A concurrent invocation hitting a non-pending row aborts before any
    network request by raising ``ExecutionAlreadyClaimed``.
    """

    def __init__(self, execution_id: int, engine: Any):
        self._execution_id = execution_id
        self._engine = engine
        self._claimed = False
        self._attempt_count = 0

    @property
    def claimed(self) -> bool:
        return self._claimed

    @property
    def attempt_count(self) -> int:
        return self._attempt_count

    async def attempt_started(self) -> None:
        from backend.db.models import SearchQueryExecution

        _Session = sessionmaker(bind=self._engine, expire_on_commit=False)
        session = _Session()
        try:
            if not self._claimed:
                # Atomic claim: only pending -> running succeeds.
                result = session.execute(
                    update(SearchQueryExecution)
                    .where(
                        SearchQueryExecution.id == self._execution_id,
                        SearchQueryExecution.status == "pending",
                    )
                    .values(
                        status="running",
                        attempt_count=1,
                        attempted_at=_now(),
                    )
                )
                if result.rowcount != 1:
                    # Row is not pending -- another invocation claimed it,
                    # or it is already terminal/running.
                    current = session.execute(
                        select(SearchQueryExecution.status).where(
                            SearchQueryExecution.id == self._execution_id
                        )
                    ).scalar_one_or_none()
                    raise ExecutionAlreadyClaimed(
                        f"execution {self._execution_id} is "
                        f"{current!r}, cannot claim from pending"
                    )
                session.commit()
                self._claimed = True
                self._attempt_count = 1
            else:
                # Increment: running -> running, attempt_count += 1.
                session.execute(
                    update(SearchQueryExecution)
                    .where(SearchQueryExecution.id == self._execution_id)
                    .values(attempt_count=self._attempt_count + 1)
                )
                session.commit()
                self._attempt_count += 1
        except ExecutionAlreadyClaimed:
            raise
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


class ExecutionAlreadyClaimed(Exception):
    """Raised when a concurrent invocation cannot atomically claim a row."""


# ── Execution recorder ───────────────────────────────────────────────


class ExecutionRecorder:
    """Records the lifecycle of one query/source execution.

    Provides:
      - ``ensure_pending_executions``: create pending rows for intended sources
      - ``skip_unavailable``: transition pending -> skipped for sources
        with no active adapter
      - ``run_execution``: drive one adapter through its lifecycle via a
        ``DatabaseAttemptObserver``, persisting the terminal outcome
      - ``is_terminal``: check immutability for replay safety
    """

    def __init__(self, engine: Any):
        self._engine = engine

    def _session(self):
        return sessionmaker(bind=self._engine, expire_on_commit=False)()

    def ensure_pending_executions(
        self, search_query_id: int, intended_sources: list[str],
    ) -> dict[str, int]:
        """Create a ``pending`` execution row for each intended source.

        Idempotent: if a row already exists for ``(search_query_id, source)``
        (e.g. from a prior partial run), reuse it. Returns ``source -> id``.

        Pre-existing terminal rows are NOT reset (replay immutability).
        """
        from backend.db.models import SearchQueryExecution

        session = self._session()
        source_to_id: dict[str, int] = {}
        try:
            for source in intended_sources:
                existing = session.execute(
                    select(SearchQueryExecution).where(
                        SearchQueryExecution.search_query_id == search_query_id,
                        SearchQueryExecution.source == source,
                    )
                ).scalar_one_or_none()

                if existing is not None:
                    source_to_id[source] = existing.id
                else:
                    row = SearchQueryExecution(
                        search_query_id=search_query_id,
                        source=source,
                        status="pending",
                        attempt_count=0,
                        accounting_status="incomplete",
                    )
                    session.add(row)
                    session.flush()
                    source_to_id[source] = row.id
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        return source_to_id

    def skip_unavailable(
        self, execution_id: int, reason: str = "no active adapter",
    ) -> None:
        """Transition a pending execution to ``skipped``.

        Only valid from ``pending``. Raises ``ValueError`` if the row is not
        pending (another state requires investigation, not silent skip).
        """
        from backend.db.models import SearchQueryExecution

        self._transition(
            execution_id, "skipped",
            error_detail=sanitize_error_detail(reason),
            extra_values={"completed_at": _now()},
        )

    def is_terminal(self, execution_id: int) -> bool:
        """Check whether the execution is in a terminal (immutable) state."""
        from backend.db.models import SearchQueryExecution

        session = self._session()
        try:
            status = session.execute(
                select(SearchQueryExecution.status).where(
                    SearchQueryExecution.id == execution_id
                )
            ).scalar_one_or_none()
            return status in TERMINAL_STATUSES
        finally:
            session.close()

    def _get_state(self, execution_id: int) -> tuple[str, int, datetime | None]:
        """Return (status, attempt_count, attempted_at) for an execution."""
        from backend.db.models import SearchQueryExecution

        session = self._session()
        try:
            row = session.execute(
                select(
                    SearchQueryExecution.status,
                    SearchQueryExecution.attempt_count,
                    SearchQueryExecution.attempted_at,
                ).where(SearchQueryExecution.id == execution_id)
            ).one()
            return row[0], row[1], row[2]
        finally:
            session.close()

    def _transition(
        self, execution_id: int, to_status: str,
        *,
        error_detail: str | None = None,
        extra_values: dict | None = None,
    ) -> None:
        """Validate and apply a transition in a short transaction.

        Raises ``ValueError`` on invalid transition. Propagates (does NOT
        swallow) -- an invalid transition is a programming/state defect.
        """
        from backend.db.models import SearchQueryExecution

        current_status, _, _ = self._get_state(execution_id)
        allowed = VALID_TRANSITIONS.get(current_status, frozenset())
        if to_status not in allowed:
            raise ValueError(
                f"invalid transition: {current_status!r} -> {to_status!r} "
                f"(allowed: {sorted(allowed) or 'none — state is terminal'})"
            )

        session = self._session()
        try:
            values: dict[str, Any] = {}
            if error_detail is not None:
                values["error_detail"] = error_detail
            if extra_values:
                values.update(extra_values)
            values["status"] = to_status

            session.execute(
                update(SearchQueryExecution)
                .where(SearchQueryExecution.id == execution_id)
                .values(**values)
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    async def run_execution(
        self,
        execution_id: int,
        source_name: str,
        adapter: Any,
        query: str,
        *,
        timeout_seconds: float | None = None,
        **search_kwargs: Any,
    ) -> AttemptOutcome:
        """Drive one adapter through its full lifecycle.

        1. Check immutability -- if terminal, return the existing state
           without invoking the adapter.
        2. Create a ``DatabaseAttemptObserver`` for this execution.
        3. Call ``adapter.search(query, attempt_observer=observer, **kwargs)``.
        4. The outcome MUST be a ``SourceSearchOutcome`` (bare list -> raise).
        5. Validate invariants, cross-check attempt_count, persist terminal.

        On unexpected adapter exception:
          - Before first observer callback: pending -> failed (attempt_count=0)
          - After callbacks: running -> failed (observed attempt_count)
          - Exception propagates after persisting.

        On ``asyncio.TimeoutError`` from ``asyncio.wait_for``:
          - If no observer callback fired: pending -> failed (pre-attempt)
          - If callbacks fired: running -> timeout (observed attempt_count)

        On ``asyncio.CancelledError``: propagate; leave row ``running``.
        """
        import asyncio

        from backend.db.models import SearchQueryExecution

        # ── Replay: terminal rows are immutable ──
        status, ac, _ = self._get_state(execution_id)
        if status in TERMINAL_STATUSES:
            logger.debug(
                "execution %d is terminal (%s) — replay is a no-op",
                execution_id, status,
            )
            return AttemptOutcome(
                execution_id=execution_id, source=source_name,
                status=status, attempt_count=ac,
            )

        observer = DatabaseAttemptObserver(execution_id, self._engine)

        try:
            if timeout_seconds is not None:
                outcome = await asyncio.wait_for(
                    adapter.search(
                        query, attempt_observer=observer, **search_kwargs,
                    ),
                    timeout=timeout_seconds,
                )
            else:
                outcome = await adapter.search(
                    query, attempt_observer=observer, **search_kwargs,
                )
        except asyncio.CancelledError:
            # Propagate cancellation; leave the row running truthfully.
            raise
        except asyncio.TimeoutError:
            # asyncio.wait_for expired.
            _, obs_ac, attempted_at = self._get_state(execution_id)
            if attempted_at is None:
                # No observer callback fired before timeout — pre-attempt failure.
                self._transition(
                    execution_id, "failed",
                    error_detail=sanitize_error_detail(
                        f"recorder timeout ({timeout_seconds}s) before first attempt"
                    ),
                    extra_values={"completed_at": _now()},
                )
                return AttemptOutcome(
                    execution_id=execution_id, source=source_name,
                    status="failed", attempt_count=0,
                    error_detail=f"recorder timeout before first attempt",
                )
            else:
                self._transition(
                    execution_id, "timeout",
                    error_detail=sanitize_error_detail(
                        f"recorder timeout ({timeout_seconds}s) after {obs_ac} attempts"
                    ),
                    extra_values={"completed_at": _now()},
                )
                return AttemptOutcome(
                    execution_id=execution_id, source=source_name,
                    status="timeout", attempt_count=obs_ac,
                    error_detail=f"recorder timeout after {obs_ac} attempts",
                )
        except Exception as exc:
            # Unexpected adapter exception.
            _, obs_ac, attempted_at = self._get_state(execution_id)
            if attempted_at is None:
                # Pre-attempt failure: exception before any observer callback.
                self._transition(
                    execution_id, "failed",
                    error_detail=sanitize_error_detail(
                        f"{type(exc).__name__}: {exc}"
                    ),
                    extra_values={"completed_at": _now()},
                )
            else:
                self._transition(
                    execution_id, "failed",
                    error_detail=sanitize_error_detail(
                        f"{type(exc).__name__}: {exc}"
                    ),
                    extra_values={"completed_at": _now()},
                )
            # Propagate — this is a programming/adapter defect.
            raise

        # ── Strict return-type check ──
        if not isinstance(outcome, SourceSearchOutcome):
            # Bare list or other type on the governed path — instrumentation
            # error. Persist as failed, then raise TypeError.
            _, obs_ac, attempted_at = self._get_state(execution_id)
            if attempted_at is not None:
                self._transition(
                    execution_id, "failed",
                    error_detail=sanitize_error_detail(
                        f"adapter returned {type(outcome).__name__}, "
                        f"expected SourceSearchOutcome"
                    ),
                    extra_values={"completed_at": _now()},
                )
            raise TypeError(
                f"governed adapter {source_name!r} returned "
                f"{type(outcome).__name__}, expected SourceSearchOutcome. "
                f"All adapters must be migrated to the outcome contract."
            )

        # ── Validate outcome invariants ──
        _, obs_ac, attempted_at = self._get_state(execution_id)
        attempted_at_is_null = attempted_at is None
        validate_outcome(outcome, attempted_at_is_null=attempted_at_is_null)

        # ── Cross-check attempt_count ──
        # The observer's independently counted attempts should match the
        # adapter's reported count. A mismatch is an instrumentation defect.
        if outcome.attempt_count != obs_ac:
            raise ValueError(
                f"attempt_count mismatch for execution {execution_id}: "
                f"adapter reported {outcome.attempt_count}, "
                f"observer counted {obs_ac}"
            )

        # ── Persist terminal transition ──
        self._transition(
            execution_id, outcome.status,
            error_detail=sanitize_error_detail(outcome.error_detail)
            if outcome.status != "success" else None,
            extra_values={"completed_at": _now()},
        )

        return AttemptOutcome(
            execution_id=execution_id, source=source_name,
            status=outcome.status, attempt_count=outcome.attempt_count,
            results=list(outcome.results),
            error_detail=outcome.error_detail if outcome.status != "success" else None,
        )
