"""Provider-neutral identity-evidence contract for embedding adapters (P0.4B0.1a).

This module defines the contract that every embedding provider populates
with whatever model-identity evidence the underlying API actually exposes.
Per the P0.4B0 directive, the contract is deliberately *evidence*, not a
capability binding: providers capture what they observed; the shared
classifier (B0.2) interprets it.

Frozen rules (directive):

  captured identity evidence ≠ stable model identity
  provider echo of requested model ≠ exact revision
  missing response identity → reported_model NULL
  no capability binding/check created in B0

This module has no dependency on the provider implementations; providers
import from here when they want to surface evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ProviderModelIdentityEvidence:
    """Evidence captured from a single embedding provider response.

    All fields are advisory evidence — none of them alone implies a
    stable capability identity. B0.2's classifier consumes this record
    plus the effective runtime configuration to derive posture.

    Fields:
        provider_kind: short identifier of the provider family
            (e.g. "openai", "gemini", "ollama", "lmstudio"). Used for
            routing and dispatch; not a model identity.
        requested_model: the model identifier the caller configured or
            passed to the request. Always populated.
        reported_model: the model identifier the provider echoed back in
            its response, if any. NULL when the provider's response
            carries no model field (Gemini, Ollama) or the field was
            missing/malformed (OpenAI edge cases). NULL is honest — it
            means "we have no evidence beyond the request."
        deployment_id: a deployment, endpoint, or serving identifier
            that the configuration has pinned (e.g. an Azure deployment
            name, a LM Studio loaded model id). NULL unless the adapter
            has a specific, non-ambient reason to populate it.
        provider_revision: an immutable artifact identity the provider
            exposes (e.g. Ollama manifest digest, a model checksum).
            NULL for providers that do not expose one. When non-NULL,
            B0.2 may classify the posture as ``exact_revision``.
        evidence_source: short machine-readable string identifying where
            the evidence came from (e.g. "openai_response_model",
            "lmstudio_v1_models", "ollama_api_show_digest",
            "configured_only"). Required so a later audit can
            distinguish "we read it from the response" from "we copied
            it from the request."
    """

    provider_kind: str
    requested_model: str
    evidence_source: str
    reported_model: str | None = None
    deployment_id: str | None = None
    provider_revision: str | None = None


@dataclass(frozen=True)
class ProviderEmbeddingBatch:
    """Result of a document-embedding call: vectors plus identity evidence.

    The adapter returns both pieces so callers can record evidence
    without re-issuing a probe. The evidence is *what was observed* —
    B0.2 interprets it; B0 does not.

    Tuple types (not lists) make the records hashable and communicate
    immutability: once a batch is returned, neither the caller nor the
    adapter should mutate the vectors.
    """

    embeddings: tuple[tuple[float, ...], ...]
    identity_evidence: ProviderModelIdentityEvidence


@dataclass(frozen=True)
class ProviderEmbeddingQuery:
    """Result of a single-text query embedding: vector plus identity evidence.

    Equivalent to ``ProviderEmbeddingBatch`` for the single-text query
    path. Kept as a distinct type so role-aware validation (B0.3
    adapter, future verified runtime) can distinguish document batches
    from query results without inspecting length.
    """

    embedding: tuple[float, ...]
    identity_evidence: ProviderModelIdentityEvidence


# Evidence-source vocabulary. Adapters should use one of these strings
# (or document a new one in this list). The classifier (B0.2) reads
# these to weight evidence — "we read it from the response" is stronger
# than "we copied it from the request."
EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL = "openai_response_model"
EVIDENCE_SOURCE_LMSTUDIO_V1_MODELS = "lmstudio_v1_models"
EVIDENCE_SOURCE_LMSTUDIO_RESPONSE_MODEL = "lmstudio_response_model"
EVIDENCE_SOURCE_OLLAMA_API_SHOW_DIGEST = "ollama_api_show_digest"
EVIDENCE_SOURCE_OLLAMA_RESPONSE = "ollama_response"
EVIDENCE_SOURCE_GEMINI_CONFIGURED_MODEL = "gemini_configured_model"
EVIDENCE_SOURCE_CONFIGURED_ONLY = "configured_only"
