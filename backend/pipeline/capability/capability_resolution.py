"""Capability resolution classifier (P0.4A1.2).

Classifies what a successful dual-probe proved about the runtime identity
and produces the ``ResolvedBindingInput`` that ``resolve_or_create_binding``
consumes.

Resolution postures:

  exact_revision
      The provider exposed an immutable artifact identity (e.g. Ollama
      manifest digest) that the probe captured. This is the strongest
      posture — the runtime is pinned to an exact revision.

  configured_match
      The provider echoed back the requested model identity (e.g. OpenAI
      response.model matches the request). The runtime matches the
      declared contract but is not pinned to an immutable revision.

  configured_only
      The provider returned no identity evidence beyond what was
      configured (e.g. Gemini, Ollama without /api/show). The runtime
      is assumed to match the declared contract but cannot be proven.

A binding is created with whichever posture the probe evidence supports.
The posture participates in binding identity, so a future probe that
gains stronger evidence produces a distinct (and potentially
higher-confidence) binding.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.pipeline.knowledge.embedding_provider_identity import (
    ProviderModelIdentityEvidence,
)

if TYPE_CHECKING:
    from backend.pipeline.knowledge.embedding_configuration import (
        EffectiveEmbeddingConfiguration,
    )

# ── Posture vocabulary ────────────────────────────────────────────────

POSTURE_EXACT_REVISION = "exact_revision"
POSTURE_CONFIGURED_MATCH = "configured_match"
POSTURE_CONFIGURED_ONLY = "configured_only"

_VALID_POSTURES = frozenset({
    POSTURE_EXACT_REVISION,
    POSTURE_CONFIGURED_MATCH,
    POSTURE_CONFIGURED_ONLY,
})


@dataclass(frozen=True)
class ResolvedBindingInput:
    """The fields a successful probe proved.

    Constructed ONLY from ``EffectiveEmbeddingConfiguration`` plus observed
    probe evidence. Never from a failed or incomplete probe.
    """

    embedding_profile_id: str
    profile_schema_version: str
    provider_kind: str
    resolved_model: str
    provider_revision: str | None
    model_resolution_posture: str
    resolved_deployment_id: str | None
    resolved_document_task: str | None
    resolved_query_task: str | None
    resolved_dimension: int
    resolved_normalization: str
    postprocessing_contract_version: str
    sanitized_endpoint_identity: str
    provider_adapter_contract_version: str
    governed_adapter_contract_version: str


@dataclass(frozen=True)
class ResolutionDecision:
    """The output of ``classify_resolution``.

    ``posture`` identifies what the probe proved.
    ``binding_input`` is the resolved evidence that determines the
    binding identity.
    """

    posture: str
    binding_input: ResolvedBindingInput


def classify_resolution(
    effective_config: EffectiveEmbeddingConfiguration,
    document_evidence: ProviderModelIdentityEvidence,
    query_evidence: ProviderModelIdentityEvidence,
    observed_document_dimension: int,
    observed_query_dimension: int,
) -> ResolutionDecision:
    """Classify what the probe proved about the runtime identity.

    Uses the strongest evidence available from either document or query
    probe. If the provider exposed a revision (digest), the posture is
    ``exact_revision``. If the provider echoed the requested model, the
    posture is ``configured_match``. Otherwise ``configured_only``.

    The ``resolved_model`` is the configured ``requested_model`` — it is
    the declared contract, not the provider's echo. The echo is captured
    separately in the check's observation columns.
    """
    # Determine posture from the strongest evidence
    revision = None
    posture = POSTURE_CONFIGURED_ONLY

    # Prefer document evidence, fall back to query
    for evidence in (document_evidence, query_evidence):
        if evidence.provider_revision:
            revision = evidence.provider_revision
            posture = POSTURE_EXACT_REVISION
            break
        if evidence.reported_model and evidence.reported_model == effective_config.requested_model:
            posture = POSTURE_CONFIGURED_MATCH

    # If one evidence has revision but the other doesn't, that's a conflict
    # — but we already took the strongest. The check's observation columns
    # preserve both separately for audit.

    binding_input = ResolvedBindingInput(
        embedding_profile_id=effective_config.embedding_profile_id,
        profile_schema_version=effective_config.profile_schema_version,
        provider_kind=effective_config.provider_kind,
        resolved_model=effective_config.requested_model,
        provider_revision=revision,
        model_resolution_posture=posture,
        resolved_deployment_id=effective_config.configured_deployment_id,
        resolved_document_task=effective_config.document_task,
        resolved_query_task=effective_config.query_task,
        resolved_dimension=effective_config.expected_dimension,
        resolved_normalization=effective_config.declared_normalization_policy,
        postprocessing_contract_version=effective_config.implemented_postprocessing_policy,
        sanitized_endpoint_identity=effective_config.sanitized_endpoint_identity,
        provider_adapter_contract_version=effective_config.provider_adapter_contract_version,
        governed_adapter_contract_version=effective_config.governed_adapter_contract_version,
    )

    assert posture in _VALID_POSTURES, f"invalid posture: {posture}"

    return ResolutionDecision(posture=posture, binding_input=binding_input)
