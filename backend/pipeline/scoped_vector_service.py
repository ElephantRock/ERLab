"""Scoped vector retrieval service (P0.3.3B-H).

The single governed vector-query boundary. Every retrieval:
  1. Resolves an explicit relational paper scope (P0.3.1)
  2. Freezes the exact eligible indexed vector records
  3. Validates the query vector
  4. Atomically claims the retrieval event
  5. Constrains backend ranking to the frozen candidate set
  6. Validates every returned match against the snapshot
  7. Persists results and terminal status

Empty scopes succeed with zero results (no global fallback).
Strict incomplete coverage fails before backend contact.
"""

from __future__ import annotations

import hashlib
import logging
import math
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import select, update, func
from sqlalchemy.orm import Session, sessionmaker

from backend.pipeline.vector_backend import BackendVectorMatch, GovernedVectorBackend
from backend.pipeline.vector_contracts import (
    VECTOR_INDEX_V1,
    EligibleVectorSnapshot,
    RetrievalAlreadyClaimedError,
    ScopedVectorRetrievalOutcome,
    ScopedVectorRetrievalRequest,
    ScopedVectorResult,
    VectorRetrievalDriftError,
    compute_collection_name,
)
from backend.pipeline.vector_scope import resolve_vector_scope

logger = logging.getLogger(__name__)

# Default batch size for candidate-constrained queries (Chroma $in limit safety).
_DEFAULT_BATCH_SIZE = 500


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _query_vector_fingerprint(query_vector: Sequence[float]) -> str:
    """SHA-256 of canonical float32 byte representation."""
    import struct
    packed = b"".join(struct.pack("<f", float(v)) for v in query_vector)
    return hashlib.sha256(packed).hexdigest()


def _compute_input_fingerprint(
    scope_fingerprint: str,
    embedding_profile_id: str,
    query_fingerprint: str,
    top_k: int,
    allow_partial: bool,
) -> str:
    data = {
        "scope_fingerprint": scope_fingerprint,
        "embedding_profile_id": embedding_profile_id,
        "query_fingerprint": query_fingerprint,
        "top_k": top_k,
        "allow_partial": allow_partial,
    }
    import json
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


# ── Query-vector validation ──────────────────────────────────────────


def validate_query_vector(
    query_vector: Any, expected_dimension: int,
) -> tuple[bool, str | None]:
    """Validate a query vector before any backend query.

    Delegates all structural checks to the canonical
    ``backend.pipeline.knowledge.embedding_validation.validate_embedding_vector``
    so that rejection rules live in exactly one place.

    Returns (is_valid, failure_code). The failure_code is the canonical
    EmbeddingValidationError subclass's ``failure_code`` attribute.
    """
    from backend.pipeline.knowledge.embedding_validation import (
        EmbeddingValidationError,
        validate_embedding_vector,
    )

    try:
        validate_embedding_vector(
            query_vector, expected_dimension=expected_dimension, role="query"
        )
    except EmbeddingValidationError as exc:
        return False, exc.failure_code
    return True, None


def validate_top_k(top_k: int) -> tuple[bool, str | None]:
    if not isinstance(top_k, int) or isinstance(top_k, bool):
        return False, "invalid_top_k"
    if top_k <= 0:
        return False, "invalid_top_k"
    return True, None


# ── Eligible-record resolution ───────────────────────────────────────


