"""Capability binding repository (P0.4A1.2).

Idempotent creation of immutable capability bindings.

  resolve_or_create_binding(session, decision) -> str
      Accepts a ``ResolutionDecision`` (produced by ``classify_resolution``
      after a successful probe). If a binding with the same identity
      already exists, returns its ID. If not, creates a new immutable
      binding row and returns its ID.

      Raises ``CapabilityBindingDriftError`` if a binding exists for the
      same profile but with different resolved fields — this indicates
      corruption (the same profile should always resolve to the same
      binding under a given classifier version).

Bindings are insert-only. There is no UPDATE path in this repository.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import EmbeddingCapabilityBinding
from backend.pipeline.capability.capability_identity import (
    compute_capability_binding_id,
)
from backend.pipeline.capability.capability_resolution import ResolutionDecision
from backend.pipeline.vector_contracts import (
    CAPABILITY_BINDING_SCHEMA_V1,
    RESOLUTION_CLASSIFIER_V1,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class CapabilityBindingDriftError(Exception):
    """A binding exists for the same profile but with different resolved
    fields. Indicates corruption or classifier version mismatch."""

    def __init__(self, profile_id: str, existing_binding_id: str, computed_binding_id: str):
        self.profile_id = profile_id
        self.existing_binding_id = existing_binding_id
        self.computed_binding_id = computed_binding_id
        super().__init__(
            f"binding drift for profile {profile_id[:16]}...: "
            f"existing={existing_binding_id[:16]}... "
            f"computed={computed_binding_id[:16]}..."
        )


def resolve_or_create_binding(
    session: Session,
    decision: ResolutionDecision,
) -> str:
    """Idempotently resolve or create an immutable capability binding.

    Returns the ``binding_id``. The binding is insert-only — once created,
    it is never updated. If a binding with the same deterministic identity
    already exists, it is returned as-is.

    Raises ``CapabilityBindingDriftError`` if a binding exists for the
    same profile but with a different identity (different resolved fields
    under the same classifier).
    """
    bi = decision.binding_input
    computed_id = compute_capability_binding_id(
        embedding_profile_id=bi.embedding_profile_id,
        profile_schema_version=bi.profile_schema_version,
        provider_kind=bi.provider_kind,
        resolved_model=bi.resolved_model,
        provider_revision=bi.provider_revision,
        model_resolution_posture=bi.model_resolution_posture,
        resolved_deployment_id=bi.resolved_deployment_id,
        resolved_document_task=bi.resolved_document_task,
        resolved_query_task=bi.resolved_query_task,
        resolved_dimension=bi.resolved_dimension,
        resolved_normalization=bi.resolved_normalization,
        postprocessing_contract_version=bi.postprocessing_contract_version,
        sanitized_endpoint_identity=bi.sanitized_endpoint_identity,
        provider_adapter_contract_version=bi.provider_adapter_contract_version,
        governed_adapter_contract_version=bi.governed_adapter_contract_version,
        resolution_classifier_version=RESOLUTION_CLASSIFIER_V1,
    )

    # Check if this exact binding already exists
    existing = session.execute(
        select(EmbeddingCapabilityBinding).where(
            EmbeddingCapabilityBinding.binding_id == computed_id
        )
    ).scalar_one_or_none()

    if existing is not None:
        logger.debug(
            "capability binding resolved (existing): %s...",
            computed_id[:16],
        )
        return computed_id

    # Check for drift: does a binding exist for the same profile with a
    # different identity? This should not happen under deterministic
    # resolution but catches corruption.
    profile_binding = session.execute(
        select(EmbeddingCapabilityBinding).where(
            EmbeddingCapabilityBinding.embedding_profile_id == bi.embedding_profile_id
        )
    ).scalar_one_or_none()

    if profile_binding is not None and profile_binding.binding_id != computed_id:
        raise CapabilityBindingDriftError(
            profile_id=bi.embedding_profile_id,
            existing_binding_id=profile_binding.binding_id,
            computed_binding_id=computed_id,
        )

    # Create the new immutable binding
    binding = EmbeddingCapabilityBinding(
        binding_id=computed_id,
        embedding_profile_id=bi.embedding_profile_id,
        provider_kind=bi.provider_kind,
        resolved_model=bi.resolved_model,
        provider_revision=bi.provider_revision,
        model_resolution_posture=bi.model_resolution_posture,
        resolved_document_task=bi.resolved_document_task,
        resolved_query_task=bi.resolved_query_task,
        resolved_dimension=bi.resolved_dimension,
        resolved_normalization=bi.resolved_normalization,
        postprocessing_contract_version=bi.postprocessing_contract_version,
        resolved_endpoint_identity=bi.sanitized_endpoint_identity,
        resolved_deployment_id=bi.resolved_deployment_id,
        profile_schema_version=bi.profile_schema_version,
        provider_adapter_contract_version=bi.provider_adapter_contract_version,
        governed_adapter_contract_version=bi.governed_adapter_contract_version,
        resolution_classifier_version=RESOLUTION_CLASSIFIER_V1,
        binding_schema_version=CAPABILITY_BINDING_SCHEMA_V1,
    )
    session.add(binding)
    session.flush()  # detect constraint violations before commit
    logger.info(
        "capability binding created: %s... (posture=%s, provider=%s, model=%s, dim=%d)",
        computed_id[:16],
        decision.posture,
        bi.provider_kind,
        bi.resolved_model,
        bi.resolved_dimension,
    )
    return computed_id
