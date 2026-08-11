"""Central vector scope resolver (P0.3.1).

The single authority for converting a ``VectorRetrievalScope`` into a
``ResolvedVectorScope``. No production caller may construct backend
filters independently.

Resolution rules per mode:
  current_run_only       → run_papers WHERE run_id = :run_id
  same_domain_prior_runs → earlier reconciled provenance_v1 runs with same domain_scope_key
  global_library         → active global_library_memberships
  selected_papers        → validated explicit paper IDs

For provenance_v1 runs, absence of a scope is a contract error.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.pipeline.provenance_gate import (
    load_run_provenance_contract,
)
from backend.pipeline.vector_contracts import (
    ResolvedVectorScope,
    VectorRetrievalScope,
    VectorScopeError,
    compute_scope_fingerprint,
)

logger = logging.getLogger(__name__)


class VectorScopeResolutionError(VectorScopeError):
    """Scope resolution failed."""


def resolve_vector_scope(
    session: Session,
    scope: VectorRetrievalScope,
) -> ResolvedVectorScope:
    """Resolve a vector retrieval scope into an immutable allowed-paper set.

    Uses the session's active transaction (read-only queries).
    Returns a ``ResolvedVectorScope`` with the authoritative paper set.
    """
    contract = load_run_provenance_contract(session, scope.run_id)

    # Governed runs require explicit scope
    if contract.provenance_version == "provenance_v1":
        if scope.schema_version != "vector_scope_v1":
            raise VectorScopeResolutionError(
                f"governed run {scope.run_id} requires vector_scope_v1, "
                f"got {scope.schema_version!r}"
            )
    elif contract.provenance_version == "pre_provenance":
        raise VectorScopeResolutionError(
            f"legacy run {scope.run_id} cannot use governed vector scope; "
            f"use query_vectors_legacy_unscoped instead"
        )

    # Resolve allowed paper IDs by mode
    if scope.mode == "current_run_only":
        allowed = _resolve_current_run(session, scope.run_id)
    elif scope.mode == "same_domain_prior_runs":
        allowed = _resolve_same_domain_prior_runs(session, scope.run_id, contract)
    elif scope.mode == "global_library":
        allowed = _resolve_global_library(session)
    elif scope.mode == "selected_papers":
        allowed = _resolve_selected_papers(session, scope.selected_paper_ids)
    else:
        raise VectorScopeResolutionError(
            f"unknown scope mode {scope.mode!r}"
        )

    # Compute indexed subset (P0.3.2 will populate vector_index_records;
    # for now, assume all allowed papers are potentially indexed)
    # This is the contract — P0.3.2 will make this real.
    indexed_paper_ids = allowed  # placeholder until registry exists

    # Compute fingerprint
    domain_key = _get_domain_scope_key(session, scope.run_id)
    fingerprint = compute_scope_fingerprint(
        run_id=scope.run_id,
        mode=scope.mode,
        embedding_profile_id=scope.embedding_profile_id,
        allowed_paper_ids=allowed,
        indexed_paper_ids=indexed_paper_ids,
        domain_scope_key=domain_key,
    )

    return ResolvedVectorScope(
        schema_version="resolved_vector_scope_v1",
        mode=scope.mode,
        run_id=scope.run_id,
        embedding_profile_id=scope.embedding_profile_id,
        allowed_paper_ids=tuple(sorted(allowed)),
        allowed_paper_count=len(allowed),
        indexed_paper_ids=tuple(sorted(indexed_paper_ids)),
        indexed_paper_count=len(indexed_paper_ids),
        eligible_vector_record_count=len(indexed_paper_ids),
        scope_fingerprint=fingerprint,
    )


def _resolve_current_run(session: Session, run_id: int) -> list[int]:
    """Resolve allowed papers for current_run_only mode."""
    from backend.db.models import RunPaper

    rows = session.execute(
        select(RunPaper.paper_id).where(RunPaper.run_id == run_id)
    ).all()
    return [r[0] for r in rows]


def _resolve_same_domain_prior_runs(
    session: Session, run_id: int, contract,
) -> list[int]:
    """Resolve papers from earlier reconciled runs with the same domain."""
    from backend.db.models import PipelineRun, RunPaper, RunSearchReconciliation

    current_run = session.execute(
        select(PipelineRun).where(PipelineRun.id == run_id)
    ).scalar_one_or_none()

    if current_run is None or current_run.domain_scope_key is None:
        raise VectorScopeResolutionError(
            f"same_domain_prior_runs requires domain_scope_key on run {run_id}"
        )

    domain_key = current_run.domain_scope_key

    # Find earlier reconciled provenance_v1 runs with the same domain.
    # Use id < run_id as the primary ordering criterion (deterministic,
    # immune to timestamp precision issues). The created_at check is a
    # secondary guard against unusual ID allocation patterns; using <=
    # avoids excluding prior runs created in the same microsecond.
    prior_runs = session.execute(
        select(PipelineRun.id).where(
            PipelineRun.domain_scope_key == domain_key,
            PipelineRun.provenance_version == "provenance_v1",
            PipelineRun.id != run_id,
            PipelineRun.id < run_id,
            PipelineRun.created_at <= current_run.created_at,
        )
    ).scalars().all()

    if not prior_runs:
        return []

    # Filter to reconciled runs only
    reconciled_runs = set()
    for prior_id in prior_runs:
        rsr = session.execute(
            select(RunSearchReconciliation.status).where(
                RunSearchReconciliation.run_id == prior_id
            )
        ).scalar_one_or_none()
        if rsr == "reconciled":
            reconciled_runs.add(prior_id)

    if not reconciled_runs:
        return []

    rows = session.execute(
        select(RunPaper.paper_id).where(
            RunPaper.run_id.in_(reconciled_runs)
        ).distinct()
    ).all()
    return [r[0] for r in rows]


def _resolve_global_library(session: Session) -> list[int]:
    """Resolve active global-library members."""
    from backend.db.models import GlobalLibraryMembership

    rows = session.execute(
        select(GlobalLibraryMembership.paper_id).where(
            GlobalLibraryMembership.status == "active"
        )
    ).all()
    return [r[0] for r in rows]


def _resolve_selected_papers(
    session: Session, selected_ids: tuple[int, ...],
) -> list[int]:
    """Validate and normalize an explicit paper selection."""
    from backend.db.models import Paper

    if not selected_ids:
        return []

    unique_ids = list(set(selected_ids))
    rows = session.execute(
        select(Paper.id).where(Paper.id.in_(unique_ids))
    ).all()
    found = {r[0] for r in rows}

    missing = set(unique_ids) - found
    if missing:
        raise VectorScopeResolutionError(
            f"selected_papers references unknown paper IDs: {sorted(missing)}"
        )

    return sorted(found)


def _get_domain_scope_key(session: Session, run_id: int) -> str | None:
    """Load the domain_scope_key for a run."""
    from backend.db.models import PipelineRun

    return session.execute(
        select(PipelineRun.domain_scope_key).where(PipelineRun.id == run_id)
    ).scalar_one_or_none()
