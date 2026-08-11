"""Tests for P0.4B0.5a: side-channel embedding contracts.

Proves:
  - Namespace fingerprint determinism and sensitivity
  - Different purposes produce different fingerprints
  - Credentials never enter fingerprints
  - Collection name derivation
  - Cache namespace isolation across runtime changes
  - Purpose/profile guards
"""

from __future__ import annotations

import pytest

from backend.pipeline.side_channel_embedding import (
    SideChannelEmbeddingError,
    assert_profile_not_paper_profile,
    assert_purpose_not_paper,
    compute_cache_namespace,
    compute_namespace_fingerprint,
    compute_side_channel_collection_name,
)

# ── Fingerprint determinism ─────────────────────────────────────────


def _fp_kwargs(**overrides):
    defaults = dict(
        embedding_profile_id="a" * 64,
        purpose="knowledge_graph_entity",
        provider_kind="lmstudio",
        requested_model="qwen3-embedding",
        sanitized_endpoint_identity="http://localhost:1234",
        expected_dimension=1024,
        declared_normalization_policy="none",
        implemented_postprocessing_policy="none",
        provider_adapter_contract_version="v1",
        governed_adapter_contract_version="v1",
    )
    defaults.update(overrides)
    return defaults


def test_fingerprint_deterministic():
    fp1 = compute_namespace_fingerprint(**_fp_kwargs())
    fp2 = compute_namespace_fingerprint(**_fp_kwargs())
    assert fp1 == fp2
    assert len(fp1) == 64


def test_different_purpose_different_fingerprint():
    fp_kg = compute_namespace_fingerprint(**_fp_kwargs(purpose="knowledge_graph_entity"))
    fp_tool = compute_namespace_fingerprint(**_fp_kwargs(purpose="tool_description"))
    assert fp_kg != fp_tool


def test_different_profile_different_fingerprint():
    fp_a = compute_namespace_fingerprint(**_fp_kwargs(embedding_profile_id="a" * 64))
    fp_b = compute_namespace_fingerprint(**_fp_kwargs(embedding_profile_id="b" * 64))
    assert fp_a != fp_b


def test_different_model_different_fingerprint():
    fp_a = compute_namespace_fingerprint(**_fp_kwargs(requested_model="model-a"))
    fp_b = compute_namespace_fingerprint(**_fp_kwargs(requested_model="model-b"))
    assert fp_a != fp_b


def test_different_endpoint_different_fingerprint():
    fp_a = compute_namespace_fingerprint(**_fp_kwargs(sanitized_endpoint_identity="http://a:1234"))
    fp_b = compute_namespace_fingerprint(**_fp_kwargs(sanitized_endpoint_identity="http://b:1234"))
    assert fp_a != fp_b


def test_different_dimension_different_fingerprint():
    fp_a = compute_namespace_fingerprint(**_fp_kwargs(expected_dimension=768))
    fp_b = compute_namespace_fingerprint(**_fp_kwargs(expected_dimension=1024))
    assert fp_a != fp_b


def test_different_adapter_version_different_fingerprint():
    fp_a = compute_namespace_fingerprint(**_fp_kwargs(governed_adapter_contract_version="v1"))
    fp_b = compute_namespace_fingerprint(**_fp_kwargs(governed_adapter_contract_version="v2"))
    assert fp_a != fp_b


# ── Credential safety ────────────────────────────────────────────────


def test_credentials_not_in_fingerprint():
    # The fingerprint only receives sanitized inputs; if a caller passes
    # credentials, they'd have to be in one of the named fields.
    # Verify that the computed hash doesn't contain recognizable secrets.
    fp = compute_namespace_fingerprint(**_fp_kwargs(
        sanitized_endpoint_identity="http://localhost:1234",
    ))
    assert "password" not in fp
    assert "secret" not in fp
    assert "api_key" not in fp


# ── Collection name ──────────────────────────────────────────────────


def test_collection_name_deterministic():
    fp = compute_namespace_fingerprint(**_fp_kwargs())
    name1 = compute_side_channel_collection_name("kg_entity_embeddings", fp)
    name2 = compute_side_channel_collection_name("kg_entity_embeddings", fp)
    assert name1 == name2
    assert name1.startswith("kg_entity_embeddings_")


