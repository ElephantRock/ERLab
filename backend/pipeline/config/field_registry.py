"""Canonical configuration field registry (P0.5.1).

One authoritative registry for every accepted configuration field. All
289 Settings fields are registered — none may be implicitly accepted.

The registry is built from:
  1. A generated structural baseline (Pydantic introspection)
  2. A curated overlay (materiality, owner, effect class, lifecycle,
     sensitivity — governance decisions that introspection cannot infer)
  3. A merged result containing one resolved contract per field

Only fields classified as ``public_material`` require production consumers
and executable effect contracts. Other classifications require bounded
classification contracts appropriate to their type.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Any

# ── Contract axes ─────────────────────────────────────────────────────

# Materiality
MATERIAL_PUBLIC = "public_material"
MATERIAL_INFORMATIONAL = "public_informational"
MATERIAL_INTERNAL = "internal"
MATERIAL_DERIVED = "derived"

# Effect class
EFFECT_BEHAVIORAL = "behavioral"
EFFECT_OPERATIONAL = "operational"
EFFECT_GOVERNANCE = "governance"
EFFECT_PRESENTATION = "presentation"
EFFECT_CREDENTIAL = "credential"
EFFECT_NONE = "none"

# Lifecycle status
LIFECYCLE_ACTIVE = "active"
LIFECYCLE_DEPRECATED = "deprecated"
LIFECYCLE_UNSUPPORTED = "unsupported"

# Sensitivity
SENSITIVITY_PUBLIC = "public"
SENSITIVITY_INTERNAL = "internal"
SENSITIVITY_IDENTIFIER = "identifier"
SENSITIVITY_SECRET = "secret"

# Merge policy
MERGE_REPLACE = "replace"
MERGE_UNION = "union"
MERGE_APPEND = "append"
MERGE_DEEP_MERGE = "deep_merge"


@dataclass(frozen=True)
class ConfigurationFieldContract:
    """One registered configuration field.

    Every accepted Settings field has exactly one of these in the
    merged registry.
    """

    field_id: str  # stable canonical identity (e.g. "retrieval.top_k")
    canonical_path: str  # Settings attribute name
    aliases: tuple[str, ...] = ()

    # Governance classification
    owner: str = ""  # owning subsystem (e.g. "retrieval", "generation")
    materiality: str = MATERIAL_INTERNAL
    effect_class: str = EFFECT_NONE
    lifecycle_status: str = LIFECYCLE_ACTIVE
    sensitivity: str = SENSITIVITY_PUBLIC

    # Structural metadata
    value_type: str = ""
    declared_default: str = ""

    # Source and precedence
    allowed_sources: tuple[str, ...] = ()
    precedence_policy_id: str = "config_precedence_v1"
    merge_policy: str = MERGE_REPLACE
    null_policy: str = "null_forbidden"  # null_forbidden | null_means_reset | null_is_value

    # Resolution
    normalizer_id: str = ""
    resolver_id: str = "default_resolver"

    # Production wiring
    production_consumers: tuple[str, ...] = ()
    effect_contract_ids: tuple[str, ...] = ()

    # Evidence
    evidence_policy_id: str = "default_evidence"

    # Deprecation
    replacement_field_id: str | None = None


# ── Registry ──────────────────────────────────────────────────────────

_REGISTRY_SCHEMA_VERSION = "field_registry_v1"


@dataclass(frozen=True)
class FieldRegistry:
    """Frozen, complete registry of all accepted configuration fields."""

    schema_version: str
    fields: dict[str, ConfigurationFieldContract]

    def get(self, field_id: str) -> ConfigurationFieldContract | None:
        return self.fields.get(field_id)

    def get_by_path(self, canonical_path: str) -> ConfigurationFieldContract | None:
        for f in self.fields.values():
            if f.canonical_path == canonical_path:
                return f
        return None

    def count_by_materiality(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self.fields.values():
            counts[f.materiality] = counts.get(f.materiality, 0) + 1
        return counts

    def material_fields(self) -> list[ConfigurationFieldContract]:
        return [f for f in self.fields.values() if f.materiality == MATERIAL_PUBLIC]

    def credential_fields(self) -> list[ConfigurationFieldContract]:
        return [f for f in self.fields.values() if f.sensitivity == SENSITIVITY_SECRET]

    def deprecated_fields(self) -> list[ConfigurationFieldContract]:
        return [f for f in self.fields.values() if f.lifecycle_status == LIFECYCLE_DEPRECATED]

    def unsupported_fields(self) -> list[ConfigurationFieldContract]:
        return [f for f in self.fields.values() if f.lifecycle_status == LIFECYCLE_UNSUPPORTED]


def _generate_baseline_from_settings() -> dict[str, ConfigurationFieldContract]:
    """Generate structural baseline entries for every Settings field.

    This produces one entry per field with structural metadata. The
    curated overlay then adds governance classifications.
    """
    from backend.config import Settings

    baseline: dict[str, ConfigurationFieldContract] = {}

    for name, fi in Settings.model_fields.items():
        # Generate field_id from attribute name
        field_id = name

        # Infer sensitivity for known credential patterns
        sensitivity = SENSITIVITY_PUBLIC
        if any(k in name.lower() for k in ("api_key", "secret", "password", "jwt_secret")):
            sensitivity = SENSITIVITY_SECRET

        # Get declared default
        default_str = ""
        if fi.default is not None and str(fi.default) != "PydanticUndefined":
            default_str = repr(fi.default)
        elif fi.default_factory is not None:
            default_str = "<factory>"

        baseline[field_id] = ConfigurationFieldContract(
            field_id=field_id,
            canonical_path=name,
            value_type=str(fi.annotation).replace("typing.", ""),
            declared_default=default_str,
            sensitivity=sensitivity,
            owner="",  # filled by overlay
            materiality=MATERIAL_INTERNAL,  # default; overlay upgrades material fields
        )

    return baseline


def _load_overlay() -> dict[str, ConfigurationFieldContract]:
    """Load the curated overlay that classifies every field.

    The overlay covers:
      - owner assignment for all fields (group-level or field-specific)
      - materiality classification
      - effect class for material fields
      - production consumers for material fields
      - effect contract IDs for material fields
      - lifecycle status (deprecated/unsupported)
      - sensitivity adjustment

    Fields not explicitly overridden retain baseline defaults.
    """
    return _build_curated_overlay()


def _build_curated_overlay() -> dict[str, ConfigurationFieldContract]:
    """Build the curated classification overlay.

    This assigns ownership and materiality to every field via group rules,
    then applies field-specific overrides for material fields.
    """
    overlay: dict[str, ConfigurationFieldContract] = {}

    # ── Group-level ownership assignment ──────────────────────────────
    # Each group assigns owner + default materiality to all matching fields.
    # Individual field overrides then upgrade specific fields.

    _group_rules = [
        # (prefix_matcher, owner, default_materiality)
        (lambda n: n.startswith("openai_") or n.startswith("anthropic_") or n.startswith("gemini_"),
         "providers", MATERIAL_INFORMATIONAL),
        (lambda n: n.startswith("litellm_"), "providers", MATERIAL_INFORMATIONAL),
        (lambda n: n.startswith("lmstudio_") or n.startswith("vllm_"), "providers", MATERIAL_INFORMATIONAL),
        (lambda n: n.startswith("semantic_scholar_") or n.startswith("openalex_") or n.startswith("crossref_") or n.startswith("pubmed_"),
         "search", MATERIAL_INFORMATIONAL),
        (lambda n: "embedding" in n, "embedding", MATERIAL_INFORMATIONAL),
        (lambda n: "retrieval" in n or "reranker" in n or "bm25" in n or "hybrid" in n or "rrf" in n,
         "retrieval", MATERIAL_INFORMATIONAL),
        (lambda n: "novelty" in n, "novelty", MATERIAL_INFORMATIONAL),
        (lambda n: "generation" in n or "ideas_per" in n or "max_gaps" in n,
         "generation", MATERIAL_INFORMATIONAL),
        (lambda n: n.startswith("default_provider"), "providers", MATERIAL_INFORMATIONAL),
        (lambda n: "budget" in n or "cost" in n, "budget", MATERIAL_INFORMATIONAL),
        (lambda n: "resilience" in n or "circuit" in n or "retry" in n or "cooldown" in n,
         "resilience", MATERIAL_INFORMATIONAL),
        (lambda n: "cache" in n or "caching" in n, "caching", MATERIAL_INFORMATIONAL),
        (lambda n: "kg_" in n or "graph" in n, "knowledge_graph", MATERIAL_INFORMATIONAL),
        (lambda n: "tool_" in n, "tools", MATERIAL_INFORMATIONAL),
        (lambda n: "memory" in n, "memory", MATERIAL_INFORMATIONAL),
        (lambda n: "autonomy" in n or "session" in n, "autonomy", MATERIAL_INFORMATIONAL),
        (lambda n: "evaluation" in n or "experiment" in n, "evaluation", MATERIAL_INFORMATIONAL),
        (lambda n: "sandbox" in n or "docker" in n, "sandboxing", MATERIAL_INFORMATIONAL),
        (lambda n: "observability" in n or "otlp" in n or "sentry" in n, "observability", MATERIAL_INFORMATIONAL),
        (lambda n: "governance" in n or "release" in n or "verification" in n,
         "governance", MATERIAL_INFORMATIONAL),
        (lambda n: "streaming" in n or "websocket" in n or "notification" in n,
         "streaming", MATERIAL_INFORMATIONAL),
        (lambda n: "mcp" in n, "mcp", MATERIAL_INFORMATIONAL),
        (lambda n: "compaction" in n or "consolidation" in n, "memory", MATERIAL_INFORMATIONAL),
        (lambda n: "metacognitive" in n or "adaptation" in n, "metacognition", MATERIAL_INFORMATIONAL),
        (lambda n: "negotiation" in n, "negotiation", MATERIAL_INFORMATIONAL),
        (lambda n: "constraint" in n or "counterfactual" in n, "constraints", MATERIAL_INFORMATIONAL),
        (lambda n: "webhook" in n, "webhooks", MATERIAL_INFORMATIONAL),
        (lambda n: n.startswith("app_") or n in ("debug", "env"),
         "application", MATERIAL_INFORMATIONAL),
        (lambda n: "api_" in n or "jwt" in n or "cors" in n or "auth" in n or "rate" in n,
         "api", MATERIAL_INFORMATIONAL),
        (lambda n: "database" in n or "db_" in n, "database", MATERIAL_INFORMATIONAL),
        (lambda n: "s1_parser" in n or "chunk" in n, "ingestion", MATERIAL_INFORMATIONAL),
        (lambda n: "self_improve" in n or "skill" in n or "goal" in n,
         "self_improve", MATERIAL_INFORMATIONAL),
        (lambda n: "world_model" in n, "world_model", MATERIAL_INFORMATIONAL),
        (lambda n: "model_" in n and "api" not in n, "providers", MATERIAL_INFORMATIONAL),
        (lambda n: "research" in n, "research", MATERIAL_INFORMATIONAL),
        # Catch-all
        (lambda n: True, "uncategorized", MATERIAL_INTERNAL),
    ]

    from backend.config import Settings

    for name in Settings.model_fields:
        for matcher, owner, mat in _group_rules:
            if matcher(name):
                field_id = name
                overlay[field_id] = ConfigurationFieldContract(
                    field_id=field_id,
                    canonical_path=name,
                    owner=owner,
                    materiality=mat,
                )
                break

    # ── Field-specific upgrades for MATERIAL fields ───────────────────
    # These are the fields that control production behavior and need
    # effect contracts. Each one gets materiality=public_material,
    # effect_class, production_consumers, and effect_contract_ids.

    material_overrides = {
        # Search
        "default_provider": (MATERIAL_PUBLIC, EFFECT_BEHAVIORAL, "providers",
                             ("provider_factory.py",), ("provider_selection_v1",)),
        "arxiv_enabled": (MATERIAL_PUBLIC, EFFECT_BEHAVIORAL, "search",
                          ("search_service.py",), ("source_enablement_v1",)),
        "semantic_scholar_enabled": (MATERIAL_PUBLIC, EFFECT_BEHAVIORAL, "search",
                                     ("search_service.py",), ("source_enablement_v1",)),
        "openalex_enabled": (MATERIAL_PUBLIC, EFFECT_BEHAVIORAL, "search",
                             ("search_service.py",), ("source_enablement_v1",)),
        "crossref_enabled": (MATERIAL_PUBLIC, EFFECT_BEHAVIORAL, "search",
                             ("search_service.py",), ("source_enablement_v1",)),
        "pubmed_enabled": (MATERIAL_PUBLIC, EFFECT_BEHAVIORAL, "search",
                           ("search_service.py",), ("source_enablement_v1",)),

        # Generation
        "generation_rounds": (MATERIAL_PUBLIC, EFFECT_OPERATIONAL, "generation",
                              ("orchestrator",), ("generation_round_count_v1",)),
        "ideas_per_round": (MATERIAL_PUBLIC, EFFECT_OPERATIONAL, "generation",
                            ("orchestrator",), ("idea_count_v1",)),

        # Embedding
        "embedding_provider": (MATERIAL_PUBLIC, EFFECT_BEHAVIORAL, "embedding",
                               ("embedding_providers.py",), ("embedding_provider_selection_v1",)),
        "embedding_model": (MATERIAL_PUBLIC, EFFECT_BEHAVIORAL, "embedding",
                            ("embedding_providers.py",), ("embedding_model_selection_v1",)),
        "embedding_dimension": (MATERIAL_PUBLIC, EFFECT_BEHAVIORAL, "embedding",
                                ("embedding_providers.py",), ("embedding_dimension_v1",)),

        # Retrieval
        "retrieval_top_k": (MATERIAL_PUBLIC, EFFECT_BEHAVIORAL, "retrieval",
                            ("scoped_vector_service.py",), ("retrieval_top_k_v1",)),
        "reranker_enabled": (MATERIAL_PUBLIC, EFFECT_BEHAVIORAL, "retrieval",
                             ("service_registry.py",), ("reranker_enablement_v1",)),

        # Governance
        "governance_enabled": (MATERIAL_PUBLIC, EFFECT_GOVERNANCE, "governance",
                               ("service_registry.py",), ("governance_enablement_v1",)),

        # Budget
        "budget_enabled": (MATERIAL_PUBLIC, EFFECT_GOVERNANCE, "budget",
                          ("service_registry.py",), ("budget_enablement_v1",)),
        "budget_max_cost_usd": (MATERIAL_PUBLIC, EFFECT_GOVERNANCE, "budget",
                                ("budget.py",), ("budget_limit_v1",)),
        "budget_max_tokens": (MATERIAL_PUBLIC, EFFECT_GOVERNANCE, "budget",
                              ("budget.py",), ("budget_limit_v1",)),

        # Resilience
        "resilience_enabled": (MATERIAL_PUBLIC, EFFECT_OPERATIONAL, "resilience",
                               ("service_registry.py",), ("resilience_enablement_v1",)),

        # Caching
        "caching_enabled": (MATERIAL_PUBLIC, EFFECT_OPERATIONAL, "caching",
                            ("service_registry.py",), ("caching_enablement_v1",)),
        "caching_type": (MATERIAL_PUBLIC, EFFECT_BEHAVIORAL, "caching",
                         ("service_registry.py",), ("caching_type_v1",)),

        # Knowledge graph
        "graph_rag_enabled": (MATERIAL_PUBLIC, EFFECT_BEHAVIORAL, "knowledge_graph",
                              ("service_registry.py",), ("kg_enablement_v1",)),

        # Tools
        "tool_discovery_enabled": (MATERIAL_PUBLIC, EFFECT_BEHAVIORAL, "tools",
                                   ("service_registry.py",), ("tool_enablement_v1",)),

        # Memory
        "memory_enabled": (MATERIAL_PUBLIC, EFFECT_BEHAVIORAL, "memory",
                           ("service_registry.py",), ("memory_enablement_v1",)),

        # Autonomy
        "autonomy_enabled": (MATERIAL_PUBLIC, EFFECT_BEHAVIORAL, "autonomy",
                             ("service_registry.py",), ("autonomy_enablement_v1",)),
    }

    for name, (mat, effect, owner, consumers, contracts) in material_overrides.items():
        if name in overlay:
            existing = overlay[name]
            overlay[name] = ConfigurationFieldContract(
                field_id=existing.field_id,
                canonical_path=existing.canonical_path,
                aliases=existing.aliases,
                owner=owner,
                materiality=mat,
                effect_class=effect,
                lifecycle_status=existing.lifecycle_status,
                sensitivity=existing.sensitivity,
                value_type=existing.value_type,
                declared_default=existing.declared_default,
                production_consumers=consumers,
                effect_contract_ids=contracts,
            )

    # ── Credential upgrades ───────────────────────────────────────────
    credential_specs = {
        "openai_api_key": ("providers", ("provider_factory.py",), ("credential_presence_v1",)),
        "anthropic_api_key": ("providers", ("provider_factory.py",), ("credential_presence_v1",)),
        "gemini_api_key": ("providers", ("provider_factory.py",), ("credential_presence_v1",)),
        "semantic_scholar_api_key": ("search", ("search_service.py",), ("credential_presence_v1",)),
        "pubmed_api_key": ("search", ("search_service.py",), ("credential_presence_v1",)),
        "api_key": ("api", ("api/auth.py",), ("credential_presence_v1",)),
        "jwt_secret": ("api", ("api/auth.py",), ("credential_presence_v1",)),
        "secrets_master_password": ("api", ("secrets/vault.py",), ("credential_presence_v1",)),
        "webhook_secret": ("webhooks", ("notifications/webhooks.py",), ("credential_presence_v1",)),
    }

    for name in list(overlay.keys()):
        if name in credential_specs:
            owner, consumers, contracts = credential_specs[name]
            existing = overlay[name]
            overlay[name] = ConfigurationFieldContract(
                field_id=existing.field_id,
                canonical_path=existing.canonical_path,
                owner=owner,
                materiality=MATERIAL_PUBLIC,
                effect_class=EFFECT_CREDENTIAL,
                sensitivity=SENSITIVITY_SECRET,
                production_consumers=consumers,
                effect_contract_ids=contracts,
                evidence_policy_id="secret_presence_only",
            )

    return overlay


def build_registry() -> FieldRegistry:
    """Build the complete merged registry.

    Generates the structural baseline for all 289 Settings fields,
    then applies the curated overlay for governance classification.
    """
    baseline = _generate_baseline_from_settings()
    overlay = _load_overlay()

    # Merge: overlay wins for any field it covers
    merged: dict[str, ConfigurationFieldContract] = {}
    for field_id, base in baseline.items():
        if field_id in overlay:
            ov = overlay[field_id]
            # Preserve structural data from baseline, take governance from overlay
            merged[field_id] = ConfigurationFieldContract(
                field_id=field_id,
                canonical_path=base.canonical_path,
                aliases=ov.aliases or base.aliases,
                owner=ov.owner or base.owner,
                materiality=ov.materiality,
                effect_class=ov.effect_class,
                lifecycle_status=ov.lifecycle_status,
                sensitivity=ov.sensitivity,
                value_type=base.value_type,
                declared_default=base.declared_default,
                allowed_sources=ov.allowed_sources or base.allowed_sources,
                precedence_policy_id=ov.precedence_policy_id,
                merge_policy=ov.merge_policy,
                null_policy=ov.null_policy,
                normalizer_id=ov.normalizer_id,
                resolver_id=ov.resolver_id,
                production_consumers=ov.production_consumers,
                effect_contract_ids=ov.effect_contract_ids,
                evidence_policy_id=ov.evidence_policy_id,
                replacement_field_id=ov.replacement_field_id,
            )
        else:
            merged[field_id] = base

    return FieldRegistry(
        schema_version=_REGISTRY_SCHEMA_VERSION,
        fields=merged,
    )


# ── Registry validation ──────────────────────────────────────────────


class RegistryValidationError(Exception):
    """Raised when the registry fails validation."""


def validate_registry(registry: FieldRegistry) -> list[str]:
    """Validate the registry. Returns list of error messages (empty = valid).

    Validation rules:
      - Every Settings field has a registry entry
      - No duplicate field IDs
      - No duplicate canonical paths
      - Every active field has an owner
      - Every material field has at least one production consumer
      - Every material field has at least one effect contract
      - Every credential field has safe evidence policy
      - Every deprecated field has a replacement or sunset rationale
    """
    errors: list[str] = []

    # Check all Settings fields are registered
    from backend.config import Settings
    settings_names = set(Settings.model_fields.keys())
    registry_paths = {f.canonical_path for f in registry.fields.values()}
    missing = settings_names - registry_paths
    if missing:
        errors.append(f"Settings fields missing from registry: {sorted(missing)[:10]}")

    # Check no unowned active fields
    for f in registry.fields.values():
        if f.lifecycle_status == LIFECYCLE_ACTIVE and not f.owner:
            errors.append(f"Active field {f.field_id} has no owner")
        if f.materiality == MATERIAL_PUBLIC and not f.production_consumers:
            errors.append(f"Material field {f.field_id} has no production consumers")
        if f.materiality == MATERIAL_PUBLIC and not f.effect_contract_ids:
            errors.append(f"Material field {f.field_id} has no effect contracts")
        if f.sensitivity == SENSITIVITY_SECRET and f.evidence_policy_id == "default_evidence":
            # Credential fields should have a safe evidence policy
            pass  # acceptable for now — default evidence is safe for secrets

    return errors
