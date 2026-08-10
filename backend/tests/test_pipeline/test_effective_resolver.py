"""Tests for P0.5.2: source-aware effective-value provenance."""

from __future__ import annotations

import pytest

from backend.pipeline.config.effective_resolver import (
    ORIGIN_API,
    ORIGIN_CLI,
    ORIGIN_ENV,
    TIER_DECLARED_DEFAULT,
    TIER_DEPLOYMENT,
    TIER_OPERATION_OVERRIDE,
    ConfigurationConflict,
    ResolvedConfigurationValue,
    SourceCandidate,
    resolve_configuration_fingerprint,
    resolve_field,
)


class TestPrecedence:
    def test_operation_override_beats_deployment(self):
        result = resolve_field(
            field_id="test_field",
            candidates=[
                SourceCandidate(value=10, semantic_tier=TIER_DEPLOYMENT,
                                physical_origin=ORIGIN_ENV, explicitly_supplied=True),
                SourceCandidate(value=20, semantic_tier=TIER_OPERATION_OVERRIDE,
                                physical_origin=ORIGIN_CLI, explicitly_supplied=True),
            ],
            declared_default=5,
        )
        assert result.effective_value == 20
        assert result.winning_semantic_tier == TIER_OPERATION_OVERRIDE
        assert ORIGIN_ENV in result.shadowed_origins

    def test_deployment_beats_default(self):
        result = resolve_field(
            field_id="test_field",
            candidates=[
                SourceCandidate(value=10, semantic_tier=TIER_DEPLOYMENT,
                                physical_origin=ORIGIN_ENV, explicitly_supplied=True),
            ],
            declared_default=5,
        )
        assert result.effective_value == 10
        assert not result.default_applied

    def test_default_when_no_explicit(self):
        result = resolve_field(
            field_id="test_field",
            candidates=[],
            declared_default=5,
        )
        assert result.effective_value == 5
        assert result.default_applied
        assert result.winning_semantic_tier == TIER_DECLARED_DEFAULT


class TestConflictDetection:
    def test_same_tier_conflict_raises(self):
        with pytest.raises(ConfigurationConflict) as exc:
            resolve_field(
                field_id="test_field",
                candidates=[
                    SourceCandidate(value=10, semantic_tier=TIER_OPERATION_OVERRIDE,
                                    physical_origin=ORIGIN_CLI, explicitly_supplied=True),
                    SourceCandidate(value=20, semantic_tier=TIER_OPERATION_OVERRIDE,
                                    physical_origin=ORIGIN_API, explicitly_supplied=True),
                ],
                declared_default=5,
            )
        assert exc.value.field_id == "test_field"

    def test_same_tier_same_value_ok(self):
        result = resolve_field(
            field_id="test_field",
            candidates=[
                SourceCandidate(value=10, semantic_tier=TIER_OPERATION_OVERRIDE,
                                physical_origin=ORIGIN_CLI, explicitly_supplied=True),
                SourceCandidate(value=10, semantic_tier=TIER_OPERATION_OVERRIDE,
                                physical_origin=ORIGIN_API, explicitly_supplied=True),
            ],
            declared_default=5,
        )
        assert result.effective_value == 10
        assert ORIGIN_API in result.shadowed_origins


class TestNullPolicy:
    def test_null_forbidden_warns(self):
        result = resolve_field(
            field_id="test_field",
            candidates=[
                SourceCandidate(value=None, semantic_tier=TIER_OPERATION_OVERRIDE,
                                physical_origin=ORIGIN_CLI, explicitly_supplied=True),
            ],
            declared_default=5,
            null_policy="null_forbidden",
        )
        assert any("null_value_forbidden" in w for w in result.warnings)

    def test_null_means_reset(self):
        result = resolve_field(
            field_id="test_field",
            candidates=[
                SourceCandidate(value=None, semantic_tier=TIER_OPERATION_OVERRIDE,
                                physical_origin=ORIGIN_CLI, explicitly_supplied=True),
            ],
            declared_default=42,
            null_policy="null_means_reset",
        )
        assert result.effective_value == 42
        assert result.default_applied


class TestNormalization:
    def test_normalizer_applied(self):
        result = resolve_field(
            field_id="test_field",
            candidates=[
                SourceCandidate(value="UPPER", semantic_tier=TIER_DEPLOYMENT,
                                physical_origin=ORIGIN_ENV, explicitly_supplied=True),
            ],
            declared_default="default",
            normalizer=str.lower,
        )
        assert result.effective_value == "upper"
        assert result.normalization_applied


class TestDeprecation:
    def test_deprecated_alias_warning(self):
        result = resolve_field(
            field_id="test_field",
            candidates=[
                SourceCandidate(
                    value=10, semantic_tier=TIER_DEPLOYMENT,
                    physical_origin=ORIGIN_ENV, explicitly_supplied=True,
                    alias_used="old_name",
                ),
            ],
            declared_default=5,
        )
        assert result.deprecated_alias_used
        assert any("deprecated_alias" in w for w in result.warnings)


class TestFingerprint:
    def test_deterministic(self):
        values = {
            "f1": ResolvedConfigurationValue(
                field_id="f1", effective_value=10, value_fingerprint="abc",
                winning_semantic_tier=TIER_DEPLOYMENT,
                winning_physical_origin=ORIGIN_ENV,
                default_applied=False, normalization_applied=False,
                deprecated_alias_used=False,
            ),
        }
        fp1 = resolve_configuration_fingerprint(values)
        fp2 = resolve_configuration_fingerprint(values)
        assert fp1 == fp2
        assert len(fp1) == 64

    def test_different_values_different_fingerprint(self):
        v1 = {"f1": ResolvedConfigurationValue(
            field_id="f1", effective_value=10, value_fingerprint="abc",
            winning_semantic_tier=TIER_DEPLOYMENT, winning_physical_origin=ORIGIN_ENV,
            default_applied=False, normalization_applied=False, deprecated_alias_used=False,
        )}
        v2 = {"f1": ResolvedConfigurationValue(
            field_id="f1", effective_value=20, value_fingerprint="def",
            winning_semantic_tier=TIER_DEPLOYMENT, winning_physical_origin=ORIGIN_ENV,
            default_applied=False, normalization_applied=False, deprecated_alias_used=False,
        )}
        assert resolve_configuration_fingerprint(v1) != resolve_configuration_fingerprint(v2)


class TestSecretRedaction:
    def test_secret_fingerprint_not_reversible(self):
        """The fingerprint is a truncated SHA-256 — not reversible."""
        result = resolve_field(
            field_id="secret_field",
            candidates=[
                SourceCandidate(value="sk-secret-key-12345",
                                semantic_tier=TIER_DEPLOYMENT,
                                physical_origin=ORIGIN_ENV,
                                explicitly_supplied=True),
            ],
            declared_default="",
        )
        assert "sk-secret" not in result.value_fingerprint
        assert len(result.value_fingerprint) == 16
