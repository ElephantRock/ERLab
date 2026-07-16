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
    SourceQueryPlan,
    SourceSearchOutcome,
    validate_outcome,
)

logger = logging.getLogger(__name__)


class TranslationDriftError(Exception):
    """Raised when a pending execution's stored translation differs from the
    newly built plan. The previous translation is preserved as evidence."""


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
        from backend.pipeline.literature.run_reconciliation import (
            ensure_execution_scope,
        )

        # P0.2.6: Register the execution scope atomically.
        ensure_execution_scope(self._engine, search_query_id, intended_sources)

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
            extra_values={
                "completed_at": _now(),
                "failure_category": "source_unavailable",
                "failure_code": "no_active_adapter",
                "execution_metadata_version": "execution_v1",
            },
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

    def _get_translated_query(self, execution_id: int) -> str | None:
        """Return the stored translated_query for an execution."""
        from backend.db.models import SearchQueryExecution

        session = self._session()
        try:
            return session.execute(
                select(SearchQueryExecution.translated_query).where(
                    SearchQueryExecution.id == execution_id
                )
            ).scalar_one_or_none()
        finally:
            session.close()

    def _ensure_linkage_ledger(
        self, execution_id: int, terminal_values: dict[str, Any],
    ) -> None:
        """Create or preserve the linkage ledger row for an execution.

        Called after terminal accounting is persisted. Uses the same short
        transaction semantics.

        - Reconciled execution → status='pending', expected=source_unique_count
        - Incomplete execution → status='not_applicable', expected=NULL
        - Existing pending/not_applicable/linked → preserved (no overwrite)
        - Existing failed → preserved (eligible for retry)
        """
        from backend.db.models import ExecutionDiscoveryLinkage

        session = self._session()
        try:
            existing = session.execute(
                select(ExecutionDiscoveryLinkage).where(
                    ExecutionDiscoveryLinkage.execution_id == execution_id
                )
            ).scalar_one_or_none()

            if existing is not None:
                # Preserve existing ledger state (replay-safe).
                session.commit()
                return

            accounting_status = terminal_values.get("accounting_status", "incomplete")
            if accounting_status == "reconciled":
                expected = terminal_values.get("source_unique_count")
                row = ExecutionDiscoveryLinkage(
                    execution_id=execution_id,
                    linkage_schema_version="linkage_v1",
                    status="pending",
                    expected_discovery_count=expected,
                    linked_discovery_count=None,
                    linkage_attempt_count=0,
                )
            else:
                row = ExecutionDiscoveryLinkage(
                    execution_id=execution_id,
                    linkage_schema_version="linkage_v1",
                    status="not_applicable",
                    expected_discovery_count=None,
                    linked_discovery_count=None,
                    linkage_attempt_count=0,
                    completed_at=_now(),
                )
            session.add(row)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _persist_translation(
        self, execution_id: int, translated_query: str,
    ) -> None:
        """Persist translated_query if NULL; detect drift if already set.

        Raises ``TranslationDriftError`` if the stored translation differs.
        """
        from backend.db.models import SearchQueryExecution

        session = self._session()
        try:
            existing = session.execute(
                select(SearchQueryExecution.translated_query).where(
                    SearchQueryExecution.id == execution_id
                )
            ).scalar_one_or_none()

            if existing is None:
                # Write the translation.
                session.execute(
                    update(SearchQueryExecution)
                    .where(SearchQueryExecution.id == execution_id)
                    .values(
                        translated_query=translated_query,
                        execution_metadata_version="execution_v1",
                    )
                )
                session.commit()
            elif existing == translated_query:
                # Replay-safe; proceed.
                pass
            else:
                # Drift: mark failed, preserve the old translation.
                session.execute(
                    update(SearchQueryExecution)
                    .where(SearchQueryExecution.id == execution_id)
                    .values(
                        status="failed",
                        error_detail="translation drift detected",
                        failure_category="query_translation",
                        failure_code="translation_drift",
                        execution_metadata_version="execution_v1",
                        completed_at=_now(),
                    )
                )
                session.commit()
                raise TranslationDriftError(
                    f"execution {execution_id}: stored translation differs from "
                    f"newly built plan"
                )
        except TranslationDriftError:
            raise
        except Exception:
            session.rollback()
            raise
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
        limit: int = 20,
        year_from: int | None = None,
        year_to: int | None = None,
        **search_kwargs: Any,
    ) -> AttemptOutcome:
        """Drive one adapter through its full lifecycle.

        P0.2.3: Builds the query plan, persists the translation before the
        first outbound request, then executes exactly that plan.

        1. Check immutability -- if terminal/running, return without adapter.
        2. Build query plan (``adapter.build_query_plan``).
        3. Persist ``translated_query`` (drift-checked).
        4. Create ``DatabaseAttemptObserver``.
        5. Execute plan (``adapter.execute_query_plan``) via the observer.
        6. Validate invariants, cross-check attempt_count, persist terminal.
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

        # ── Running: do not invoke adapter (stale recovery deferred) ──
        if status == "running":
            logger.debug(
                "execution %d is running — not invoking adapter", execution_id,
            )
            return AttemptOutcome(
                execution_id=execution_id, source=source_name,
                status="running", attempt_count=ac,
            )

        # ── Build query plan ──
        try:
            plan = adapter.build_query_plan(
                query, limit=limit, year_from=year_from, year_to=year_to,
            )
        except Exception as exc:
            # Pre-attempt translation failure.
            self._transition(
                execution_id, "failed",
                error_detail=sanitize_error_detail(f"{type(exc).__name__}: {exc}"),
                extra_values={
                    "completed_at": _now(),
                    "failure_category": "internal",
                    "failure_code": "unexpected_translation_exception",
                    "execution_metadata_version": "execution_v1",
                },
            )
            raise

        # ── Persist translation (drift-checked) ──
        try:
            self._persist_translation(execution_id, plan.translated_query)
        except TranslationDriftError:
            return AttemptOutcome(
                execution_id=execution_id, source=source_name,
                status="failed", attempt_count=0,
                error_detail="translation drift detected",
                failure_category="query_translation",
                failure_code="translation_drift",
            )

        # ── Execute via observer ──
        observer = DatabaseAttemptObserver(execution_id, self._engine)

        try:
            if timeout_seconds is not None:
                outcome = await asyncio.wait_for(
                    adapter.execute_query_plan(plan, attempt_observer=observer),
                    timeout=timeout_seconds,
                )
            else:
                outcome = await adapter.execute_query_plan(
                    plan, attempt_observer=observer,
                )
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            _, obs_ac, attempted_at = self._get_state(execution_id)
            if attempted_at is None:
                self._transition(
                    execution_id, "failed",
                    error_detail=sanitize_error_detail(
                        f"recorder timeout ({timeout_seconds}s) before first attempt"
                    ),
                    extra_values={
                        "completed_at": _now(),
                        "failure_category": "internal",
                        "failure_code": "recorder_timeout",
                        "execution_metadata_version": "execution_v1",
                    },
                )
                return AttemptOutcome(
                    execution_id=execution_id, source=source_name,
                    status="failed", attempt_count=0,
                    error_detail="recorder timeout before first attempt",
                    failure_category="internal", failure_code="recorder_timeout",
                )
            else:
                self._transition(
                    execution_id, "timeout",
                    error_detail=sanitize_error_detail(
                        f"recorder timeout ({timeout_seconds}s) after {obs_ac} attempts"
                    ),
                    extra_values={
                        "completed_at": _now(),
                        "failure_category": "timeout",
                        "failure_code": "recorder_timeout",
                        "execution_metadata_version": "execution_v1",
                    },
                )
                return AttemptOutcome(
                    execution_id=execution_id, source=source_name,
                    status="timeout", attempt_count=obs_ac,
                    error_detail=f"recorder timeout after {obs_ac} attempts",
                    failure_category="timeout", failure_code="recorder_timeout",
                )
        except Exception as exc:
            _, obs_ac, attempted_at = self._get_state(execution_id)
            self._transition(
                execution_id, "failed",
                error_detail=sanitize_error_detail(f"{type(exc).__name__}: {exc}"),
                extra_values={
                    "completed_at": _now(),
                    "failure_category": "internal",
                    "failure_code": "unexpected_exception",
                    "execution_metadata_version": "execution_v1",
                },
            )
            raise

        # ── Strict return-type check ──
        if not isinstance(outcome, SourceSearchOutcome):
            _, obs_ac, attempted_at = self._get_state(execution_id)
            if attempted_at is not None:
                self._transition(
                    execution_id, "failed",
                    error_detail=sanitize_error_detail(
                        f"adapter returned {type(outcome).__name__}, "
                        f"expected SourceSearchOutcome"
                    ),
                    extra_values={
                        "completed_at": _now(),
                        "failure_category": "adapter_contract",
                        "failure_code": "adapter_return_type",
                        "execution_metadata_version": "execution_v1",
                    },
                )
            raise TypeError(
                f"governed adapter {source_name!r} returned "
                f"{type(outcome).__name__}, expected SourceSearchOutcome."
            )

        # ── Validate invariants ──
        _, obs_ac, attempted_at = self._get_state(execution_id)
        attempted_at_is_null = attempted_at is None
        try:
            validate_outcome(outcome, attempted_at_is_null=attempted_at_is_null)
        except ValueError:
            # Invariant violation — persist as failed then propagate.
            self._transition(
                execution_id, "failed",
                error_detail="outcome invariant violation",
                extra_values={
                    "completed_at": _now(),
                    "failure_category": "adapter_contract",
                    "failure_code": "outcome_invariant",
                    "execution_metadata_version": "execution_v1",
                },
            )
            raise

        # ── Cross-check attempt_count ──
        if outcome.attempt_count != obs_ac:
            self._transition(
                execution_id, "failed",
                error_detail="attempt_count mismatch",
                extra_values={
                    "completed_at": _now(),
                    "failure_category": "adapter_contract",
                    "failure_code": "attempt_count_mismatch",
                    "execution_metadata_version": "execution_v1",
                },
            )
            raise ValueError(
                f"attempt_count mismatch for execution {execution_id}: "
                f"adapter reported {outcome.attempt_count}, "
                f"observer counted {obs_ac}"
            )

        # ── P0.2.4: Accounting validation and persistence ──
        from backend.pipeline.literature.contracts import validate_accounting

        extra: dict[str, Any] = {"completed_at": _now()}
        if outcome.status != "success":
            extra["failure_category"] = outcome.failure_category
            extra["failure_code"] = outcome.failure_code

        # success/partial MUST include valid accounting (frozen rule).
        # failed MAY include accounting. timeout/skipped NEVER.
        if outcome.status in ("success", "partial"):
            if outcome.accounting is None:
                # Missing accounting on governed success/partial = contract defect.
                self._transition(
                    execution_id, "failed",
                    error_detail="governed success/partial outcome missing accounting",
                    extra_values={
                        "completed_at": _now(),
                        "failure_category": "adapter_contract",
                        "failure_code": "accounting_missing",
                        "execution_metadata_version": "execution_v1",
                    },
                )
                raise ValueError(
                    f"governed {outcome.status} outcome for execution {execution_id} "
                    f"is missing accounting"
                )
            try:
                validate_accounting(outcome.accounting, outcome.results)
            except ValueError:
                self._transition(
                    execution_id, "failed",
                    error_detail="accounting invariant violation",
                    extra_values={
                        "completed_at": _now(),
                        "failure_category": "adapter_contract",
                        "failure_code": "accounting_invariant",
                        "execution_metadata_version": "execution_v1",
                    },
                )
                raise
            # Persist reconciled accounting atomically with terminal state.
            extra["raw_result_count"] = outcome.accounting.raw_result_count
            extra["normalized_result_count"] = outcome.accounting.normalized_result_count
            extra["rejected_result_count"] = outcome.accounting.rejected_result_count
            extra["source_unique_count"] = outcome.accounting.source_unique_count
            extra["accounting_status"] = "reconciled"
            extra["accounting_schema_version"] = "accounting_v1"

        elif outcome.status == "failed" and outcome.accounting is not None:
            # Failed outcome may carry accounting if a stable raw set was observed.
            try:
                validate_accounting(outcome.accounting, outcome.results)
                extra["raw_result_count"] = outcome.accounting.raw_result_count
                extra["normalized_result_count"] = outcome.accounting.normalized_result_count
                extra["rejected_result_count"] = outcome.accounting.rejected_result_count
                extra["source_unique_count"] = outcome.accounting.source_unique_count
                extra["accounting_status"] = "reconciled"
                extra["accounting_schema_version"] = "accounting_v1"
            except ValueError:
                # Invalid accounting on failed — persist as failed, no counts.
                pass

        # timeout/skipped: leave accounting incomplete (all NULL, no version).
        # The _transition call below does NOT set count fields if not in extra.

        self._transition(
            execution_id, outcome.status,
            error_detail=sanitize_error_detail(outcome.error_detail)
            if outcome.status != "success" else None,
            extra_values=extra,
        )

        # ── P0.2.5: Create linkage ledger atomically with terminal accounting ──
        self._ensure_linkage_ledger(execution_id, extra)

        return AttemptOutcome(
            execution_id=execution_id, source=source_name,
            status=outcome.status, attempt_count=outcome.attempt_count,
            results=list(outcome.results),
            error_detail=outcome.error_detail if outcome.status != "success" else None,
            failure_category=outcome.failure_category if outcome.status != "success" else None,
            failure_code=outcome.failure_code if outcome.status != "success" else None,
        )
