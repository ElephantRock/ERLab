"""Tests for P0.4A2.7: side-channel binding namespace policy."""

from __future__ import annotations

import pytest

from backend.pipeline.capability.side_channel_binding_policy import (
    compute_cache_namespace,
    compute_kg_collection_name,
    compute_tool_collection_name,
    is_cross_binding_cache_hit_allowed,
    is_cross_check_cache_hit_allowed,
)


class TestCacheNamespace:
    def test_activation_eligible_namespace_by_binding(self):
        ns = compute_cache_namespace(
            capability_binding_id="b" * 64,
            model_resolution_posture="configured_match",
        )
        assert ns.binding_aware is True
        assert ns.check_scoped is False
        assert "b" * 24 in ns.namespace

    def test_alias_only_namespace_by_binding_and_check(self):
        ns = compute_cache_namespace(
            capability_binding_id="b" * 64,
            capability_check_id="c" * 64,
            model_resolution_posture="configured_only",
        )
        assert ns.check_scoped is True
        assert "b" * 24 in ns.namespace
        assert "c" * 24 in ns.namespace

    def test_alias_only_without_check_raises(self):
        with pytest.raises(ValueError):
            compute_cache_namespace(
                capability_binding_id="b" * 64,
                capability_check_id=None,
                model_resolution_posture="configured_only",
            )


class TestCrossBindingPrevention:
    def test_cross_binding_not_allowed(self):
        assert not is_cross_binding_cache_hit_allowed(
            insertion_binding_id="a" * 64,
            query_binding_id="b" * 64,
        )

    def test_same_binding_allowed(self):
        assert is_cross_binding_cache_hit_allowed(
            insertion_binding_id="a" * 64,
            query_binding_id="a" * 64,
        )


class TestCrossCheckPrevention:
    def test_alias_only_cross_check_not_allowed(self):
        assert not is_cross_check_cache_hit_allowed(
            insertion_check_id="a" * 64,
            query_check_id="b" * 64,
            check_scoped=True,
        )

    def test_activation_eligible_ignores_check(self):
        assert is_cross_check_cache_hit_allowed(
            insertion_check_id="a" * 64,
            query_check_id="b" * 64,
            check_scoped=False,
        )


class TestCollectionNames:
    def test_kg_collection_name(self):
        name = compute_kg_collection_name("b" * 64)
        assert name.startswith("kg_entity_embeddings_v3_")

    def test_tool_collection_name(self):
        name = compute_tool_collection_name("b" * 64)
        assert name.startswith("tool_embeddings_v2_")