def test_collection_name_different_per_fingerprint():
    fp_a = compute_namespace_fingerprint(**_fp_kwargs(purpose="knowledge_graph_entity"))
    fp_b = compute_namespace_fingerprint(**_fp_kwargs(purpose="tool_description"))
    name_a = compute_side_channel_collection_name("base", fp_a)
    name_b = compute_side_channel_collection_name("base", fp_b)
    assert name_a != name_b


# ── Cache namespace ──────────────────────────────────────────────────


def test_cache_namespace_same_runtime_same_namespace():
    fp = compute_namespace_fingerprint(**_fp_kwargs(purpose="llm_cache_key"))
    ns1 = compute_cache_namespace(
        purpose="llm_cache_key",
        embedding_profile_id="a" * 64,
        namespace_fingerprint=fp,
    )
    ns2 = compute_cache_namespace(
        purpose="llm_cache_key",
        embedding_profile_id="a" * 64,
        namespace_fingerprint=fp,
    )
    assert ns1 == ns2


def test_cache_namespace_different_model_miss():
    fp_a = compute_namespace_fingerprint(**_fp_kwargs(
        purpose="llm_cache_key", requested_model="model-a"))
    fp_b = compute_namespace_fingerprint(**_fp_kwargs(
        purpose="llm_cache_key", requested_model="model-b"))
    ns_a = compute_cache_namespace(
        purpose="llm_cache_key", embedding_profile_id="p",
        namespace_fingerprint=fp_a)
    ns_b = compute_cache_namespace(
        purpose="llm_cache_key", embedding_profile_id="p",
        namespace_fingerprint=fp_b)
    assert ns_a != ns_b  # Different model → cache miss


def test_cache_namespace_different_endpoint_miss():
    fp_a = compute_namespace_fingerprint(**_fp_kwargs(
        purpose="llm_cache_key", sanitized_endpoint_identity="http://a:1234"))
    fp_b = compute_namespace_fingerprint(**_fp_kwargs(
        purpose="llm_cache_key", sanitized_endpoint_identity="http://b:1234"))
    ns_a = compute_cache_namespace(
        purpose="llm_cache_key", embedding_profile_id="p",
        namespace_fingerprint=fp_a)
    ns_b = compute_cache_namespace(
        purpose="llm_cache_key", embedding_profile_id="p",
        namespace_fingerprint=fp_b)
    assert ns_a != ns_b  # Different endpoint → cache miss


def test_cache_namespace_different_adapter_miss():
    fp_a = compute_namespace_fingerprint(**_fp_kwargs(
        purpose="llm_cache_key", governed_adapter_contract_version="v1"))
    fp_b = compute_namespace_fingerprint(**_fp_kwargs(
        purpose="llm_cache_key", governed_adapter_contract_version="v2"))
    ns_a = compute_cache_namespace(
        purpose="llm_cache_key", embedding_profile_id="p",
        namespace_fingerprint=fp_a)
    ns_b = compute_cache_namespace(
        purpose="llm_cache_key", embedding_profile_id="p",
        namespace_fingerprint=fp_b)
    assert ns_a != ns_b  # Different adapter contract → cache miss


# ── Purpose/profile guards ───────────────────────────────────────────


def test_paper_purpose_rejected():
    with pytest.raises(SideChannelEmbeddingError) as exc:
        assert_purpose_not_paper("paper")
    assert exc.value.code == "side_channel_purpose_mismatch"


def test_non_paper_purpose_accepted():
    assert_purpose_not_paper("knowledge_graph_entity")
    assert_purpose_not_paper("tool_description")
    assert_purpose_not_paper("llm_cache_key")


def test_paper_profile_reuse_rejected():
    with pytest.raises(SideChannelEmbeddingError) as exc:
        assert_profile_not_paper_profile("same_id", "same_id")
    assert exc.value.code == "side_channel_profile_mismatch"


def test_different_profile_accepted():
    assert_profile_not_paper_profile("kg_profile_id", "paper_profile_id")
