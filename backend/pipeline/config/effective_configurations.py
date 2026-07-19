"""Bounded effective domain configuration objects (P0.5.3).

These replace raw Settings reads in production consumers. Each domain
gets one frozen object containing only its material fields, resolved
through the effective-value resolver.

P0.4's EffectiveEmbeddingConfiguration remains authoritative for
embeddings — it is registered rather than redesigned.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EffectiveSearchConfiguration:
    """Material search and corpus configuration."""

    pubmed_enabled: bool
    crossref_enabled: bool
    openalex_email: str
    semantic_scholar_api_key_present: bool
    pubmed_api_key_present: bool


@dataclass(frozen=True)
class EffectiveRetrievalConfiguration:
    """Material retrieval and ranking configuration."""

    retrieval_mode: str
    reranker_enabled: bool
    reranker_type: str
    bm25_persist_dir: str


@dataclass(frozen=True)
class EffectiveGenerationConfiguration:
    """Material generation and provider configuration."""

    default_provider: str
    generation_rounds: int
    ideas_per_round: int


@dataclass(frozen=True)
class EffectiveOperationalConfiguration:
    """Material operational configuration."""

    caching_enabled: bool
    caching_type: str
    resilience_enabled: bool
    embedding_batch_size: int


@dataclass(frozen=True)
class EffectiveGovernanceConfiguration:
    """Material governance configuration."""

    governance_enabled: bool
    budget_enabled: bool
    budget_max_cost_usd: float
    budget_max_tokens: int


@dataclass(frozen=True)
class EffectiveKnowledgeConfiguration:
    """Material knowledge-graph and tool configuration."""

    graph_rag_enabled: bool
    tool_discovery_enabled: bool
    memory_enabled: bool


@dataclass(frozen=True)
class EffectiveAutonomyConfiguration:
    """Material autonomy configuration."""

    autonomy_enabled: bool


@dataclass(frozen=True)
class EffectiveDomainConfigurations:
    """All domain effective configurations in one composition root.

    Built once at application startup from Settings. Passed to the
    service registry instead of the raw Settings object.
    """

    search: EffectiveSearchConfiguration
    retrieval: EffectiveRetrievalConfiguration
    generation: EffectiveGenerationConfiguration
    operational: EffectiveOperationalConfiguration
    governance: EffectiveGovernanceConfiguration
    knowledge: EffectiveKnowledgeConfiguration
    autonomy: EffectiveAutonomyConfiguration


def build_effective_domain_configurations(settings: Any) -> EffectiveDomainConfigurations:
    """Build domain configurations from a Settings instance.

    This is the composition root: raw sources → Settings → domain
    configurations → service registry.

    No local fallback defaults — every value comes from the registry
    owner (Settings), which is the single canonical source.
    """
    return EffectiveDomainConfigurations(
        search=EffectiveSearchConfiguration(
            pubmed_enabled=settings.pubmed_enabled,
            crossref_enabled=settings.crossref_enabled,
            openalex_email=settings.openalex_email,
            semantic_scholar_api_key_present=bool(settings.semantic_scholar_api_key),
            pubmed_api_key_present=bool(settings.pubmed_api_key),
        ),
        retrieval=EffectiveRetrievalConfiguration(
            retrieval_mode=settings.retrieval_mode,
            reranker_enabled=settings.reranker_enabled,
            reranker_type=settings.reranker_type,
            bm25_persist_dir=settings.bm25_persist_dir,
        ),
        generation=EffectiveGenerationConfiguration(
            default_provider=settings.default_provider,
            generation_rounds=settings.generation_rounds,
            ideas_per_round=settings.ideas_per_round,
        ),
        operational=EffectiveOperationalConfiguration(
            caching_enabled=settings.caching_enabled,
            caching_type=settings.caching_type,
            resilience_enabled=settings.resilience_enabled,
            embedding_batch_size=settings.embedding_batch_size,
        ),
        governance=EffectiveGovernanceConfiguration(
            governance_enabled=settings.governance_enabled,
            budget_enabled=settings.budget_enabled,
            budget_max_cost_usd=settings.budget_max_cost_usd,
            budget_max_tokens=settings.budget_max_tokens,
        ),
        knowledge=EffectiveKnowledgeConfiguration(
            graph_rag_enabled=settings.graph_rag_enabled,
            tool_discovery_enabled=settings.tool_discovery_enabled,
            memory_enabled=settings.memory_enabled,
        ),
        autonomy=EffectiveAutonomyConfiguration(
            autonomy_enabled=settings.autonomy_enabled,
        ),
    )
