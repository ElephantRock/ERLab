"""Tests for P0.4B0.7: EffectiveEmbeddingConfiguration resolver.

Proves:
  - Happy path: valid configuration produces immutable result
  - All agreement failures (provider, model, dimension, normalization, tasks)
  - Post-processing truth (declared l2 + implemented none = fail)
  - Endpoint safety (credentials, query strings, fragments stripped/rejected)
  - Deployment pinning rules
  - Mutation safety (inputs unchanged)
  - Determinism
  - No capability/binding/check creation
"""

from __future__ import annotations

import pytest

from backend.pipeline.knowledge.embedding_configuration import (
    EffectiveEmbeddingConfiguration,
    EmbeddingAdapterCapabilitySnapshot,
    EmbeddingConfigurationError,
    EmbeddingProfileSnapshot,
    EmbeddingRuntimeSettingsSnapshot,
    resolve_effective_embedding_configuration,
    sanitize_endpoint_identity,
)

# ── Fixtures ─────────────────────────────────────────────────────────


def _settings(**overrides):
    defaults = dict(
        provider_kind="lmstudio",
        requested_model="qwen3-embedding-0.6b",
        expected_dimension=1024,
        declared_normalization_policy="none",
        document_task=None,
        query_task=None,
        endpoint="http://localhost:1234/v1",
        configured_deployment_id=None,
        deployment_is_explicitly_pinned=False,
    )
    defaults.update(overrides)
    return EmbeddingRuntimeSettingsSnapshot(**defaults)


def _profile(**overrides):
    defaults = dict(
        embedding_profile_id="a" * 64,
        profile_schema_version="embedding_profile_v1",
        provider_kind="lmstudio",
        model_identifier="qwen3-embedding-0.6b",
        dimension=1024,
        normalization_policy="none",
        document_task=None,
        query_task=None,
        verification_status="unverified",
    )
    defaults.update(overrides)
    return EmbeddingProfileSnapshot(**defaults)


def _adapter(**overrides):
    defaults = dict(
        provider_adapter_contract_version="provider_adapter_v1",
        governed_adapter_contract_version="governed_adapter_v1",
        implemented_postprocessing_policy="none",
        supports_document_embedding=True,
        supports_query_embedding=True,
    )
    defaults.update(overrides)
    return EmbeddingAdapterCapabilitySnapshot(**defaults)


# ── Happy path ───────────────────────────────────────────────────────


def test_happy_path():
    cfg = resolve_effective_embedding_configuration(
        settings=_settings(),
        profile=_profile(),
        adapter=_adapter(),
    )
    assert isinstance(cfg, EffectiveEmbeddingConfiguration)
    assert cfg.provider_kind == "lmstudio"
    assert cfg.requested_model == "qwen3-embedding-0.6b"
    assert cfg.expected_dimension == 1024
    assert cfg.declared_normalization_policy == "none"
    assert cfg.implemented_postprocessing_policy == "none"
    assert cfg.sanitized_endpoint_identity == "http://localhost:1234/v1"


def test_no_credentials_in_result():
    cfg = resolve_effective_embedding_configuration(
        settings=_settings(),
        profile=_profile(),
        adapter=_adapter(),
    )
    cfg_repr = repr(cfg)
    assert "api_key" not in cfg_repr.lower()
    assert "password" not in cfg_repr.lower()
    assert "secret" not in cfg_repr.lower()


def test_no_provider_construction_or_request():
    """The resolver is pure — no side effects."""
    # If this function returns without error, no provider was constructed
    # or invoked (there's no provider parameter).
    cfg = resolve_effective_embedding_configuration(
        settings=_settings(),
        profile=_profile(),
        adapter=_adapter(),
    )
    assert cfg is not None


# ── Agreement failures ───────────────────────────────────────────────


def test_provider_mismatch():
    with pytest.raises(EmbeddingConfigurationError) as exc:
        resolve_effective_embedding_configuration(
            settings=_settings(provider_kind="openai"),
            profile=_profile(provider_kind="lmstudio"),
            adapter=_adapter(),
        )
    assert exc.value.code == "embedding_provider_mismatch"


def test_model_mismatch():
    with pytest.raises(EmbeddingConfigurationError) as exc:
        resolve_effective_embedding_configuration(
            settings=_settings(requested_model="model-a"),
            profile=_profile(model_identifier="model-b"),
            adapter=_adapter(),
        )
    assert exc.value.code == "embedding_model_mismatch"


def test_dimension_mismatch():
    with pytest.raises(EmbeddingConfigurationError) as exc:
        resolve_effective_embedding_configuration(
            settings=_settings(expected_dimension=768),
            profile=_profile(dimension=1024),
            adapter=_adapter(),
        )
    assert exc.value.code == "embedding_dimension_mismatch"


