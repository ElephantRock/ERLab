"""Capability identity contracts (P0.4A1.2).

Deterministic identity functions for the capability ledger:

  compute_runtime_config_fingerprint
      Canonical SHA-256 over every reconciled field that defines the
      embedding operation. Stored on each check so authorization can
      detect drift without re-deriving the binding.

  compute_capability_binding_id
      Deterministic SHA-256 over ALL semantic-space-defining fields.
      Covers profile, provider, model, revision, posture, tasks,
      dimension, normalization, post-processing, endpoint, deployment,
      contracts, and classifier version. Two runtimes that share a
      provider+model+dimension but differ in any other field produce
      distinct bindings. check_id and timestamps do NOT participate.

  compute_check_id
      UUID4 hex — each probe is a distinct event.

  compute_check_expiry
      probed_at + ttl_seconds, returned as a timezone-aware datetime.

Frozen rule:
  The capability check ID and timestamps must not participate in binding
  identity. A binding identifies a semantic space, not a probe event.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from backend.pipeline.vector_contracts import (
    CAPABILITY_BINDING_SCHEMA_V1,
    RESOLUTION_CLASSIFIER_V1,
    RUNTIME_CONFIG_FINGERPRINT_V1,
)

if TYPE_CHECKING:
    from backend.pipeline.knowledge.embedding_configuration import (
        EffectiveEmbeddingConfiguration,
    )


def _canonical_json(payload: dict) -> str:
    """Deterministic JSON encoding for hashing."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_runtime_config_fingerprint(
    effective_config: EffectiveEmbeddingConfiguration,
) -> str:
    """Canonical SHA-256 over every reconciled runtime field.

    Covers ALL fields that define the embedding operation:
    profile identity, provider, model, dimension, normalization,
    post-processing, tasks, endpoint, deployment, contract versions.

    Versioned by ``RUNTIME_CONFIG_FINGERPRINT_V1`` so that changing
    the fingerprint algorithm produces a different hash.
    """
    payload = {
        "fingerprint_version": RUNTIME_CONFIG_FINGERPRINT_V1,
        "embedding_profile_id": effective_config.embedding_profile_id,
        "profile_schema_version": effective_config.profile_schema_version,
        "provider_kind": effective_config.provider_kind,
        "requested_model": effective_config.requested_model,
        "expected_dimension": effective_config.expected_dimension,
        "declared_normalization_policy": effective_config.declared_normalization_policy,
        "implemented_postprocessing_policy": effective_config.implemented_postprocessing_policy,
        "document_task": effective_config.document_task,
        "query_task": effective_config.query_task,
        "sanitized_endpoint_identity": effective_config.sanitized_endpoint_identity,
        "configured_deployment_id": effective_config.configured_deployment_id,
        "deployment_is_explicitly_pinned": effective_config.deployment_is_explicitly_pinned,
        "provider_adapter_contract_version": effective_config.provider_adapter_contract_version,
        "governed_adapter_contract_version": effective_config.governed_adapter_contract_version,
    }
    return hashlib.sha256(_canonical_json(payload).encode()).hexdigest()


def compute_capability_binding_id(
    *,
    embedding_profile_id: str,
    profile_schema_version: str,
    provider_kind: str,
    resolved_model: str,
    provider_revision: str | None,
    model_resolution_posture: str,
    resolved_deployment_id: str | None,
    resolved_document_task: str | None,
    resolved_query_task: str | None,
    resolved_dimension: int,
    resolved_normalization: str,
    postprocessing_contract_version: str,
    sanitized_endpoint_identity: str,
    provider_adapter_contract_version: str,
    governed_adapter_contract_version: str,
    resolution_classifier_version: str = RESOLUTION_CLASSIFIER_V1,
) -> str:
    """Deterministic binding identity from resolved probe evidence.

    Covers ALL semantic-space-defining fields. Two runtimes that share
    provider+model+dimension but differ in any other field produce
    distinct bindings.

    check_id and timestamps do NOT participate — a binding identifies a
    semantic space, not a probe event.
    """
    payload = {
        "binding_schema_version": CAPABILITY_BINDING_SCHEMA_V1,
        "embedding_profile_id": embedding_profile_id,
        "profile_schema_version": profile_schema_version,
        "provider_kind": provider_kind,
        "resolved_model": resolved_model,
        "provider_revision": provider_revision,
        "model_resolution_posture": model_resolution_posture,
        "resolved_deployment_id": resolved_deployment_id,
        "resolved_document_task": resolved_document_task,
        "resolved_query_task": resolved_query_task,
        "resolved_dimension": resolved_dimension,
        "resolved_normalization": resolved_normalization,
        "postprocessing_contract_version": postprocessing_contract_version,
        "sanitized_endpoint_identity": sanitized_endpoint_identity,
        "provider_adapter_contract_version": provider_adapter_contract_version,
        "governed_adapter_contract_version": governed_adapter_contract_version,
        "resolution_classifier_version": resolution_classifier_version,
    }
    return hashlib.sha256(_canonical_json(payload).encode()).hexdigest()


def compute_check_id() -> str:
    """UUID4 hex — each probe is a distinct event."""
    return uuid.uuid4().hex


def compute_check_expiry(probed_at: datetime, ttl_seconds: int) -> datetime:
    """Authorization expiry timestamp for a passed check."""
    if probed_at.tzinfo is None:
        probed_at = probed_at.replace(tzinfo=UTC)
    return probed_at + timedelta(seconds=ttl_seconds)
