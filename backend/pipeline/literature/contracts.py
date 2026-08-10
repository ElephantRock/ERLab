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

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

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


# ── Query plan (P0.2.3) ──────────────────────────────────────────────


@dataclass(frozen=True)
class SourceQueryPlan:
    """Deterministic provider-level query plan.

    ``translated_query`` is the canonical JSON serialization, safe for
    persistence. ``request_parameters`` are used by the adapter's
    ``execute_query_plan`` and MUST exclude secrets (API keys, tokens,
    authorization headers, URL credentials, mailto identity).

    The persisted ``translated_query`` is the same plan the adapter
    executes — one source of truth, no independent reconstruction.
    """

    source: str
    schema_version: Literal["source_query_v1"]
    translated_query: str
    request_parameters: Mapping[str, object]


def canonical_plan_json(source: str, parameters: dict[str, Any]) -> str:
    """Build a canonical JSON serialization of a query plan.

    The output is deterministic (sorted keys, compact separators) so it
    can be compared for translation-drift detection. MUST NOT contain
    secrets — the adapter is responsible for excluding them from
    ``parameters`` before calling this.
    """
    representation = {
        "schema": "source_query_v1",
        "source": source,
        "parameters": parameters,
    }
    return json.dumps(
        representation,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


# ── Result accounting (P0.2.4) ───────────────────────────────────────


@dataclass(frozen=True)
class SourceResultAccounting:
    """Execution-local reconciliation of provider candidates.

    Every governed success/partial execution must carry valid accounting.
    The invariant: ``raw_result_count = normalized_result_count +
    rejected_result_count`` and ``source_unique_count <=
    normalized_result_count`` and ``len(results) == source_unique_count``.
    """

    schema_version: Literal["accounting_v1"]
    raw_result_count: int
    normalized_result_count: int
    rejected_result_count: int
    source_unique_count: int

    @property
    def within_execution_duplicates_removed(self) -> int:
        return self.normalized_result_count - self.source_unique_count


def validate_accounting(
    accounting: SourceResultAccounting,
    results: list[SearchResult],
) -> None:
    """Validate that a SourceResultAccounting is internally consistent.

    Rejects:
      - bool values (Python treats bool as int subclass)
      - negative values
      - raw != normalized + rejected
      - source_unique > normalized
      - len(results) != source_unique
      - schema_version != accounting_v1

    Raises ``ValueError`` on violation.
    """
    a = accounting

    # Reject bool (Python bool is an int subclass — must check explicitly).
    for name, val in (
        ("raw_result_count", a.raw_result_count),
        ("normalized_result_count", a.normalized_result_count),
        ("rejected_result_count", a.rejected_result_count),
        ("source_unique_count", a.source_unique_count),
    ):
        if isinstance(val, bool):
            raise ValueError(f"accounting {name} must be int, not bool")
        if not isinstance(val, int):
            raise ValueError(f"accounting {name} must be int, got {type(val).__name__}")
        if val < 0:
            raise ValueError(f"accounting {name} must be >= 0, got {val}")

    if a.schema_version != "accounting_v1":
        raise ValueError(
            f"accounting schema_version must be 'accounting_v1', got {a.schema_version!r}"
        )

    if a.raw_result_count != a.normalized_result_count + a.rejected_result_count:
        raise ValueError(
            f"accounting equation violated: raw ({a.raw_result_count}) != "
            f"normalized ({a.normalized_result_count}) + rejected ({a.rejected_result_count})"
        )

    if a.source_unique_count > a.normalized_result_count:
        raise ValueError(
            f"source_unique ({a.source_unique_count}) > normalized ({a.normalized_result_count})"
        )

    if len(results) != a.source_unique_count:
        raise ValueError(
            f"len(results) ({len(results)}) != source_unique_count ({a.source_unique_count})"
        )


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

    P0.2.4: Every governed success/partial outcome must include valid
    ``accounting``. Failed/timeout outcomes may include accounting only
    when a stable raw candidate set was observed.
    """

    results: list[SearchResult]
    status: ExecutionStatus
    attempt_count: int
    error_detail: str | None = None
    failure_category: str | None = None
    failure_code: str | None = None
    accounting: SourceResultAccounting | None = None


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
    failure_category: str | None = None
    failure_code: str | None = None


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


@dataclass(frozen=True)
class ExecutionLinkageExpectation:
    """Reference to an execution for governed corpus persistence (P0.2.5).

    Each reconciled execution produces one expectation; zero-result
    executions still need explicit reconciliation. The governed persistence
    validates that every source-unique result produces exactly one
    PaperDiscovery linked to this execution.
    """

    execution_id: int
    search_query_id: int
    source: str
    expected_discovery_count: int | None
    accounting_status: str


@dataclass(frozen=True)
class GovernedSearchContext:
    """Explicit marker that a governed search has been executed.

    P0.2.7: Replaces context-truthiness checks. An empty candidate list
    is VALID for a governed search — the marker's presence (not list
    truthiness) signals the governed path.
    """

    schema_version: Literal["governed_search_context_v1"]
    search_query_data: tuple  # tuple[SearchQueryData, ...]
    candidate_papers: tuple  # tuple[CandidateWithDiscoveries, ...]
    execution_linkage_expectations: tuple  # tuple[ExecutionLinkageExpectation, ...]


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
    cat = outcome.failure_category
    code = outcome.failure_code
    n_results = len(outcome.results)

    if status == "success":
        if ac < 1:
            raise ValueError(
                f"success outcome requires attempt_count >= 1, got {ac}"
            )
        if err is not None:
            raise ValueError("success outcome must have error_detail = None")
        if cat is not None or code is not None:
            raise ValueError("success outcome must have failure_category/code = None")

    elif status == "partial":
        if ac < 1:
            raise ValueError(
                f"partial outcome requires attempt_count >= 1, got {ac}"
            )
        if n_results == 0:
            raise ValueError("partial outcome requires non-empty results")
        if not err:
            raise ValueError("partial outcome requires error_detail present")
        if not cat:
            raise ValueError("partial outcome requires failure_category")
        if not code:
            raise ValueError("partial outcome requires failure_code")

    elif status == "failed":
        if n_results > 0:
            raise ValueError("failed outcome must have empty results")
        if not err:
            raise ValueError("failed outcome requires error_detail present")
        if not cat:
            raise ValueError("failed outcome requires failure_category")
        if not code:
            raise ValueError("failed outcome requires failure_code")
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
        if cat != "timeout":
            raise ValueError(
                f"timeout outcome requires failure_category='timeout', got {cat!r}"
            )
        if not code:
            raise ValueError("timeout outcome requires failure_code")

    else:
        raise ValueError(
            f"SourceSearchOutcome.status must be success/partial/failed/timeout, "
            f"got {status!r}"
        )
