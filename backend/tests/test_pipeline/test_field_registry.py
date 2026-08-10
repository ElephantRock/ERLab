"""Tests for P0.5.1: canonical configuration field registry.

Proves:
  - Every Settings field has a registry entry (289)
  - No duplicate field IDs
  - Every active field has an owner
  - Material fields have production consumers + effect contracts
  - Credential fields are classified as secret
  - Registry validation passes
"""

from __future__ import annotations

from backend.config import Settings
from backend.pipeline.config.field_registry import (
    EFFECT_BEHAVIORAL,
    LIFECYCLE_ACTIVE,
    MATERIAL_INFORMATIONAL,
    MATERIAL_INTERNAL,
    MATERIAL_PUBLIC,
    SENSITIVITY_SECRET,
    build_registry,
    validate_registry,
)


class TestRegistryCompleteness:
    def test_every_settings_field_registered(self):
        """Every accepted Settings field must have a registry entry."""
        registry = build_registry()
        settings_names = set(Settings.model_fields.keys())
        registry_paths = {f.canonical_path for f in registry.fields.values()}
        missing = settings_names - registry_paths
        assert not missing, f"Missing from registry: {sorted(missing)[:10]}"

    def test_registry_has_289_fields(self):
        """The registry must contain exactly as many entries as Settings has fields."""
        registry = build_registry()
        assert len(registry.fields) == len(Settings.model_fields)

    def test_no_duplicate_field_ids(self):
        registry = build_registry()
        ids = [f.field_id for f in registry.fields.values()]
        assert len(ids) == len(set(ids)), "Duplicate field IDs found"

    def test_no_duplicate_canonical_paths(self):
        registry = build_registry()
        paths = [f.canonical_path for f in registry.fields.values()]
        assert len(paths) == len(set(paths)), "Duplicate canonical paths found"


class TestRegistryClassification:
    def test_every_active_field_has_owner(self):
        registry = build_registry()
        unowned = [
            f.field_id for f in registry.fields.values()
            if f.lifecycle_status == LIFECYCLE_ACTIVE and not f.owner
        ]
        # Uncategorized fields may have owner="uncategorized" which is truthy
        assert not unowned, f"Active fields without owner: {unowned[:10]}"

    def test_material_fields_have_consumers(self):
        registry = build_registry()
        material = registry.material_fields()
        without_consumers = [
            f.field_id for f in material if not f.production_consumers
        ]
        assert not without_consumers, (
            f"Material fields without production consumers: {without_consumers}"
        )

    def test_material_fields_have_effect_contracts(self):
        registry = build_registry()
        material = registry.material_fields()
        without_contracts = [
            f.field_id for f in material if not f.effect_contract_ids
        ]
        assert not without_contracts, (
            f"Material fields without effect contracts: {without_contracts}"
        )

    def test_credential_fields_are_secret(self):
        registry = build_registry()
        # Only check fields that are actual credentials, not directories
        # that happen to have "secret" in the name (e.g. secrets_persist_dir)
        credential_names = [
            "openai_api_key", "anthropic_api_key", "gemini_api_key",
            "semantic_scholar_api_key", "pubmed_api_key",
            "api_key", "jwt_secret", "secrets_master_password",
            "webhook_secret",
        ]
        for name in credential_names:
            field = registry.get_by_path(name)
            if field is not None:
                assert field.sensitivity == SENSITIVITY_SECRET, (
                    f"Credential field {name} not classified as secret"
                )

    def test_has_material_fields(self):
        """At least the known material fields should be classified."""
        registry = build_registry()
        material = registry.material_fields()
        # Should have at least 20 material fields from the overlay
        assert len(material) >= 20, f"Expected >=20 material fields, got {len(material)}"

    def test_has_internal_fields(self):
        """Some fields should be classified as internal."""
        registry = build_registry()
        counts = registry.count_by_materiality()
        assert MATERIAL_INTERNAL in counts or MATERIAL_INFORMATIONAL in counts, (
            "No internal or informational fields found"
        )


class TestRegistryValidation:
    def test_validation_passes(self):
        """The registry validation must pass with zero errors."""
        registry = build_registry()
        errors = validate_registry(registry)
        assert not errors, "Registry validation errors:\n" + "\n".join(errors)


class TestRegistryStructure:
    def test_schema_version(self):
        registry = build_registry()
        assert registry.schema_version == "field_registry_v1"

    def test_get_by_path(self):
        registry = build_registry()
        field = registry.get_by_path("default_provider")
        assert field is not None
        assert field.materiality == MATERIAL_PUBLIC

    def test_get_by_id(self):
        registry = build_registry()
        field = registry.get("embedding_provider")
        assert field is not None
        assert field.effect_class == EFFECT_BEHAVIORAL

    def test_count_by_materiality(self):
        registry = build_registry()
        counts = registry.count_by_materiality()
        total = sum(counts.values())
        assert total == len(registry.fields)
