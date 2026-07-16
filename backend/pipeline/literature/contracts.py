"""Transport-neutral contracts for the literature search execution lifecycle.

This module is intentionally free of database/ORM imports so that source
adapters can type their ``search()`` signatures without pulling in a
database-aware recorder. The dependency direction is:

    adapters            -> contracts
    execution_recorder  -> contracts + ORM/persistence
    search_service      -> adapters + recorder + contracts

This keeps the graph acyclic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

from backend.pipeline.literature.models import SearchResult

# ── Terminal statuses ────────────────────────────────────────────────

# The lifecycle vocabulary. See SearchQueryExecution model docstring and
# migration 015 for the CHECK-constrained set.
ExecutionStatus = Literal[
    "pending", "running", "success", "partial", "failed", "timeout", "skipped",
]

# Statuses that are terminal (immutable under replay).
TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"success", "partial", "failed", "timeout", "skipped"}
)

# Valid transitions. Keys are the "from" status; values are the allowed "to"
# statuses. Terminal states are absent -- they are immutable.
#   pending -> running : normal start (via first observer callback)
#   pending -> skipped : intended source has no active adapter
#   pending -> failed  : pre-attempt failure (exception before any request)
#   running -> success | partial | failed | timeout : terminal outcomes
VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"running", "skipped", "failed"}),
    "running": frozenset({"success", "partial", "failed", "timeout"}),
}


# ── Observer ─────────────────────────────────────────────────────────


@runtime_checkable
class AttemptObserver(Protocol):
    """Notified immediately before every outbound provider request.

    The observer owns the database transitions, so ``attempt_count`` is
    accurate even on cancellation, crash, or timeout-interruption.

    The first callback atomically claims the execution (pending -> running).
    Subsequent callbacks increment the count (running -> running).
    """

    async def attempt_started(self) -> None:
        """Record one actual outbound provider request."""
        ...


# ── Outcomes ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SourceSearchOutcome:
    """Truthful outcome of a single source-adapter ``search()`` invocation.

    Adapters MUST return this (not a bare ``list[SearchResult]``) on the
    governed path. The ``attempt_count`` is the adapter's report of how many
    outbound requests it made; the recorder cross-checks this against the
    observer's independently counted callbacks and a mismatch is a defect.

    Outcome invariants (validated by ``validate_outcome``):
        success:  attempt_count >= 1, error_detail None
        partial:  attempt_count >= 1, results non-empty, error_detail present
        failed:   attempt_count >= 0 (0 only if attempted_at is NULL),
                  results empty, error_detail present
        timeout:  attempt_count >= 1, results empty, error_detail present
    """

    results: list[SearchResult]
    status: ExecutionStatus
    attempt_count: int
    error_detail: str | None = None


@dataclass(frozen=True)
class AttemptOutcome:
    """A recorder's terminal record for one execution, including the result.

    Returned by ``ExecutionRecorder.run_execution``. Failed/skipped/timeout
    executions produce an AttemptOutcome with empty ``results`` -- the caller
    (SearchService) collects these so failed attempts remain visible even
    when no candidates are persisted.
    """

    execution_id: int
    source: str
    status: ExecutionStatus
    attempt_count: int
    results: list[SearchResult] = field(default_factory=list)
    error_detail: str | None = None


@dataclass(frozen=True)
class SearchBatchOutcome:
    """The result of one logical query across all intended sources.

    Carries both the deduplicated candidates (for corpus persistence) and
    the per-source execution outcomes (for telemetry). Failed/skipped
    executions appear in ``executions`` even when they produced no
    candidates -- that is the visibility guarantee.
    """

    candidates: list  # list[CandidateWithDiscoveries] -- typed loosely to avoid import cycle
    executions: list[AttemptOutcome]


# ── Invariant validation ─────────────────────────────────────────────


def validate_outcome(
    outcome: SourceSearchOutcome, *, attempted_at_is_null: bool,
) -> None:
    """Validate that a SourceSearchOutcome is internally consistent.

    Raises ``ValueError`` on violation. This is an instrumentation defect,
    not an expected transport failure -- it must propagate, not be swallowed.

    Args:
        outcome: the adapter-reported outcome.
        attempted_at_is_null: whether the persisted execution has
            ``attempted_at IS NULL`` at terminal time (i.e. no observer
            callback ever fired). True only for pre-attempt failures.
    """
    status = outcome.status
    ac = outcome.attempt_count
    err = outcome.error_detail
    n_results = len(outcome.results)

    if status == "success":
        if ac < 1:
            raise ValueError(
                f"success outcome requires attempt_count >= 1, got {ac}"
            )
        if err is not None:
            raise ValueError("success outcome must have error_detail = None")

    elif status == "partial":
        if ac < 1:
            raise ValueError(
                f"partial outcome requires attempt_count >= 1, got {ac}"
            )
        if n_results == 0:
            raise ValueError("partial outcome requires non-empty results")
        if not err:
            raise ValueError("partial outcome requires error_detail present")

    elif status == "failed":
        if n_results > 0:
            raise ValueError("failed outcome must have empty results")
        if not err:
            raise ValueError("failed outcome requires error_detail present")
        if ac < 0:
            raise ValueError(f"failed outcome attempt_count must be >= 0, got {ac}")
        # attempt_count == 0 is permitted only when no attempt was observed.
        if ac == 0 and not attempted_at_is_null:
            raise ValueError(
                "failed outcome with attempt_count=0 requires attempted_at IS NULL "
                "(pre-attempt failure), but an attempt was observed"
            )
        if ac >= 1 and attempted_at_is_null:
            raise ValueError(
                f"failed outcome with attempt_count={ac} but attempted_at IS NULL "
                "(observer counted attempts but none were recorded as started)"
            )

    elif status == "timeout":
        if ac < 1:
            raise ValueError(
                f"timeout outcome requires attempt_count >= 1, got {ac}"
            )
        if n_results > 0:
            raise ValueError("timeout outcome must have empty results")
        if not err:
            raise ValueError("timeout outcome requires error_detail present")

    else:
        raise ValueError(
            f"SourceSearchOutcome.status must be success/partial/failed/timeout, "
            f"got {status!r}"
        )
