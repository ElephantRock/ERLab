"""P0.5.8: Durable configuration resolution evidence.

Persists operation-linked, secret-safe configuration receipts. Never
persists secret raw values — only presence markers and safe fingerprints.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from backend.pipeline.config.effective_resolver import (
    ResolvedConfigurationValue,
    resolve_configuration_fingerprint,
)


@dataclass(frozen=True)
class ConfigurationResolutionSnapshot:
    """Durable snapshot of effective configuration for one operation."""

    snapshot_id: str
    scope_kind: str  # "search_execution" | "retrieval_event" | "generation" | "release"
    scope_id: str  # FK to the operation (e.g. execution_id, event_id)
    registry_schema_version: str
    precedence_policy_version: str
    effective_configuration_fingerprint: str
    created_at: datetime
    items: tuple[ConfigurationResolutionItem, ...]


@dataclass(frozen=True)
class ConfigurationResolutionItem:
    """One resolved field within a snapshot."""

    snapshot_id: str
    field_id: str
    effect_class: str
    winning_semantic_tier: str
    winning_physical_origin: str
    default_applied: bool
    normalization_applied: bool
    value_representation: str | None  # None for secrets
    value_fingerprint: str | None  # None for low-entropy secrets
    shadowed_source_count: int


def build_resolution_snapshot(
    *,
    scope_kind: str,
    scope_id: str,
    resolved_values: dict[str, ResolvedConfigurationValue],
    field_classifications: dict[str, str] | None = None,
) -> ConfigurationResolutionSnapshot:
    """Build a durable configuration resolution snapshot.

    Never includes raw secret values. Secret fields get:
      value_representation = None
      value_fingerprint = None
    """
    import hashlib

    snapshot_id = hashlib.sha256(
        f"{scope_kind}:{scope_id}:{datetime.now(UTC).isoformat()}".encode()
    ).hexdigest()[:32]
    now = datetime.now(UTC)
    fingerprint = resolve_configuration_fingerprint(resolved_values)

    items: list[ConfigurationResolutionItem] = []
    for field_id, rv in resolved_values.items():
        # Determine if this is a secret field
        effect_class = (field_classifications or {}).get(field_id, "behavioral")
        is_secret = "credential" in effect_class.lower() or "secret" in effect_class.lower()

        value_repr = None
        value_fp = None
        if not is_secret:
            value_repr = repr(rv.effective_value)[:200]
            value_fp = rv.value_fingerprint

        items.append(ConfigurationResolutionItem(
            snapshot_id=snapshot_id,
            field_id=field_id,
            effect_class=effect_class,
            winning_semantic_tier=rv.winning_semantic_tier,
            winning_physical_origin=rv.winning_physical_origin,
            default_applied=rv.default_applied,
            normalization_applied=rv.normalization_applied,
            value_representation=value_repr,
            value_fingerprint=value_fp,
            shadowed_source_count=len(rv.shadowed_origins),
        ))

    return ConfigurationResolutionSnapshot(
        snapshot_id=snapshot_id,
        scope_kind=scope_kind,
        scope_id=scope_id,
        registry_schema_version="field_registry_v1",
        precedence_policy_version="config_precedence_v1",
        effective_configuration_fingerprint=fingerprint,
        created_at=now,
        items=tuple(items),
    )
