"""Effective embedding configuration resolver (P0.4B0.7).

Reconciles runtime settings, registered embedding profiles, and adapter
capabilities into one immutable, secret-safe contract. The resolver is
pure — no provider construction, requests, database writes, or SDK mutation.

Disagreement between settings, profile, and adapter fails before any
provider is constructed or invoked.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)


# ── Exception ────────────────────────────────────────────────────────


class EmbeddingConfigurationError(Exception):
    """Configuration reconciliation failure with a bounded code."""

    def __init__(self, code: str, detail: str):
        self.code = code
        # Sanitize detail — strip potential secrets
        self.detail = _sanitize_text(detail)
        super().__init__(f"[{code}] {self.detail}")


def _sanitize_text(text: str) -> str:
    """Strip credentials from text for safe error messages."""
    s = text
    # Strip URL userinfo
    s = re.sub(r"[a-zA-Z0-9._~%-]+:[a-zA-Z0-9._~%-]+@", "[creds]@", s)
    # Strip api_key-like patterns
    s = re.sub(r"(?i)(api[_-]?key|token|secret|password|bearer)\s*[=:]\s*\S+", "[auth]", s)
    # Strip query strings
    s = re.sub(r"\?[^\s'\"]*", "[query]", s)
    if len(s) > 500:
        s = s[:497] + "..."
    return s


# ── Input snapshots ──────────────────────────────────────────────────


@dataclass(frozen=True)
class EmbeddingRuntimeSettingsSnapshot:
    """Immutable snapshot of runtime embedding settings. No credentials."""
    provider_kind: str
    requested_model: str
    expected_dimension: int
    declared_normalization_policy: str
    document_task: str | None
    query_task: str | None
    endpoint: str | None
    configured_deployment_id: str | None
    deployment_is_explicitly_pinned: bool


@dataclass(frozen=True)
class EmbeddingProfileSnapshot:
    """Immutable snapshot of a registered embedding profile."""
    embedding_profile_id: str
    profile_schema_version: str
    provider_kind: str
    model_identifier: str
    dimension: int
    normalization_policy: str
    document_task: str | None
    query_task: str | None
    verification_status: str


@dataclass(frozen=True)
class EmbeddingAdapterCapabilitySnapshot:
    """What the adapter code actually implements."""
    provider_adapter_contract_version: str
    governed_adapter_contract_version: str
    implemented_postprocessing_policy: str
    supports_document_embedding: bool
    supports_query_embedding: bool


# ── Result ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class EffectiveEmbeddingConfiguration:
    """Immutable reconciled configuration. The single source of truth for
    what a governed embedding operation may assume about its runtime."""
    embedding_profile_id: str
    profile_schema_version: str
    provider_kind: str
    requested_model: str
    expected_dimension: int
    declared_normalization_policy: str
    implemented_postprocessing_policy: str
    document_task: str | None
    query_task: str | None
    sanitized_endpoint_identity: str
    configured_deployment_id: str | None
    deployment_is_explicitly_pinned: bool
    provider_adapter_contract_version: str
    governed_adapter_contract_version: str


# ── Provider canonicalization ────────────────────────────────────────

_PROVIDER_ALIASES: dict[str, str] = {
    "lm_studio": "lmstudio",
    "lm-studio": "lmstudio",
    "local": "lmstudio",
    "google": "gemini",
    "google_genai": "gemini",
    "ollama": "ollama",
    "open-ai": "openai",
}


def _canonicalize_provider(name: str) -> str:
    """Canonicalize known provider aliases. Unknown names pass through."""
    return _PROVIDER_ALIASES.get(name.strip().lower(), name.strip())


# ── Endpoint sanitizer ───────────────────────────────────────────────


def sanitize_endpoint_identity(endpoint: str | None) -> str:
    """Deterministic, secret-free endpoint identity.

    Rules:
      - scheme lowercase
      - hostname lowercase
      - default ports normalized (80/http, 443/https)
      - userinfo removed
      - fragment removed
      - query parameters rejected (B0.7 default: no query strings)
      - trailing slash removed

    Returns "provider-default://<kind>" for None endpoints.
    """
    if endpoint is None or endpoint.strip() == "":
        return "provider-default://unset"

    parsed = urlparse(endpoint)

    # Reject userinfo
    if parsed.username or parsed.password:
        raise EmbeddingConfigurationError(
            "embedding_endpoint_identity_invalid",
            "endpoint contains userinfo credentials",
        )

    # Reject query parameters
    if parsed.query:
        raise EmbeddingConfigurationError(
            "embedding_endpoint_identity_invalid",
            "endpoint contains query parameters",
        )

    # Reject fragments
    if parsed.fragment:
        raise EmbeddingConfigurationError(
            "embedding_endpoint_identity_invalid",
            "endpoint contains fragment",
        )

    scheme = (parsed.scheme or "http").lower()
    hostname = (parsed.hostname or "").lower()
    port = parsed.port

    # Normalize default ports
    if port == 80 and scheme == "http":
        port = None
    elif port == 443 and scheme == "https":
        port = None

    # Normalize path
    path = parsed.path.rstrip("/") or ""

    netloc = hostname
    if port is not None:
        netloc = f"{hostname}:{port}"

    normalized = urlunparse((scheme, netloc, path, "", "", ""))
    return normalized


# ── Reconciliation ───────────────────────────────────────────────────


def resolve_effective_embedding_configuration(
    *,
    settings: EmbeddingRuntimeSettingsSnapshot,
    profile: EmbeddingProfileSnapshot,
    adapter: EmbeddingAdapterCapabilitySnapshot,
) -> EffectiveEmbeddingConfiguration:
    """Pure reconciliation of settings + profile + adapter capabilities.

    Returns an immutable EffectiveEmbeddingConfiguration if all checks pass.
    Raises EmbeddingConfigurationError with a bounded code on disagreement.

    This function performs no provider construction, requests, DB writes,
    or environment mutation.
    """
    # ── Profile schema ──
    if profile.profile_schema_version != "embedding_profile_v1":
        raise EmbeddingConfigurationError(
            "embedding_profile_schema_unsupported",
            f"profile schema {profile.profile_schema_version!r}; "
            f"expected 'embedding_profile_v1'",
        )

    # ── Provider agreement ──
    settings_provider = _canonicalize_provider(settings.provider_kind)
    profile_provider = _canonicalize_provider(profile.provider_kind)
    if settings_provider != profile_provider:
        raise EmbeddingConfigurationError(
            "embedding_provider_mismatch",
            f"settings provider {settings_provider!r} != "
            f"profile provider {profile_provider!r}",
        )

    # ── Model agreement ──
    settings_model = settings.requested_model.strip()
    profile_model = profile.model_identifier.strip()
    if settings_model != profile_model:
        raise EmbeddingConfigurationError(
            "embedding_model_mismatch",
            f"settings model {settings_model!r} != "
            f"profile model {profile_model!r}",
        )

    # ── Dimension agreement ──
    if isinstance(settings.expected_dimension, bool):
        raise EmbeddingConfigurationError(
            "embedding_dimension_mismatch",
            "settings dimension is bool, not integer",
        )
    if not isinstance(settings.expected_dimension, int) or settings.expected_dimension <= 0:
        raise EmbeddingConfigurationError(
            "embedding_dimension_mismatch",
            f"settings dimension {settings.expected_dimension!r} is not a positive integer",
        )
    if settings.expected_dimension != profile.dimension:
        raise EmbeddingConfigurationError(
            "embedding_dimension_mismatch",
            f"settings dimension {settings.expected_dimension} != "
            f"profile dimension {profile.dimension}",
        )

    # ── Normalization: declaration vs declaration ──
    settings_norm = settings.declared_normalization_policy.strip().lower()
    profile_norm = profile.normalization_policy.strip().lower()
    if settings_norm != profile_norm:
        raise EmbeddingConfigurationError(
            "embedding_normalization_mismatch",
            f"settings normalization {settings_norm!r} != "
            f"profile normalization {profile_norm!r}",
        )

    # ── Normalization: declaration vs implementation ──
    implemented_norm = adapter.implemented_postprocessing_policy.strip().lower()
    if profile_norm != implemented_norm:
        raise EmbeddingConfigurationError(
            "embedding_postprocessing_contract_mismatch",
            f"declared {profile_norm!r} but implemented {implemented_norm!r}; "
            f"the adapter does not implement the declared post-processing",
        )

    # ── Document task agreement ──
    if settings.document_task != profile.document_task:
        raise EmbeddingConfigurationError(
            "embedding_document_task_mismatch",
            f"settings document_task {settings.document_task!r} != "
            f"profile document_task {profile.document_task!r}",
        )

    # ── Query task agreement ──
    if settings.query_task != profile.query_task:
        raise EmbeddingConfigurationError(
            "embedding_query_task_mismatch",
            f"settings query_task {settings.query_task!r} != "
            f"profile query_task {profile.query_task!r}",
        )

    # ── Adapter role support ──
    if not adapter.supports_document_embedding:
        raise EmbeddingConfigurationError(
            "embedding_document_role_unsupported",
            "adapter does not support document embedding",
        )
    if not adapter.supports_query_embedding:
        raise EmbeddingConfigurationError(
            "embedding_query_role_unsupported",
            "adapter does not support query embedding",
        )

    # ── Adapter contract versions ──
    if not adapter.provider_adapter_contract_version:
        raise EmbeddingConfigurationError(
            "embedding_adapter_contract_missing",
            "provider adapter contract version is empty",
        )
    if not adapter.governed_adapter_contract_version:
        raise EmbeddingConfigurationError(
            "embedding_adapter_contract_missing",
            "governed adapter contract version is empty",
        )

    # ── Endpoint identity ──
    sanitized_endpoint = sanitize_endpoint_identity(settings.endpoint)

    # ── Deployment pinning ──
    if settings.deployment_is_explicitly_pinned and not settings.configured_deployment_id:
        raise EmbeddingConfigurationError(
            "embedding_deployment_pin_incomplete",
            "deployment pin is true but no deployment ID is configured",
        )

    # ── Success: build effective configuration ──
    return EffectiveEmbeddingConfiguration(
        embedding_profile_id=profile.embedding_profile_id,
        profile_schema_version=profile.profile_schema_version,
        provider_kind=settings_provider,
        requested_model=settings_model,
        expected_dimension=settings.expected_dimension,
        declared_normalization_policy=profile_norm,
        implemented_postprocessing_policy=implemented_norm,
        document_task=settings.document_task,
        query_task=settings.query_task,
        sanitized_endpoint_identity=sanitized_endpoint,
        configured_deployment_id=settings.configured_deployment_id,
        deployment_is_explicitly_pinned=settings.deployment_is_explicitly_pinned,
        provider_adapter_contract_version=adapter.provider_adapter_contract_version,
        governed_adapter_contract_version=adapter.governed_adapter_contract_version,
    )
