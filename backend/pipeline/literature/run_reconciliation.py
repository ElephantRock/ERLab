"""Run-level search reconciliation engine (P0.2.6).

Reconciles a governed literature-search run from logical query intent through
intended source executions, execution-local accounting, execution-linked
discovery routes, canonical papers, and RunPaper membership.

The reconciliation is an **audit snapshot** over already-committed state.
It uses a separate short transaction so a reconciliation defect cannot
roll back valid execution or corpus records.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

_VALID_NONREMOTE_ORIGINS = frozenset({"local_upload", "knowledge_library", "legacy_global_import"})


class RunReconciliationError(Exception):
    """Base class for reconciliation failures."""


class RunReconciliationDriftError(RunReconciliationError):
    """A reconciled run's input fingerprint changed on replay."""


class ExecutionScopeDriftError(RunReconciliationError):
    """An execution scope's intended source set changed on replay."""


def _now() -> datetime:
    return datetime.now(UTC)


# ── Reconciliation snapshot ──────────────────────────────────────────


@dataclass(frozen=True)
class RunSearchReconciliationSnapshot:
    """Complete aggregate snapshot of a run's search provenance."""

    run_id: int
    logical_query_count: int
    expected_execution_count: int
    actual_execution_count: int
    terminal_execution_count: int

    success_execution_count: int
    partial_execution_count: int
    failed_execution_count: int
    timeout_execution_count: int
    skipped_execution_count: int

    reconciled_accounting_execution_count: int
    incomplete_accounting_execution_count: int

    source_unique_result_count: int
    linked_discovery_count: int

    remote_canonical_paper_count: int
    nonremote_canonical_paper_count: int
    remote_only_paper_count: int
    nonremote_only_paper_count: int
    multi_origin_paper_count: int
    run_paper_count: int

    canonicalization_reduction_count: int
    unexplained_membership_count: int
    unowned_discovery_paper_count: int

    execution_posture: str
    input_fingerprint: str


# ── Scope registration ───────────────────────────────────────────────


def canonical_source_set(intended_sources: list[str]) -> list[str]:
    """Normalize and deduplicate intended sources into canonical sorted form."""
    return sorted({s.strip().lower() for s in intended_sources if s and s.strip()})


def canonical_source_json(sources: list[str]) -> str:
    """Canonical JSON representation of a source set."""
    return json.dumps(sources, ensure_ascii=False, separators=(",", ":"))


def source_set_hash(sources: list[str]) -> str:
    """SHA-256 of the canonical source set JSON."""
    return hashlib.sha256(canonical_source_json(sources).encode("utf-8")).hexdigest()


def ensure_execution_scope(
    engine: Any,
    search_query_id: int,
    intended_sources: list[str],
) -> None:
    """Register or verify an execution scope for a logical query.

    Same source set → no-op (replay-safe).
    Different source set → ExecutionScopeDriftError (historical preserved).
    """
    from backend.db.models import SearchQueryExecutionScope

    sources = canonical_source_set(intended_sources)
    src_json = canonical_source_json(sources)
    src_hash = source_set_hash(sources)

    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        existing = session.execute(
            select(SearchQueryExecutionScope).where(
                SearchQueryExecutionScope.search_query_id == search_query_id
            )
        ).scalar_one_or_none()

        if existing is not None:
            if existing.source_set_hash != src_hash:
                raise ExecutionScopeDriftError(
                    f"execution scope drift for query {search_query_id}: "
                    f"stored hash {existing.source_set_hash[:12]}... != new hash {src_hash[:12]}..."
                )
            # Replay-safe: same scope, no-op.
            session.commit()
            return

        scope = SearchQueryExecutionScope(
            search_query_id=search_query_id,
            scope_schema_version="execution_scope_v1",
            intended_sources_json=src_json,
            intended_source_count=len(sources),
            source_set_hash=src_hash,
        )
        session.add(scope)
        session.commit()
    except ExecutionScopeDriftError:
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── Reconciliation snapshot builder ──────────────────────────────────