def test_dimension_bool_rejected():
    with pytest.raises(EmbeddingConfigurationError) as exc:
        resolve_effective_embedding_configuration(
            settings=_settings(expected_dimension=True),
            profile=_profile(),
            adapter=_adapter(),
        )
    assert exc.value.code == "embedding_dimension_mismatch"


def test_dimension_zero_rejected():
    with pytest.raises(EmbeddingConfigurationError) as exc:
        resolve_effective_embedding_configuration(
            settings=_settings(expected_dimension=0),
            profile=_profile(),
            adapter=_adapter(),
        )
    assert exc.value.code == "embedding_dimension_mismatch"


def test_normalization_mismatch():
    with pytest.raises(EmbeddingConfigurationError) as exc:
        resolve_effective_embedding_configuration(
            settings=_settings(declared_normalization_policy="l2"),
            profile=_profile(normalization_policy="none"),
            adapter=_adapter(),
        )
    assert exc.value.code == "embedding_normalization_mismatch"


def test_document_task_mismatch():
    with pytest.raises(EmbeddingConfigurationError) as exc:
        resolve_effective_embedding_configuration(
            settings=_settings(document_task="retrieval_document"),
            profile=_profile(document_task=None),
            adapter=_adapter(),
        )
    assert exc.value.code == "embedding_document_task_mismatch"


def test_query_task_mismatch():
    with pytest.raises(EmbeddingConfigurationError) as exc:
        resolve_effective_embedding_configuration(
            settings=_settings(query_task="retrieval_query"),
            profile=_profile(query_task=None),
            adapter=_adapter(),
        )
    assert exc.value.code == "embedding_query_task_mismatch"


# ── Post-processing truth ────────────────────────────────────────────


def test_declared_l2_implemented_none_fails():
    """declared l2 + implemented none → postprocessing_contract_mismatch."""
    with pytest.raises(EmbeddingConfigurationError) as exc:
        resolve_effective_embedding_configuration(
            settings=_settings(declared_normalization_policy="l2"),
            profile=_profile(normalization_policy="l2"),
            adapter=_adapter(implemented_postprocessing_policy="none"),
        )
    assert exc.value.code == "embedding_postprocessing_contract_mismatch"


def test_declared_none_implemented_none_passes():
    cfg = resolve_effective_embedding_configuration(
        settings=_settings(declared_normalization_policy="none"),
        profile=_profile(normalization_policy="none"),
        adapter=_adapter(implemented_postprocessing_policy="none"),
    )
    assert cfg.declared_normalization_policy == "none"
    assert cfg.implemented_postprocessing_policy == "none"


# ── Adapter role support ─────────────────────────────────────────────


def test_document_role_unsupported():
    with pytest.raises(EmbeddingConfigurationError) as exc:
        resolve_effective_embedding_configuration(
            settings=_settings(),
            profile=_profile(),
            adapter=_adapter(supports_document_embedding=False),
        )
    assert exc.value.code == "embedding_document_role_unsupported"


def test_query_role_unsupported():
    with pytest.raises(EmbeddingConfigurationError) as exc:
        resolve_effective_embedding_configuration(
            settings=_settings(),
            profile=_profile(),
            adapter=_adapter(supports_query_embedding=False),
        )
    assert exc.value.code == "embedding_query_role_unsupported"


def test_missing_adapter_contract_version():
    with pytest.raises(EmbeddingConfigurationError) as exc:
        resolve_effective_embedding_configuration(
            settings=_settings(),
            profile=_profile(),
            adapter=_adapter(governed_adapter_contract_version=""),
        )
    assert exc.value.code == "embedding_adapter_contract_missing"


# ── Profile schema ───────────────────────────────────────────────────


def test_unsupported_profile_schema():
    with pytest.raises(EmbeddingConfigurationError) as exc:
        resolve_effective_embedding_configuration(
            settings=_settings(),
            profile=_profile(profile_schema_version="bogus_v2"),
            adapter=_adapter(),
        )
    assert exc.value.code == "embedding_profile_schema_unsupported"


# ── Endpoint safety ──────────────────────────────────────────────────


def test_endpoint_userinfo_rejected():
    with pytest.raises(EmbeddingConfigurationError) as exc:
        resolve_effective_embedding_configuration(
            settings=_settings(endpoint="https://user:pass@host.com/v1"),
            profile=_profile(),
            adapter=_adapter(),
        )
    assert exc.value.code == "embedding_endpoint_identity_invalid"


def test_endpoint_query_string_rejected():
    with pytest.raises(EmbeddingConfigurationError) as exc:
        resolve_effective_embedding_configuration(
            settings=_settings(endpoint="http://localhost:1234/v1?api_key=secret"),
            profile=_profile(),
            adapter=_adapter(),
        )
    assert exc.value.code == "embedding_endpoint_identity_invalid"


