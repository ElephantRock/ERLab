"""Capability-bound scoped retrieval contracts (P0.4A2.4).

Introduces a frozen retrieval posture snapshot and active-binding
resolution logic.

  RetrievalBindingContext
      Frozen snapshot resolved once at retrieval start.

  resolve_retrieval_binding_context(session, profile_id)
      Determine the current persistent-vector posture:
        no active activation → pre_capability_v0 eligibility
        one active activation → capability_v1 eligibility for that binding

  Before first activation:
    vector eligibility = pre_capability_v0
    query embedding = capability_v1 (the runtime is verified)
    query binding/check recorded
    eligible vector bindings remain unknown

  After activation:
    active binding resolved → query only active binding collection →
    snapshot only vector_index_v2 rows for active binding →
    validate all returned rows → persist exact evidence

Hard rejection:
    active binding A, query receipt binding B → fail before backend query
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import EmbeddingProfileBindingActivation
from backend.pipeline.vector_contracts import (
    EMBEDDING_CONTRACT_CAPABILITY_V1,
    EMBEDDING_CONTRACT_PRE_CAPABILITY_V0,
)

# ── Activation statuses ───────────────────────────────────────────────

ACTIVATION_CANDIDATE = "candidate"
ACTIVATION_ACTIVE = "active"
ACTIVATION_RETIRED = "retired"
ACTIVATION_REJECTED = "rejected"


@dataclass(frozen=True)
class RetrievalBindingContext:
    """Frozen retrieval posture snapshot.

    Resolved once at retrieval start. A retrieval pins one posture and
    completes under it even if activation changes concurrently, provided
    every step uses the same binding and collection.
    """

    embedding_profile_id: str
    vector_eligibility_contract_version: str
    active_binding_id: str | None
    activation_id: str | None
    activation_generation: int | None


@dataclass(frozen=True)
class QueryRetrievalEvidence:
    """Capability evidence for a query embedding.

    Captured from the AuthorizedQueryEmbedding receipt and the
    RetrievalBindingContext.
    """

    query_embedding_contract_version: str
    query_capability_binding_id: str | None
    query_capability_check_id: str | None
    binding_activation_id: str | None


class RetrievalBindingMismatch(Exception):
    """Query binding ≠ active binding — fail before backend query."""

    def __init__(self, query_binding: str, active_binding: str):
        self.query_binding = query_binding
        self.active_binding = active_binding
        super().__init__(
            f"query binding {query_binding[:16]}... != active binding "
            f"{active_binding[:16]}..."
        )


def resolve_retrieval_binding_context(
    session: Session,
    embedding_profile_id: str,
) -> RetrievalBindingContext:
    """Resolve the current persistent-vector posture for a profile.

    No active activation → pre_capability_v0 eligibility (historical
    vectors under the P0.3 contract).

    One active activation → capability_v1 eligibility for that binding
    only.
    """
    active_activation = session.execute(
        select(EmbeddingProfileBindingActivation).where(
            EmbeddingProfileBindingActivation.embedding_profile_id == embedding_profile_id,
            EmbeddingProfileBindingActivation.status == ACTIVATION_ACTIVE,
        )
    ).scalar_one_or_none()

    if active_activation is None:
        return RetrievalBindingContext(
            embedding_profile_id=embedding_profile_id,
            vector_eligibility_contract_version=EMBEDDING_CONTRACT_PRE_CAPABILITY_V0,
            active_binding_id=None,
            activation_id=None,
            activation_generation=None,
        )

    return RetrievalBindingContext(
        embedding_profile_id=embedding_profile_id,
        vector_eligibility_contract_version=EMBEDDING_CONTRACT_CAPABILITY_V1,
        active_binding_id=active_activation.capability_binding_id,
        activation_id=active_activation.activation_id,
        activation_generation=active_activation.activation_generation,
    )


def build_query_retrieval_evidence(
    *,
    query_binding_id: str | None,
    query_check_id: str | None,
    binding_context: RetrievalBindingContext,
) -> QueryRetrievalEvidence:
    """Build query retrieval evidence from receipt + context.

    If the binding context has an active binding, the query binding
    must match it. If not, the query is capability_v1 but the vectors
    remain pre_capability_v0 (transitional posture).
    """
    if binding_context.active_binding_id is not None:
        # After activation: query binding MUST match active binding
        if query_binding_id is not None and query_binding_id != binding_context.active_binding_id:
            raise RetrievalBindingMismatch(
                query_binding_id, binding_context.active_binding_id
            )
        return QueryRetrievalEvidence(
            query_embedding_contract_version=EMBEDDING_CONTRACT_CAPABILITY_V1,
            query_capability_binding_id=query_binding_id,
            query_capability_check_id=query_check_id,
            binding_activation_id=binding_context.activation_id,
        )

    # Before activation: query is capability_v1, vectors are v0
    return QueryRetrievalEvidence(
        query_embedding_contract_version=EMBEDDING_CONTRACT_CAPABILITY_V1,
        query_capability_binding_id=query_binding_id,
        query_capability_check_id=query_check_id,
        binding_activation_id=None,
    )


def is_vector_eligible_for_retrieval(
    *,
    vector_binding_id: str | None,
    vector_contract_version: str,
    binding_context: RetrievalBindingContext,
) -> bool:
    """Check if a vector is eligible for retrieval under the current posture.

    Before activation:
      pre_capability_v0 vectors are eligible
      capability_v1 vectors (candidate) are NOT eligible

    After activation:
      capability_v1 vectors under the active binding are eligible
      pre_capability_v0 vectors are NOT eligible (no fallback)
      capability_v1 vectors under a different binding are NOT eligible
    """
    if binding_context.active_binding_id is None:
        # Pre-activation: only v0 vectors eligible
        return vector_contract_version == EMBEDDING_CONTRACT_PRE_CAPABILITY_V0

    # Post-activation: only active-binding v2 vectors eligible
    if vector_contract_version != EMBEDDING_CONTRACT_CAPABILITY_V1:
        return False
    return vector_binding_id == binding_context.active_binding_id