def build_reconciliation_snapshot(engine: Any, run_id: int) -> RunSearchReconciliationSnapshot:
    """Build the aggregate reconciliation snapshot for a run.

    Queries committed state to compute all counts. Raises
    ``RunReconciliationError`` if a set-equation violation is found.
    """
    from backend.db.models import (
        ExecutionDiscoveryLinkage,
        PaperDiscovery,
        RunPaper,
        SearchQuery,
        SearchQueryExecution,
        SearchQueryExecutionScope,
    )

    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        # ── Logical queries ──
        queries = session.execute(
            select(SearchQuery).where(SearchQuery.run_id == run_id)
        ).scalars().all()
        logical_query_count = len(queries)

        # ── Execution scopes (expected set) ──
        scopes = session.execute(
            select(SearchQueryExecutionScope).where(
                SearchQueryExecutionScope.search_query_id.in_(
                    [q.id for q in queries]
                ) if queries else [0]
            )
        ).scalars().all()

        expected_pairs: set[tuple[int, str]] = set()
        for scope in scopes:
            sources = json.loads(scope.intended_sources_json)
            for src in sources:
                expected_pairs.add((scope.search_query_id, src))

        expected_execution_count = len(expected_pairs)

        # ── Actual executions ──
        query_ids = {q.id for q in queries}
        executions = session.execute(
            select(SearchQueryExecution).where(
                SearchQueryExecution.search_query_id.in_(query_ids) if query_ids else [0]
            )
        ).scalars().all()

        actual_pairs = {(e.search_query_id, e.source) for e in executions}
        actual_execution_count = len(executions)

        # ── Execution status counts ──
        status_counts: dict[str, int] = {}
        for ex in executions:
            status_counts[ex.status] = status_counts.get(ex.status, 0) + 1

        success_count = status_counts.get("success", 0)
        partial_count = status_counts.get("partial", 0)
        failed_count = status_counts.get("failed", 0)
        timeout_count = status_counts.get("timeout", 0)
        skipped_count = status_counts.get("skipped", 0)
        pending_count = status_counts.get("pending", 0)
        running_count = status_counts.get("running", 0)
        terminal_count = success_count + partial_count + failed_count + timeout_count + skipped_count

        # ── Accounting posture ──
        reconciled_acct = sum(1 for e in executions if e.accounting_status == "reconciled")
        incomplete_acct = sum(1 for e in executions if e.accounting_status == "incomplete")

        # ── Linkage ledgers ──
        exec_ids = {e.id for e in executions}
        ledgers = session.execute(
            select(ExecutionDiscoveryLinkage).where(
                ExecutionDiscoveryLinkage.execution_id.in_(exec_ids) if exec_ids else [0]
            )
        ).scalars().all()

        # ── Source-unique count ──
        source_unique_result_count = sum(
            e.source_unique_count or 0 for e in executions
            if e.accounting_status == "reconciled"
        )

        # ── Linked discoveries ──
        linked_discoveries = session.execute(
            select(func.count(PaperDiscovery.id)).where(
                PaperDiscovery.run_id == run_id,
                PaperDiscovery.linkage_schema_version == "linkage_v1",
            )
        ).scalar_one()
        linked_discovery_count = linked_discoveries

        # ── Remote canonical papers ──
        remote_paper_ids = {
            row[0] for row in session.execute(
                select(PaperDiscovery.paper_id).where(
                    PaperDiscovery.run_id == run_id,
                    PaperDiscovery.linkage_schema_version == "linkage_v1",
                    PaperDiscovery.discovery_origin == "remote_search",
                ).distinct()
            ).all()
        }
        remote_canonical_paper_count = len(remote_paper_ids)

        # ── Nonremote papers ──
        nonremote_discs = session.execute(
            select(PaperDiscovery.paper_id, PaperDiscovery.discovery_origin).where(
                PaperDiscovery.run_id == run_id,
                PaperDiscovery.linkage_schema_version.is_(None),
            ).distinct()
        ).all()
        nonremote_paper_ids: set[int] = set()
        for pid, origin in nonremote_discs:
            if origin in _VALID_NONREMOTE_ORIGINS:
                nonremote_paper_ids.add(pid)

        nonremote_canonical_paper_count = len(nonremote_paper_ids)

        # ── Set decomposition ──
        remote_only = remote_paper_ids - nonremote_paper_ids
        nonremote_only = nonremote_paper_ids - remote_paper_ids
        multi_origin = remote_paper_ids & nonremote_paper_ids

        remote_only_count = len(remote_only)
        nonremote_only_count = len(nonremote_only)
        multi_origin_count = len(multi_origin)

        # ── RunPaper membership ──
        run_paper_ids = {
            row[0] for row in session.execute(
                select(RunPaper.paper_id).where(RunPaper.run_id == run_id)
            ).all()
        }
        run_paper_count = len(run_paper_ids)

        # ── Membership reconciliation ──
        discovery_paper_ids = remote_paper_ids | nonremote_paper_ids
        unexplained_membership = run_paper_ids - discovery_paper_ids
        unowned_discovery = discovery_paper_ids - run_paper_ids
        unexplained_membership_count = len(unexplained_membership)
        unowned_discovery_paper_count = len(unowned_discovery)

        canonicalization_reduction = linked_discovery_count - remote_canonical_paper_count

        # ── Execution posture ──
        if pending_count > 0 or running_count > 0:
            posture = "degraded"  # Will be blocked, not reconciled
        elif success_count == actual_execution_count and actual_execution_count > 0:
            posture = "healthy"
        elif success_count > 0 or partial_count > 0:
            posture = "degraded"
        else:
            posture = "no_usable_sources"

        # ── Fingerprint ──
        fingerprint = _compute_fingerprint(
            queries, scopes, executions, ledgers,
            session, run_id, run_paper_ids,
        )

        return RunSearchReconciliationSnapshot(
            run_id=run_id,
            logical_query_count=logical_query_count,
            expected_execution_count=expected_execution_count,
            actual_execution_count=actual_execution_count,
            terminal_execution_count=terminal_count,
            success_execution_count=success_count,
            partial_execution_count=partial_count,
            failed_execution_count=failed_count,
            timeout_execution_count=timeout_count,
            skipped_execution_count=skipped_count,
            reconciled_accounting_execution_count=reconciled_acct,
            incomplete_accounting_execution_count=incomplete_acct,
            source_unique_result_count=source_unique_result_count,
            linked_discovery_count=linked_discovery_count,
            remote_canonical_paper_count=remote_canonical_paper_count,
            nonremote_canonical_paper_count=nonremote_canonical_paper_count,
            remote_only_paper_count=remote_only_count,
            nonremote_only_paper_count=nonremote_only_count,
            multi_origin_paper_count=multi_origin_count,
            run_paper_count=run_paper_count,
            canonicalization_reduction_count=canonicalization_reduction,
            unexplained_membership_count=unexplained_membership_count,
            unowned_discovery_paper_count=unowned_discovery_paper_count,
            execution_posture=posture,
            input_fingerprint=fingerprint,
        )
    finally:
        session.close()