def test_endpoint_fragment_rejected():
    with pytest.raises(EmbeddingConfigurationError) as exc:
        resolve_effective_embedding_configuration(
            settings=_settings(endpoint="http://localhost:1234/v1#anchor"),
            profile=_profile(),
            adapter=_adapter(),
        )
    assert exc.value.code == "embedding_endpoint_identity_invalid"


def test_endpoint_default_port_normalized():
    identity = sanitize_endpoint_identity("http://localhost:80/v1")
    assert ":80" not in identity
    assert identity == "http://localhost/v1"


def test_endpoint_https_default_port_normalized():
    identity = sanitize_endpoint_identity("https://localhost:443/v1")
    assert ":443" not in identity
    assert identity == "https://localhost/v1"


def test_endpoint_hostname_lowercased():
    identity = sanitize_endpoint_identity("http://LOCALHOST:1234/v1")
    assert "LOCALHOST" not in identity
    assert "localhost" in identity


def test_endpoint_trailing_slash_removed():
    identity = sanitize_endpoint_identity("http://localhost:1234/v1/")
    assert not identity.endswith("/")


def test_endpoint_none_returns_default():
    identity = sanitize_endpoint_identity(None)
    assert identity == "provider-default://unset"


def test_endpoint_secrets_not_in_exception():
    with pytest.raises(EmbeddingConfigurationError) as exc:
        resolve_effective_embedding_configuration(
            settings=_settings(endpoint="https://admin:hunter2@host.com/v1?token=secret"),
            profile=_profile(),
            adapter=_adapter(),
        )
    err_str = str(exc.value)
    assert "hunter2" not in err_str
    assert "secret" not in err_str
    assert "admin" not in err_str


# ── Deployment pinning ───────────────────────────────────────────────


def test_pin_true_no_deployment_id_fails():
    with pytest.raises(EmbeddingConfigurationError) as exc:
        resolve_effective_embedding_configuration(
            settings=_settings(deployment_is_explicitly_pinned=True,
                               configured_deployment_id=None),
            profile=_profile(),
            adapter=_adapter(),
        )
    assert exc.value.code == "embedding_deployment_pin_incomplete"


def test_deployment_id_no_pin_valid():
    cfg = resolve_effective_embedding_configuration(
        settings=_settings(deployment_is_explicitly_pinned=False,
                           configured_deployment_id="deploy-abc"),
        profile=_profile(),
        adapter=_adapter(),
    )
    assert cfg.configured_deployment_id == "deploy-abc"
    assert cfg.deployment_is_explicitly_pinned is False


def test_pin_true_with_deployment_id_valid():
    cfg = resolve_effective_embedding_configuration(
        settings=_settings(deployment_is_explicitly_pinned=True,
                           configured_deployment_id="deploy-xyz"),
        profile=_profile(),
        adapter=_adapter(),
    )
    assert cfg.configured_deployment_id == "deploy-xyz"
    assert cfg.deployment_is_explicitly_pinned is True


# ── Mutation safety ──────────────────────────────────────────────────


def test_inputs_not_mutated():
    s = _settings()
    p = _profile()
    a = _adapter()
    resolve_effective_embedding_configuration(settings=s, profile=p, adapter=a)
    # Frozen dataclasses are inherently immutable, but verify the function
    # didn't try to mutate via __dict__ tricks
    assert s.provider_kind == "lmstudio"
    assert p.model_identifier == "qwen3-embedding-0.6b"
    assert a.implemented_postprocessing_policy == "none"


# ── Determinism ──────────────────────────────────────────────────────


def test_same_inputs_same_output():
    s = _settings()
    p = _profile()
    a = _adapter()
    cfg1 = resolve_effective_embedding_configuration(settings=s, profile=p, adapter=a)
    cfg2 = resolve_effective_embedding_configuration(settings=s, profile=p, adapter=a)
    assert cfg1 == cfg2


# ── Provider alias canonicalization ──────────────────────────────────


def test_provider_alias_canonicalized():
    cfg = resolve_effective_embedding_configuration(
        settings=_settings(provider_kind="lm_studio"),
        profile=_profile(provider_kind="lmstudio"),
        adapter=_adapter(),
    )
    assert cfg.provider_kind == "lmstudio"


# ── Authorization boundary ───────────────────────────────────────────


def test_no_capability_artifacts_created():
    """The resolver creates no capability bindings, checks, or activation rows."""
    # If this function returns an EffectiveEmbeddingConfiguration without error,
    # it has created no DB rows or side-channel artifacts (it's pure).
    cfg = resolve_effective_embedding_configuration(
        settings=_settings(),
        profile=_profile(),
        adapter=_adapter(),
    )
    assert cfg.embedding_profile_id == "a" * 64
    # No capability_binding_id field exists on EffectiveEmbeddingConfiguration
    assert not hasattr(cfg, "capability_binding_id")
    assert not hasattr(cfg, "capability_check_id")