def resolve_eligible_records(
    session: Session,
    allowed_paper_ids: Sequence[int],
    embedding_profile_id: str,
    collection_name: str,
) -> list[EligibleVectorSnapshot]:
    """Select the exact indexed vector records for the allowed papers/profile.

    P0.4A2 Final: posture-aware eligibility. If an active binding exists
    for the profile, only v2 records under that binding are eligible. If
    no active binding exists, v1 records remain eligible (pre-capability
    posture). No mixing.
    """
    from backend.db.models import VectorIndexRecord
    from backend.pipeline.capability.capability_bound_retrieval import (
        resolve_retrieval_binding_context,
    )

    if not allowed_paper_ids:
        return []

    # Resolve the current activation posture
    binding_ctx = resolve_retrieval_binding_context(session, embedding_profile_id)

    if binding_ctx.active_binding_id is not None:
        # Post-activation: only v2 records under the active binding
        rows = session.execute(
            select(
                VectorIndexRecord.vector_record_id,
                VectorIndexRecord.paper_id,
                VectorIndexRecord.chunk_key,
                VectorIndexRecord.content_kind,
                VectorIndexRecord.collection_name,
                VectorIndexRecord.embedding_profile_id,
            ).where(
                VectorIndexRecord.index_status == "indexed",
                VectorIndexRecord.embedding_profile_id == embedding_profile_id,
                VectorIndexRecord.index_schema_version == "vector_index_v2",
                VectorIndexRecord.capability_binding_id == binding_ctx.active_binding_id,
                VectorIndexRecord.paper_id.in_(list(allowed_paper_ids)),
            ).order_by(VectorIndexRecord.vector_record_id)
        ).all()
    else:
        # Pre-activation: v1 records remain eligible
        rows = session.execute(
            select(
                VectorIndexRecord.vector_record_id,
                VectorIndexRecord.paper_id,
                VectorIndexRecord.chunk_key,
                VectorIndexRecord.content_kind,
                VectorIndexRecord.collection_name,
                VectorIndexRecord.embedding_profile_id,
            ).where(
                VectorIndexRecord.index_status == "indexed",
                VectorIndexRecord.embedding_profile_id == embedding_profile_id,
                VectorIndexRecord.index_schema_version == VECTOR_INDEX_V1,
                VectorIndexRecord.collection_name == collection_name,
                VectorIndexRecord.paper_id.in_(list(allowed_paper_ids)),
            ).order_by(VectorIndexRecord.vector_record_id)
        ).all()

    return [
        EligibleVectorSnapshot(
            vector_record_id=r[0],
            paper_id=r[1],
            chunk_key=r[2],
            content_kind=r[3],
            collection_name=r[4],
            embedding_profile_id=r[5],
        )
        for r in rows
    ]


# ── Scoped retrieval ─────────────────────────────────────────────────


