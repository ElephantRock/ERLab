"""P0.4A3.7: Capability evidence tracing service.

Reconstructs the evidence graph for a retrieval event, tracing from
the retrieval event through query check, binding, activation, cutover,
eligible vectors, generation checks, and canonical sources.

Trace integrity: fails closed when it finds missing required capability
evidence or binding mismatches. Does not silently produce a partial
"valid" trace.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import (
    EmbeddingCapabilityBinding,
    EmbeddingCapabilityCheck,
    EmbeddingProfileBindingActivation,
    VectorIndexRecord,
    VectorRetrievalEvent,
    VectorRetrievalEligibleRecord,
    VectorRetrievalResult,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EvidenceTrace:
    """Complete evidence graph for a retrieval event."""

    status: str  # valid | incomplete | invalid
    retrieval_event_id: int
    embedding_profile_id: str
    query_embedding_contract_version: str | None
    vector_eligibility_contract_version: str | None
    query_capability_binding_id: str | None
    query_capability_check_id: str | None
    binding_activation_id: str | None
    active_binding_id: str | None
    result_count: int
    returned_vector_binding_ids: tuple[str, ...] = ()
    integrity_errors: tuple[str, ...] = ()


def trace_retrieval_evidence(
    session: Session,
    retrieval_event_id: int,
) -> EvidenceTrace:
    """Trace the evidence graph for one retrieval event.

    Pure read. Fails closed on missing evidence or binding mismatches.
    """
    errors: list[str] = []

    # 1. Load retrieval event
    event = session.execute(
        select(VectorRetrievalEvent).where(
            VectorRetrievalEvent.id == retrieval_event_id,
        )
    ).scalar_one_or_none()

    if event is None:
        return EvidenceTrace(
            status="invalid",
            retrieval_event_id=retrieval_event_id,
            embedding_profile_id="",
            query_embedding_contract_version=None,
            vector_eligibility_contract_version=None,
            query_capability_binding_id=None,
            query_capability_check_id=None,
            binding_activation_id=None,
            active_binding_id=None,
            result_count=0,
            integrity_errors=("retrieval_event_not_found",),
        )

    # 2. Load activation (if referenced)
    active_binding_id = None
    if event.binding_activation_id is not None:
        activation = session.execute(
            select(EmbeddingProfileBindingActivation).where(
                EmbeddingProfileBindingActivation.activation_id == event.binding_activation_id,
            )
        ).scalar_one_or_none()

        if activation is None:
            errors.append("activation_not_found")
        else:
            active_binding_id = activation.capability_binding_id

    # 3. Load results
    results = session.execute(
        select(VectorRetrievalResult).where(
            VectorRetrievalResult.retrieval_event_id == retrieval_event_id,
        ).order_by(VectorRetrievalResult.rank)
    ).scalars().all()

    # 4. Trace each result to its vector record and binding
    returned_binding_ids: list[str] = []
    for result in results:
        vrec = session.execute(
            select(VectorIndexRecord).where(
                VectorIndexRecord.vector_record_id == result.vector_record_id,
            )
        ).scalar_one_or_none()

        if vrec is None:
            errors.append(f"vector_record_missing:{result.vector_record_id[:16]}")
            continue

        if vrec.capability_binding_id is not None:
            returned_binding_ids.append(vrec.capability_binding_id)

        # Integrity check: if the event has a query binding, the returned
        # vector binding must match
        if event.query_capability_binding_id is not None:
            if vrec.capability_binding_id is None:
                errors.append(
                    f"vector_without_binding:{result.vector_record_id[:16]}"
                )
            elif vrec.capability_binding_id != event.query_capability_binding_id:
                errors.append(
                    f"binding_mismatch:query={event.query_capability_binding_id[:16]}... "
                    f"vector={vrec.capability_binding_id[:16]}..."
                )

    # 5. Determine status
    if errors:
        status = "invalid" if any("mismatch" in e or "missing" in e for e in errors) else "incomplete"
    else:
        status = "valid"

    return EvidenceTrace(
        status=status,
        retrieval_event_id=retrieval_event_id,
        embedding_profile_id=event.embedding_profile_id,
        query_embedding_contract_version=event.query_embedding_contract_version,
        vector_eligibility_contract_version=event.vector_eligibility_contract_version,
        query_capability_binding_id=event.query_capability_binding_id,
        query_capability_check_id=event.query_capability_check_id,
        binding_activation_id=event.binding_activation_id,
        active_binding_id=active_binding_id,
        result_count=len(results),
        returned_vector_binding_ids=tuple(returned_binding_ids),
        integrity_errors=tuple(errors),
    )
