"""Side-channel capability binding transition (P0.4A2.7).

Namespace policies for the three side channels:

  KG (knowledge_graph_entity)
      Same cutover pattern as paper: dedicated profile → activation-
      eligible target binding → canonical entity snapshot → binding-
      specific collection rebuild.

  Tool (tool_description)
      Same pattern: canonical tool-definition snapshot → binding-
      specific rebuild → active-binding switch.

  Cache (llm_cache_key)
      Disposable — no durable cutover ledger needed. Namespace by:
        activation-eligible binding → namespace by capability_binding_id
        alias-only binding → namespace by binding_id + check_id
      Cache lifetime cannot exceed check expiry for alias-only bindings.
      A binding or check namespace change produces an immediate miss.

This module provides the namespace computation functions and the
cross-binding access prevention contract.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SideChannelNamespace:
    """Computed namespace for a side-channel collection."""

    namespace: str
    binding_aware: bool
    check_scoped: bool  # True for alias-only bindings


def compute_cache_namespace(
    *,
    capability_binding_id: str,
    capability_check_id: str | None = None,
    model_resolution_posture: str = "configured_only",
) -> SideChannelNamespace:
    """Compute the semantic cache namespace for a capability binding.

    Activation-eligible binding (exact_revision or configured_match):
      namespace = capability_binding_id
      The cache survives across check refreshes under the same binding.

    Alias-only binding (configured_only):
      namespace = capability_binding_id + capability_check_id
      Cache lifetime cannot exceed check expiry. A fresh check under
      potentially changed provider behavior produces an immediate miss.
    """
    if model_resolution_posture == "configured_only":
        # Alias-only: scope by both binding and check
        if capability_check_id is None:
            raise ValueError(
                "alias-only binding requires capability_check_id for cache namespace"
            )
        return SideChannelNamespace(
            namespace=f"{capability_binding_id[:24]}_{capability_check_id[:24]}",
            binding_aware=True,
            check_scoped=True,
        )

    # Activation-eligible: scope by binding only
    return SideChannelNamespace(
        namespace=capability_binding_id[:24],
        binding_aware=True,
        check_scoped=False,
    )


def compute_kg_collection_name(capability_binding_id: str) -> str:
    """Binding-specific KG entity collection name."""
    return f"kg_entity_embeddings_v3_{capability_binding_id[:24]}"


def compute_tool_collection_name(capability_binding_id: str) -> str:
    """Binding-specific tool-description collection name."""
    return f"tool_embeddings_v2_{capability_binding_id[:24]}"


def is_cross_binding_cache_hit_allowed(
    *,
    insertion_binding_id: str,
    query_binding_id: str,
) -> bool:
    """A cache hit across different bindings is NOT allowed.

    Same prompt + different binding → miss.
    """
    return insertion_binding_id == query_binding_id


def is_cross_check_cache_hit_allowed(
    *,
    insertion_check_id: str,
    query_check_id: str,
    check_scoped: bool,
) -> bool:
    """For alias-only bindings, a cache hit across checks is NOT allowed.

    Same prompt + same alias-only binding + different check → miss.
    """
    if not check_scoped:
        return True  # activation-eligible: check doesn't matter
    return insertion_check_id == query_check_id