async def query_vectors(
    *,
    session_factory: sessionmaker,
    backend: GovernedVectorBackend,
    request: ScopedVectorRetrievalRequest,
) -> ScopedVectorRetrievalOutcome:
    """Execute a governed scoped vector retrieval.

    Full lifecycle:
      1. Resolve scope + freeze eligible records
      2. Validate query vector + top_k
      3. Check replay/drift on existing events
      4. Create event + snapshot tables
      5. Coverage gate (empty, strict-incomplete, partial, complete)
      6. Atomic claim
      7. Backend query (candidate-constrained, batched)
      8. Validate results
      9. Persist results + terminal status
    """
    from backend.db.models import (
        EmbeddingProfile,
        VectorRetrievalEligibleRecord,
        VectorRetrievalEvent,
        VectorRetrievalResult,
        VectorRetrievalScopePaper,
    )

    # ── 1. Resolve scope ──
    session = session_factory()
    try:
        scope = resolve_vector_scope(session, request.scope)
        allowed_paper_ids = set(scope.allowed_paper_ids)

        # Load profile for dimension + collection
        profile = session.execute(
            select(EmbeddingProfile).where(
                EmbeddingProfile.profile_id == request.scope.embedding_profile_id
            )
        ).scalar_one_or_none()
        if profile is None:
            raise ValueError(
                f"embedding profile {request.scope.embedding_profile_id[:12]}... not registered"
            )

        collection_name = profile.collection_name

        # Resolve eligible records
        eligible = resolve_eligible_records(
            session, allowed_paper_ids, request.scope.embedding_profile_id, collection_name,
        )

        # Compute coverage
        indexed_paper_ids = {e.paper_id for e in eligible}
        allowed_count = len(allowed_paper_ids)
        indexed_count = len(indexed_paper_ids)
        unindexed_count = allowed_count - indexed_count
        eligible_count = len(eligible)

        if allowed_count == 0:
            coverage_status = "empty_scope"
        elif indexed_count == 0:
            coverage_status = "none"
        elif unindexed_count == 0:
            coverage_status = "complete"
        else:
            coverage_status = "partial"

        # ── 2. Validate query vector ──
        ok, code = validate_query_vector(request.query_vector, profile.dimension)
        if not ok:
            # Persist failed event
            _persist_failed_event(
                session_factory, request, scope, eligible,
                allowed_count, indexed_count, unindexed_count, eligible_count,
                coverage_status, collection_name, profile,
                "query_validation", code,
            )
            raise ValueError(f"query vector validation failed: {code}")

        ok, code = validate_top_k(request.top_k)
        if not ok:
            _persist_failed_event(
                session_factory, request, scope, eligible,
                allowed_count, indexed_count, unindexed_count, eligible_count,
                coverage_status, collection_name, profile,
                "query_validation", code,
            )
            raise ValueError(f"invalid top_k: {code}")

        qvf = _query_vector_fingerprint(request.query_vector)
        input_fp = _compute_input_fingerprint(
            scope.scope_fingerprint, request.scope.embedding_profile_id,
            qvf, request.top_k, request.allow_partial_index_coverage,
        )

        # ── 3. Check replay/drift ──
        existing = session.execute(
            select(VectorRetrievalEvent).where(
                VectorRetrievalEvent.run_id == request.run_id,
                VectorRetrievalEvent.stage_name == request.stage_name,
                VectorRetrievalEvent.retrieval_key == request.retrieval_key,
            )
        ).scalar_one_or_none()

        if existing is not None:
            if existing.status == "success" and existing.input_fingerprint == input_fp:
                # Replay — return stored results
                stored = session.execute(
                    select(VectorRetrievalResult).where(
                        VectorRetrievalResult.retrieval_event_id == existing.id
                    ).order_by(VectorRetrievalResult.rank)
                ).scalars().all()
                results = tuple(
                    ScopedVectorResult(
                        vector_record_id=r.vector_record_id,
                        paper_id=_get_paper_id_for(session, r.vector_record_id),
                        chunk_key=_get_chunk_key_for(session, r.vector_record_id),
                        content_kind="",
                        raw_score=r.canonical_distance,
                        rank=r.rank,
                    )
                    for r in stored
                )
                session.commit()
                return ScopedVectorRetrievalOutcome(
                    retrieval_event_id=existing.id,
                    status="replayed",
                    coverage_status=existing.coverage_status,
                    allowed_paper_count=existing.allowed_paper_count,
                    indexed_paper_count=existing.indexed_paper_count,
                    eligible_vector_record_count=existing.eligible_vector_record_count,
                    results=results,
                )
            elif existing.input_fingerprint != input_fp:
                session.rollback()
                raise VectorRetrievalDriftError(
                    f"retrieval drift for {request.run_id}/{request.stage_name}/{request.retrieval_key}"
                )
            elif existing.status == "failed":
                # Previous attempt failed with same inputs — retry by
                # reusing the existing event row instead of inserting a
                # duplicate (which would violate the UNIQUE constraint).
                # Clear any partial results from the failed attempt.
                session.execute(
                    text(
                        "DELETE FROM vector_retrieval_results "
                        "WHERE retrieval_event_id = :eid"
                    ),
                    {"eid": existing.id},
                )
                event = existing  # reuse the row
                event.status = "pending"
                event.attempt_count = (event.attempt_count or 0) + 1
                session.flush()
                event_id = event.id
                # Skip to the retrieval step (step 5+)
                # by jumping past the event creation below.
                # We achieve this by setting a flag that the code below checks.
                _reusing_failed_event = True
            else:
                _reusing_failed_event = False

        if not _reusing_failed_event:
            # ── 4. Create event + snapshots ──
            # P0.4A2 Final: record capability evidence on the retrieval event
            from backend.pipeline.capability.capability_bound_retrieval import (
                resolve_retrieval_binding_context as _resolve_ctx,
            )
            _binding_ctx = _resolve_ctx(session, request.scope.embedding_profile_id)

            event = VectorRetrievalEvent(
                run_id=request.run_id,
                stage_name=request.stage_name,
                retrieval_key=request.retrieval_key,
                request_schema_version="vector_retrieval_v1",
                scope_mode=request.scope.mode,
                scope_schema_version=request.scope.schema_version,
                scope_fingerprint=scope.scope_fingerprint,
                embedding_profile_id=request.scope.embedding_profile_id,
                profile_verification_status_snapshot=profile.verification_status,
                query_vector_fingerprint=qvf,
                input_fingerprint=input_fp,
                requested_top_k=request.top_k,
                allow_partial_index_coverage=request.allow_partial_index_coverage,
                allowed_paper_count=allowed_count,
                indexed_paper_count=indexed_count,
                unindexed_paper_count=unindexed_count,
                eligible_vector_record_count=eligible_count,
                coverage_status=coverage_status,
                status="pending",
                # P0.4A2: capability contract evidence
                query_embedding_contract_version="capability_v1",
                vector_eligibility_contract_version=_binding_ctx.vector_eligibility_contract_version,
                query_capability_binding_id=_binding_ctx.active_binding_id,
                query_capability_check_id=None,  # populated when query receipt is available
                binding_activation_id=_binding_ctx.activation_id,
            )
            session.add(event)
            session.flush()
            event_id = event.id

            # Snapshot allowed papers (only for new events)
            for pid in allowed_paper_ids:
                session.add(VectorRetrievalScopePaper(
                    retrieval_event_id=event_id,
                    paper_id=pid,
                    is_indexed=pid in indexed_paper_ids,
                ))

            # Snapshot eligible records (only for new events)
            for e in eligible:
                session.add(VectorRetrievalEligibleRecord(
                    retrieval_event_id=event_id,
                    vector_record_id=e.vector_record_id,
                ))
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    # ── 5. Coverage gate ──
    if coverage_status == "empty_scope":
        # Success with zero results — no backend call
        _mark_event_success(session_factory, event_id, 0, 0)
        return ScopedVectorRetrievalOutcome(
            retrieval_event_id=event_id, status="success",
            coverage_status="empty_scope",
            allowed_paper_count=0, indexed_paper_count=0,
            eligible_vector_record_count=0, results=(),
        )

    if coverage_status == "none":
        # No indexed records — success with zero results (partial coverage allowed)
        if request.allow_partial_index_coverage:
            _mark_event_success(session_factory, event_id, 0, 0)
            return ScopedVectorRetrievalOutcome(
                retrieval_event_id=event_id, status="success",
                coverage_status="none",
                allowed_paper_count=allowed_count, indexed_paper_count=0,
                eligible_vector_record_count=0, results=(),
            )
        else:
            _mark_event_failed(session_factory, event_id,
                               "index_coverage", "index_coverage_incomplete",
                               f"0/{allowed_count} papers indexed")
            raise ValueError("index_coverage_incomplete")

    if coverage_status == "partial" and not request.allow_partial_index_coverage:
        _mark_event_failed(session_factory, event_id,
                           "index_coverage", "index_coverage_incomplete",
                           f"{indexed_count}/{allowed_count} papers indexed")
        raise ValueError("index_coverage_incomplete")

    # ── 6. Atomic claim ──
    session = session_factory()
    try:
        claim = session.execute(
            update(VectorRetrievalEvent)
            .where(
                VectorRetrievalEvent.id == event_id,
                VectorRetrievalEvent.status.in_(["pending", "failed"]),
            )
            .values(
                status="running",
                attempt_count=VectorRetrievalEvent.attempt_count + 1,
                started_at=_now(),
            )
        )
        if claim.rowcount != 1:
            raise RetrievalAlreadyClaimedError(
                f"retrieval event {event_id} already claimed"
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    # ── 7. Backend query (candidate-constrained, batched) ──
    eligible_ids = sorted(e.vector_record_id for e in eligible)
    eligible_set = set(eligible_ids)
    eligible_map = {e.vector_record_id: e for e in eligible}

    all_matches: list[BackendVectorMatch] = []
    batch_count = 0

    for i in range(0, len(eligible_ids), _DEFAULT_BATCH_SIZE):
        batch = eligible_ids[i:i + _DEFAULT_BATCH_SIZE]
        batch_count += 1
        matches = backend.query_vectors(
            collection_name=collection_name,
            query_vector=request.query_vector,
            candidate_vector_record_ids=batch,
            top_k=request.top_k,
        )
        all_matches.extend(matches)

    # ── 8. Validate results ──
    for match in all_matches:
        if match.vector_record_id not in eligible_set:
            _mark_event_failed(session_factory, event_id,
                               "result_validation", "backend_scope_violation",
                               f"vector {match.vector_record_id[:12]} not in eligible snapshot")
            raise ValueError(f"backend_scope_violation: {match.vector_record_id[:12]}")

        snap = eligible_map[match.vector_record_id]
        if match.paper_id != snap.paper_id:
            _mark_event_failed(session_factory, event_id,
                               "result_validation", "backend_metadata_mismatch",
                               f"paper_id mismatch for {match.vector_record_id[:12]}")
            raise ValueError("backend_metadata_mismatch: paper_id")

        if math.isnan(match.canonical_distance) or math.isinf(match.canonical_distance):
            _mark_event_failed(session_factory, event_id,
                               "result_validation", "backend_distance_invalid",
                               f"non-finite distance for {match.vector_record_id[:12]}")
            raise ValueError("backend_distance_invalid")

    # Check for duplicates
    seen_ids: set[str] = set()
    for match in all_matches:
        if match.vector_record_id in seen_ids:
            _mark_event_failed(session_factory, event_id,
                               "result_validation", "backend_duplicate_result",
                               f"duplicate {match.vector_record_id[:12]}")
            raise ValueError("backend_duplicate_result")
        seen_ids.add(match.vector_record_id)

    # Trim to top_k with deterministic ordering
    all_matches.sort(key=lambda m: (
        m.canonical_distance,
        m.paper_id,
        m.chunk_key,
        m.vector_record_id,
    ))
    top_matches = all_matches[:request.top_k]

    # ── 9. Persist results + terminal status ──
    session = session_factory()
    try:
        for rank, match in enumerate(top_matches, 1):
            session.add(VectorRetrievalResult(
                retrieval_event_id=event_id,
                rank=rank,
                vector_record_id=match.vector_record_id,
                canonical_distance=match.canonical_distance,
            ))

        session.execute(
            update(VectorRetrievalEvent)
            .where(VectorRetrievalEvent.id == event_id)
            .values(
                status="success",
                returned_result_count=len(top_matches),
                backend_batch_count=batch_count,
                completed_at=_now(),
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    results = tuple(
        ScopedVectorResult(
            vector_record_id=m.vector_record_id,
            paper_id=m.paper_id,
            chunk_key=m.chunk_key,
            content_kind=m.content_kind,
            raw_score=m.canonical_distance,
            rank=i,
        )
        for i, m in enumerate(top_matches, 1)
    )

    return ScopedVectorRetrievalOutcome(
        retrieval_event_id=event_id, status="success",
        coverage_status=coverage_status,
        allowed_paper_count=allowed_count,
        indexed_paper_count=indexed_count,
        eligible_vector_record_count=eligible_count,
        results=results,
    )


def _get_paper_id_for(session: Session, vector_record_id: str) -> int:
    from backend.db.models import VectorIndexRecord
    return session.execute(
        select(VectorIndexRecord.paper_id).where(
            VectorIndexRecord.vector_record_id == vector_record_id
        )
    ).scalar() or 0


def _get_chunk_key_for(session: Session, vector_record_id: str) -> str:
    from backend.db.models import VectorIndexRecord
    return session.execute(
        select(VectorIndexRecord.chunk_key).where(
            VectorIndexRecord.vector_record_id == vector_record_id
        )
    ).scalar() or ""


def _mark_event_success(
    session_factory: sessionmaker,
    event_id: int,
    result_count: int,
    batch_count: int,
) -> None:
    from backend.db.models import VectorRetrievalEvent
    session = session_factory()
    try:
        session.execute(
            update(VectorRetrievalEvent)
            .where(VectorRetrievalEvent.id == event_id)
            .values(
                status="success",
                returned_result_count=result_count,
                backend_batch_count=batch_count,
                completed_at=_now(),
            )
        )
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


def _mark_event_failed(
    session_factory: sessionmaker,
    event_id: int,
    category: str,
    code: str,
    detail: str,
) -> None:
    from backend.db.models import VectorRetrievalEvent
    session = session_factory()
    try:
        session.execute(
            update(VectorRetrievalEvent)
            .where(VectorRetrievalEvent.id == event_id)
            .values(
                status="failed",
                failure_category=category,
                failure_code=code,
                failure_detail=detail[:500],
                completed_at=_now(),
            )
        )
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


def _persist_failed_event(
    session_factory: sessionmaker,
    request: ScopedVectorRetrievalRequest,
    scope,
    eligible,
    allowed_count, indexed_count, unindexed_count, eligible_count,
    coverage_status, collection_name, profile,
    category: str, code: str,
) -> None:
    """Persist a failed event for query-validation failures."""
    from backend.db.models import (
        VectorRetrievalEligibleRecord,
        VectorRetrievalEvent,
        VectorRetrievalScopePaper,
    )

    session = session_factory()
    try:
        qvf = _query_vector_fingerprint(request.query_vector)
        input_fp = _compute_input_fingerprint(
            scope.scope_fingerprint, request.scope.embedding_profile_id,
            qvf, request.top_k, request.allow_partial_index_coverage,
        )

        event = VectorRetrievalEvent(
            run_id=request.run_id,
            stage_name=request.stage_name,
            retrieval_key=request.retrieval_key,
            request_schema_version="vector_retrieval_v1",
            scope_mode=request.scope.mode,
            scope_schema_version=request.scope.schema_version,
            scope_fingerprint=scope.scope_fingerprint,
            embedding_profile_id=request.scope.embedding_profile_id,
            profile_verification_status_snapshot=profile.verification_status,
            query_vector_fingerprint=qvf,
            input_fingerprint=input_fp,
            requested_top_k=request.top_k,
            allow_partial_index_coverage=request.allow_partial_index_coverage,
            allowed_paper_count=allowed_count,
            indexed_paper_count=indexed_count,
            unindexed_paper_count=unindexed_count,
            eligible_vector_record_count=eligible_count,
            coverage_status=coverage_status,
            status="failed",
            failure_category=category,
            failure_code=code,
            failure_detail=f"query validation failed: {code}",
            completed_at=_now(),
        )
        session.add(event)
        session.flush()

        for pid in scope.allowed_paper_ids:
            session.add(VectorRetrievalScopePaper(
                retrieval_event_id=event.id, paper_id=pid,
                is_indexed=pid in {e.paper_id for e in eligible},
            ))
        for e in eligible:
            session.add(VectorRetrievalEligibleRecord(
                retrieval_event_id=event.id, vector_record_id=e.vector_record_id,
            ))
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()
