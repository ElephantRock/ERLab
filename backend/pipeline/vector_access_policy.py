"""Central vector access policy registry (P0.3.4).

Frozen per-call-site policies for every production vector operation.
No production caller may construct backend filters or select scope
modes independently — they load a policy from here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class VectorAccessPolicy:
    """Frozen policy for one production vector operation."""

    policy_schema_version: Literal["vector_access_policy_v1"]
    operation: Literal["index", "retrieve", "delete"]
    scope_mode: Literal[
        "current_run_only",
        "same_domain_prior_runs",
        "global_library",
        "selected_papers",
    ] | None
    allow_partial_index_coverage: bool
    retrieval_key_template: str | None
    embedding_profile_id: str  # filled at runtime from settings


# ── Policy registry ──────────────────────────────────────────────────

_POLICIES: dict[str, VectorAccessPolicy] = {}


def register_policy(key: str, policy: VectorAccessPolicy) -> None:
    _POLICIES[key] = policy


def load_vector_access_policy(
    stage_name: str, operation_key: str,
) -> VectorAccessPolicy:
    """Load a frozen vector access policy for a stage + operation."""
    key = f"{stage_name}:{operation_key}"
    if key not in _POLICIES:
        raise ValueError(
            f"vector access policy not found for {key!r}; "
            f"available: {sorted(_POLICIES.keys())}"
        )
    return _POLICIES[key]


def build_scope_from_policy(
    *,
    run_id: int,
    policy: VectorAccessPolicy,
    embedding_profile_id: str,
    selected_paper_ids: tuple[int, ...] = (),
):
    """Build a VectorRetrievalScope from a policy."""
    from backend.pipeline.vector_contracts import VectorRetrievalScope

    if policy.scope_mode is None:
        raise ValueError(f"policy {policy!r} has no scope_mode for retrieval")

    return VectorRetrievalScope(
        schema_version="vector_scope_v1",
        mode=policy.scope_mode,
        run_id=run_id,
        embedding_profile_id=embedding_profile_id,
        selected_paper_ids=selected_paper_ids,
    )


# ── Default policies (profile_id filled at runtime) ──────────────────

_DEFAULT_PROFILE = "runtime_profile"  # replaced by settings at call time


def _init_default_policies() -> None:
    """Register all default production vector access policies."""

    # Indexing: governed write through vector_indexer
    register_policy("ingestion:index", VectorAccessPolicy(
        policy_schema_version="vector_access_policy_v1",
        operation="index",
        scope_mode=None,
        allow_partial_index_coverage=False,
        retrieval_key_template=None,
        embedding_profile_id=_DEFAULT_PROFILE,
    ))

    # Novelty checking: current run only
    register_policy("novelty_check:retrieve", VectorAccessPolicy(
        policy_schema_version="vector_access_policy_v1",
        operation="retrieve",
        scope_mode="current_run_only",
        allow_partial_index_coverage=False,
        retrieval_key_template="novelty:{idea_key}",
        embedding_profile_id=_DEFAULT_PROFILE,
    ))

    # Synthesis/RAG: current run only
    register_policy("synthesis:retrieve", VectorAccessPolicy(
        policy_schema_version="vector_access_policy_v1",
        operation="retrieve",
        scope_mode="current_run_only",
        allow_partial_index_coverage=False,
        retrieval_key_template="synthesis:{section_key}:{iteration}",
        embedding_profile_id=_DEFAULT_PROFILE,
    ))

    # Literature prior-paper: disabled by default (same_domain_prior_runs when enabled)
    register_policy("literature_prior:retrieve", VectorAccessPolicy(
        policy_schema_version="vector_access_policy_v1",
        operation="retrieve",
        scope_mode="same_domain_prior_runs",
        allow_partial_index_coverage=True,
        retrieval_key_template="literature_prior:{query_key}",
        embedding_profile_id=_DEFAULT_PROFILE,
    ))

    # Reference/citation support: current run only
    register_policy("reference_support:retrieve", VectorAccessPolicy(
        policy_schema_version="vector_access_policy_v1",
        operation="retrieve",
        scope_mode="current_run_only",
        allow_partial_index_coverage=False,
        retrieval_key_template="reference:{claim_key}",
        embedding_profile_id=_DEFAULT_PROFILE,
    ))

    # Knowledge search API: caller must provide explicit scope
    register_policy("knowledge_search:retrieve", VectorAccessPolicy(
        policy_schema_version="vector_access_policy_v1",
        operation="retrieve",
        scope_mode="current_run_only",
        allow_partial_index_coverage=True,
        retrieval_key_template="knowledge_search:{request_id}",
        embedding_profile_id=_DEFAULT_PROFILE,
    ))


# Initialize on import
_init_default_policies()


# ── Mixed-mode enforcement ───────────────────────────────────────────


class MixedVectorAccessModeError(Exception):
    """Governed run used legacy vector path, or vice versa."""


def resolve_profile_id(
    embedding_provider: str,
    model_identifier: str,
    dimension: int,
    normalization_policy: str,
    chunking_schema_version: str,
) -> str:
    """Compute the embedding profile ID from runtime settings."""
    from backend.pipeline.vector_contracts import compute_profile_id
    return compute_profile_id(
        embedding_provider, model_identifier, dimension,
        normalization_policy, chunking_schema_version,
    )
