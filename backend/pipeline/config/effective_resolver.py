"""Source-aware effective-value provenance (P0.5.2).

Two resolution layers:

Phase A — Deployment configuration:
  Pydantic source candidates (init, env, file, secrets, default)
  → deployment Settings
  → deployment provenance receipts

Phase B — Domain effective configuration:
  explicit operation override
  → governed persisted profile
  → deployment Settings receipt
  → declared field default
  → EffectiveDomainConfiguration

The final ResolvedConfigurationValue describes the winner across both phases.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

# ── Semantic source tiers (highest to lowest precedence) ─────────────

TIER_OPERATION_OVERRIDE = "operation_override"
TIER_GOVERNED_PROFILE = "governed_profile"
TIER_DEPLOYMENT = "deployment"
TIER_DECLARED_DEFAULT = "declared_default"

_TIER_PRECEDENCE = {
    TIER_OPERATION_OVERRIDE: 4,
    TIER_GOVERNED_PROFILE: 3,
    TIER_DEPLOYMENT: 2,
    TIER_DECLARED_DEFAULT: 1,
}

# ── Physical origins ─────────────────────────────────────────────────

ORIGIN_CLI = "cli_argument"
ORIGIN_API = "api_request"
ORIGIN_DB_PROFILE = "database_profile"
ORIGIN_ENV = "environment_variable"
ORIGIN_CONFIG_FILE = "configuration_file"
ORIGIN_DEFAULT = "application_default"

# ── Precedence policy version ────────────────────────────────────────

CONFIG_PRECEDENCE_POLICY_V1 = "config_precedence_v1"


@dataclass(frozen=True)
class SourceCandidate:
    """A value candidate from one physical origin at one semantic tier."""

    value: Any
    semantic_tier: str
    physical_origin: str
    explicitly_supplied: bool  # True if operator/config explicitly provided
    alias_used: str | None = None


@dataclass(frozen=True)
class ResolvedConfigurationValue:
    """The resolved effective value with complete provenance.

    Describes the winner across both resolution phases.
    """

    field_id: str
    effective_value: Any
    value_fingerprint: str

    winning_semantic_tier: str
    winning_physical_origin: str

    default_applied: bool
    normalization_applied: bool
    deprecated_alias_used: bool

    shadowed_origins: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class ConfigurationConflict(Exception):
    """Two sources at the same semantic tier supplied different values."""

    def __init__(self, field_id: str, origins: tuple[str, ...]):
        self.field_id = field_id
        self.origins = origins
        super().__init__(
            f"configuration_conflict for {field_id}: "
            f"same-tier origins {origins} supplied different values"
        )


class UnsupportedConfigurationField(Exception):
    """An unknown or unsupported configuration field was supplied."""

    def __init__(self, field_name: str):
        self.field_name = field_name
        super().__init__(f"unsupported_configuration_field: {field_name}")


def _compute_fingerprint(value: Any) -> str:
    """Deterministic fingerprint of a resolved value (non-secret)."""
    try:
        payload = json.dumps({"v": value}, sort_keys=True, default=str)
    except (TypeError, ValueError):
        payload = repr(value)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def resolve_field(
    *,
    field_id: str,
    candidates: list[SourceCandidate],
    declared_default: Any = None,
    null_policy: str = "null_forbidden",
    normalizer: callable | None = None,
) -> ResolvedConfigurationValue:
    """Resolve one field from its source candidates.

    Uses the registered precedence policy:
      operation_override > governed_profile > deployment > declared_default

    Same-tier conflicts fail with ConfigurationConflict.

    Args:
        field_id: The canonical field ID from the registry.
        candidates: Value candidates from various sources.
        declared_default: The registry's declared default (lowest tier).
        null_policy: How to handle None values.
        normalizer: Optional normalization function.
    """
    warnings: list[str] = []

    # Sort candidates by semantic tier (highest first)
    def tier_rank(c: SourceCandidate) -> int:
        return _TIER_PRECEDENCE.get(c.semantic_tier, 0)

    sorted_candidates = sorted(candidates, key=tier_rank, reverse=True)

    # Find the winner: highest-tier explicitly-supplied candidate
    winner: SourceCandidate | None = None
    shadowed: list[str] = []

    for candidate in sorted_candidates:
        if not candidate.explicitly_supplied:
            continue

        if winner is None:
            winner = candidate
        elif candidate.semantic_tier == winner.semantic_tier:
            # Same tier — check for conflict
            if candidate.value != winner.value:
                raise ConfigurationConflict(
                    field_id,
                    (winner.physical_origin, candidate.physical_origin),
                )
            # Same value at same tier — OK, but note the duplicate source
            shadowed.append(candidate.physical_origin)
        else:
            shadowed.append(candidate.physical_origin)

    # If no explicitly-supplied candidate, use declared default
    default_applied = False
    deprecated_alias_used = False

    if winner is None:
        winner = SourceCandidate(
            value=declared_default,
            semantic_tier=TIER_DECLARED_DEFAULT,
            physical_origin=ORIGIN_DEFAULT,
            explicitly_supplied=False,
        )
        default_applied = True

    # Check deprecated alias
    if winner.alias_used is not None:
        deprecated_alias_used = True
        warnings.append(f"deprecated_alias: {winner.alias_used}")

    # Null policy enforcement
    if winner.value is None:
        if null_policy == "null_forbidden":
            warnings.append(f"null_value_forbidden: {field_id} is None")
        elif null_policy == "null_means_reset":
            warnings.append(f"null_reset: {field_id} reset to default")
            winner = SourceCandidate(
                value=declared_default,
                semantic_tier=TIER_DECLARED_DEFAULT,
                physical_origin=ORIGIN_DEFAULT,
                explicitly_supplied=False,
            )
            default_applied = True

    # Normalization
    effective_value = winner.value
    normalization_applied = False
    if normalizer is not None and effective_value is not None:
        normalized = normalizer(effective_value)
        if normalized != effective_value:
            effective_value = normalized
            normalization_applied = True

    return ResolvedConfigurationValue(
        field_id=field_id,
        effective_value=effective_value,
        value_fingerprint=_compute_fingerprint(effective_value),
        winning_semantic_tier=winner.semantic_tier,
        winning_physical_origin=winner.physical_origin,
        default_applied=default_applied,
        normalization_applied=normalization_applied,
        deprecated_alias_used=deprecated_alias_used,
        shadowed_origins=tuple(shadowed),
        warnings=tuple(warnings),
    )


def resolve_configuration_fingerprint(
    resolved_values: dict[str, ResolvedConfigurationValue],
) -> str:
    """Compute a deterministic fingerprint over a set of resolved values.

    Used for configuration resolution snapshots.
    """
    payload = {
        "registry_version": "field_registry_v1",
        "precedence_policy": CONFIG_PRECEDENCE_POLICY_V1,
        "fields": {
            fid: {
                "value_fingerprint": rv.value_fingerprint,
                "winning_tier": rv.winning_semantic_tier,
            }
            for fid, rv in sorted(resolved_values.items())
        },
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