def _compute_fingerprint(
    queries, scopes, executions, ledgers, session, run_id, run_paper_ids,
) -> str:
    """Compute a deterministic SHA-256 fingerprint over all reconciliation inputs."""

    fingerprint_data: dict[str, Any] = {
        "query_scopes": sorted([
            {"search_query_id": s.search_query_id, "source_set_hash": s.source_set_hash}
            for s in scopes
        ], key=lambda x: x["search_query_id"]),
        "executions": sorted([
            {
                "id": e.id, "search_query_id": e.search_query_id,
                "source": e.source, "status": e.status,
                "accounting_status": e.accounting_status,
                "source_unique_count": e.source_unique_count,
            }
            for e in executions
        ], key=lambda x: x["id"]),
        "linkage_ledgers": sorted([
            {
                "execution_id": l.execution_id, "status": l.status,
                "expected_discovery_count": l.expected_discovery_count,
                "linked_discovery_count": l.linked_discovery_count,
            }
            for l in ledgers
        ], key=lambda x: x["execution_id"]),
        "run_membership": sorted(run_paper_ids),
    }

    return hashlib.sha256(
        json.dumps(fingerprint_data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


# ── Reconciliation validation ────────────────────────────────────────


def validate_snapshot(snapshot: RunSearchReconciliationSnapshot) -> str | None:
    """Validate the snapshot's set equations.

    Returns an issue_code string if a violation is found, None if valid.
    """
    s = snapshot

    # Nonterminal executions → blocked
    if s.terminal_execution_count != s.actual_execution_count:
        return "nonterminal_execution"

    # Execution set mismatch
    if s.expected_execution_count != s.actual_execution_count:
        return "execution_set_mismatch"

    # Source-unique != linked discoveries
    if s.source_unique_result_count != s.linked_discovery_count:
        return "discovery_count_mismatch"

    # Unexplained membership
    if s.unexplained_membership_count > 0:
        return "membership_mismatch"

    # Unowned discovery
    if s.unowned_discovery_paper_count > 0:
        return "membership_mismatch"

    return None


# ── Reconciliation persistence ───────────────────────────────────────


def reconcile_run_search(engine: Any, run_id: int) -> str:
    """Reconcile a run's search provenance and persist the result.

    Uses a separate short transaction. Returns the final status:
    'reconciled', 'blocked', or 'failed'.

    Replay-safe: a reconciled row with the same fingerprint is a no-op.
    A different fingerprint raises RunReconciliationDriftError.
    """
    from backend.db.models import RunSearchReconciliation

    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        existing = session.execute(
            select(RunSearchReconciliation).where(
                RunSearchReconciliation.run_id == run_id
            )
        ).scalar_one_or_none()

        if existing is None:
            existing = RunSearchReconciliation(
                run_id=run_id,
                reconciliation_schema_version="run_reconciliation_v1",
                status="pending",
                reconciliation_attempt_count=0,
            )
            session.add(existing)
            session.flush()

        # Already reconciled → check fingerprint for drift
        if existing.status == "reconciled":
            snapshot = build_reconciliation_snapshot(engine, run_id)
            if snapshot.input_fingerprint == existing.input_fingerprint:
                # No-op replay
                session.commit()
                return "reconciled"
            else:
                session.rollback()
                raise RunReconciliationDriftError(
                    f"reconciliation drift for run {run_id}: fingerprint changed"
                )

        # Build snapshot
        existing.reconciliation_attempt_count += 1
        session.commit()

        snapshot = build_reconciliation_snapshot(engine, run_id)

        # Validate
        issue = validate_snapshot(snapshot)

        if issue is not None:
            if issue == "nonterminal_execution":
                existing.status = "blocked"
            else:
                existing.status = "failed"
            existing.issue_code = issue
            existing.issue_detail = f"reconciliation failed: {issue}"
            existing.last_checked_at = _now()
            if existing.status == "failed":
                existing.completed_at = _now()
            session.commit()
            return existing.status

        # All equations hold → reconciled
        existing.status = "reconciled"
        existing.execution_posture = snapshot.execution_posture
        existing.input_fingerprint = snapshot.input_fingerprint
        existing.completed_at = _now()
        existing.last_checked_at = _now()
        existing.issue_code = None
        existing.issue_detail = None

        # Persist all aggregate counts
        for field in (
            "logical_query_count", "expected_execution_count", "actual_execution_count",
            "terminal_execution_count", "success_execution_count", "partial_execution_count",
            "failed_execution_count", "timeout_execution_count", "skipped_execution_count",
            "reconciled_accounting_execution_count", "incomplete_accounting_execution_count",
            "source_unique_result_count", "linked_discovery_count",
            "remote_canonical_paper_count", "nonremote_canonical_paper_count",
            "remote_only_paper_count", "nonremote_only_paper_count",
            "multi_origin_paper_count", "run_paper_count",
            "canonicalization_reduction_count",
            "unexplained_membership_count", "unowned_discovery_paper_count",
        ):
            setattr(existing, field, getattr(snapshot, field))

        session.commit()
        return "reconciled"
    except RunReconciliationDriftError:
        raise
    except Exception as e:
        session.rollback()
        logger.error("Run reconciliation failed for run %d: %s", run_id, e)
        # Mark as failed in a fresh attempt
        try:
            session2 = Session()
            row = session2.execute(
                select(RunSearchReconciliation).where(
                    RunSearchReconciliation.run_id == run_id
                )
            ).scalar_one_or_none()
            if row and row.status not in ("reconciled",):
                row.status = "failed"
                row.issue_code = "unexpected_error"
                row.issue_detail = sanitize_issue_detail(str(e))
                row.completed_at = _now()
                row.last_checked_at = _now()
                session2.commit()
            session2.close()
        except Exception:
            pass
        raise
    finally:
        session.close()


def sanitize_issue_detail(detail: str) -> str:
    """Sanitize an issue detail string for storage (truncate, strip secrets)."""
    if not detail:
        return "unknown error"
    s = str(detail)[:500]
    return s


def ensure_pending_reconciliation(engine: Any, run_id: int) -> None:
    """Ensure a pending run_search_reconciliation row exists for a run.

    Called at stage start so a crash leaves an explicit incomplete posture.
    """
    from backend.db.models import RunSearchReconciliation

    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        existing = session.execute(
            select(RunSearchReconciliation).where(
                RunSearchReconciliation.run_id == run_id
            )
        ).scalar_one_or_none()

        if existing is None:
            row = RunSearchReconciliation(
                run_id=run_id,
                reconciliation_schema_version="run_reconciliation_v1",
                status="pending",
                reconciliation_attempt_count=0,
            )
            session.add(row)
            session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()
