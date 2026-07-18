"""Model-aware side-channel embedding contracts (P0.4B0.5a).

Separates semantic spaces for knowledge-graph entities, tool descriptions,
and LLM semantic cache keys through dedicated embedding purpose identifiers
and deterministic namespace fingerprints.

Each side channel gets its own reconciled embedding configuration and
governed adapter — the paper embedding profile is never reused.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal


EmbeddingPurpose = Literal[
    "paper",
    "knowledge_graph_entity",
    "tool_description",
    "llm_cache_key",
]

_VALID_PURPOSES = frozenset({
    "paper",
    "knowledge_graph_entity",
    "tool_description",
    "llm_cache_key",
})


@dataclass(frozen=True)
class SideChannelEmbeddingRuntime:
    """Narrow runtime for a non-paper embedding surface.

    Contains only what a side channel needs: purpose, effective config,
    adapter, and a deterministic namespace fingerprint. Does not expose
    GovernedVectorRuntime wholesale.
    """
    purpose: EmbeddingPurpose
    effective_embedding_config: Any  # EffectiveEmbeddingConfiguration
    embedding_adapter: Any  # GovernedEmbeddingAdapter
    namespace_fingerprint: str


from typing import Any


class SideChannelEmbeddingError(Exception):
    """Bounded side-channel embedding error with sanitized detail."""
    def __init__(self, code: str, detail: str):
        self.code = code
        # Sanitize — reuse the pattern from embedding_configuration
        import re
        s = detail
        s = re.sub(r"[a-zA-Z0-9._~%-]+:[a-zA-Z0-9._~%-]+@", "[creds]@", s)
        s = re.sub(r"(?i)(api[_-]?key|token|secret|password|bearer)\s*[=:]\s*\S+", "[auth]", s)
        s = re.sub(r"\?[^\s'\"]*", "[query]", s)
        self.detail = s[:500]
        super().__init__(f"[{code}] {self.detail}")


def compute_namespace_fingerprint(
    *,
    embedding_profile_id: str,
    purpose: EmbeddingPurpose,
    provider_kind: str,
    requested_model: str,
    sanitized_endpoint_identity: str,
    expected_dimension: int,
    declared_normalization_policy: str,
    implemented_postprocessing_policy: str,
    provider_adapter_contract_version: str,
    governed_adapter_contract_version: str,
) -> str:
    """Deterministic, secret-safe namespace fingerprint for a side channel.

    Includes everything that materially affects the semantic space identity.
    Excludes credentials, timestamps, capability check IDs.
    """
    payload = {
        "embedding_profile_id": embedding_profile_id,
        "purpose": purpose,
        "provider_kind": provider_kind,
        "requested_model": requested_model,
        "endpoint": sanitized_endpoint_identity,
        "dimension": expected_dimension,
        "declared_normalization": declared_normalization_policy,
        "implemented_normalization": implemented_postprocessing_policy,
        "provider_adapter_contract": provider_adapter_contract_version,
        "governed_adapter_contract": governed_adapter_contract_version,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def compute_side_channel_collection_name(
    base_name: str,
    namespace_fingerprint: str,
) -> str:
    """Deterministic collection name for a side channel.

    Example: kg_entity_embeddings_a1b2c3d4e5f6a1b2
    """
    return f"{base_name}_{namespace_fingerprint[:24]}"


def compute_cache_namespace(
    *,
    purpose: EmbeddingPurpose,
    embedding_profile_id: str,
    namespace_fingerprint: str,
    cache_schema_version: str = "cache_v1",
) -> str:
    """Deterministic cache namespace string for semantic cache isolation.

    When any component changes (model, endpoint, dimension, adapter version),
    this produces a different namespace, making old cache entries unreachable.
    """
    payload = {
        "purpose": purpose,
        "profile_id": embedding_profile_id,
        "namespace_fingerprint": namespace_fingerprint,
        "cache_schema": cache_schema_version,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:32]


def assert_purpose_not_paper(purpose: EmbeddingPurpose) -> None:
    """Side channels must not use the 'paper' purpose."""
    if purpose == "paper":
        raise SideChannelEmbeddingError(
            "side_channel_purpose_mismatch",
            "side channels must not use the 'paper' embedding purpose",
        )


def assert_profile_not_paper_profile(
    side_channel_profile_id: str,
    paper_profile_id: str,
) -> None:
    """Side channels must not reuse the paper embedding profile."""
    if side_channel_profile_id == paper_profile_id:
        raise SideChannelEmbeddingError(
            "side_channel_profile_mismatch",
            "side channel must not reuse the paper embedding profile",
        )
