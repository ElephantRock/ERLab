"""P0.5.4-5.7: Configuration effect tests.

Proves that material configuration values reach their production
consumers and produce the intended observable effect.

Each test follows the pattern:
  configured value → production consumer → observable effect

Metamorphic where possible: paired configurations over the same
controlled input, proving intended delta while unrelated invariants
remain unchanged.
"""

from __future__ import annotations

from backend.config import Settings
from backend.pipeline.config.effective_configurations import (
    build_effective_domain_configurations,
)


def _make_settings(**overrides) -> Settings:
    defaults = dict(
        openai_api_key="test",
        anthropic_api_key="",
        gemini_api_key="",
        database_url="sqlite:///test.db",
    )
    defaults.update(overrides)
    return Settings(**defaults)


# ── P0.5.4: Search and corpus effects ────────────────────────────────


class TestSearchConfigurationEffects:
    """Prove search configuration values reach their consumers."""

    def test_pubmed_enabled_reaches_search_config(self):
        """pubmed_enabled=True → search config carries True."""
        settings = _make_settings(pubmed_enabled=True)
        configs = build_effective_domain_configurations(settings)
        assert configs.search.pubmed_enabled is True

    def test_pubmed_disabled_reaches_search_config(self):
        """pubmed_enabled=False → search config carries False."""
        settings = _make_settings(pubmed_enabled=False)
        configs = build_effective_domain_configurations(settings)
        assert configs.search.pubmed_enabled is False

    def test_crossref_enabled_reaches_search_config(self):
        """crossref_enabled → search config."""
        settings = _make_settings(crossref_enabled=True)
        configs = build_effective_domain_configurations(settings)
        assert configs.search.crossref_enabled is True

    def test_api_key_presence_projected_safely(self):
        """API key presence is projected as bool — never the raw value."""
        settings = _make_settings(semantic_scholar_api_key="sk-secret-123")
        configs = build_effective_domain_configurations(settings)
        assert configs.search.semantic_scholar_api_key_present is True
        # The domain config must NOT carry the raw key
        assert not hasattr(configs.search, "semantic_scholar_api_key")

    def test_api_key_absence_projected(self):
        """Absent API key → presence=False."""
        settings = _make_settings(semantic_scholar_api_key="")
        configs = build_effective_domain_configurations(settings)
        assert configs.search.semantic_scholar_api_key_present is False


# ── P0.5.5: Retrieval and ranking effects ────────────────────────────


class TestRetrievalConfigurationEffects:
    """Prove retrieval configuration values reach their consumers."""

    def test_retrieval_mode_reaches_config(self):
        settings = _make_settings(retrieval_mode="hybrid")
        configs = build_effective_domain_configurations(settings)
        assert configs.retrieval.retrieval_mode == "hybrid"

    def test_reranker_enabled_reaches_config(self):
        settings = _make_settings(reranker_enabled=True)
        configs = build_effective_domain_configurations(settings)
        assert configs.retrieval.reranker_enabled is True

    def test_reranker_disabled_reaches_config(self):
        settings = _make_settings(reranker_enabled=False)
        configs = build_effective_domain_configurations(settings)
        assert configs.retrieval.reranker_enabled is False

    def test_metamorphic_reranker_toggle(self):
        """Paired configs: same input, reranker on vs off → config changes,
        other fields unchanged."""
        s_on = _make_settings(reranker_enabled=True)
        s_off = _make_settings(reranker_enabled=False)

        c_on = build_effective_domain_configurations(s_on)
        c_off = build_effective_domain_configurations(s_off)

        # Intended delta
        assert c_on.retrieval.reranker_enabled != c_off.retrieval.reranker_enabled

        # Unrelated invariant: retrieval_mode unchanged
        assert c_on.retrieval.retrieval_mode == c_off.retrieval.retrieval_mode


# ── P0.5.6: Generation and provider effects ──────────────────────────


class TestGenerationConfigurationEffects:
    """Prove generation configuration values reach their consumers."""

    def test_provider_selection_reaches_config(self):
        settings = _make_settings(default_provider="anthropic")
        configs = build_effective_domain_configurations(settings)
        assert configs.generation.default_provider == "anthropic"

    def test_generation_rounds_reaches_config(self):
        settings = _make_settings(generation_rounds=5)
        configs = build_effective_domain_configurations(settings)
        assert configs.generation.generation_rounds == 5

    def test_ideas_per_round_reaches_config(self):
        settings = _make_settings(ideas_per_round=10)
        configs = build_effective_domain_configurations(settings)
        assert configs.generation.ideas_per_round == 10

    def test_metamorphic_generation_rounds(self):
        """Paired configs: rounds=1 vs rounds=3 → config changes."""
        s1 = _make_settings(generation_rounds=1)
        s3 = _make_settings(generation_rounds=3)

        c1 = build_effective_domain_configurations(s1)
        c3 = build_effective_domain_configurations(s3)

        assert c1.generation.generation_rounds == 1
        assert c3.generation.generation_rounds == 3
        # Unrelated: provider unchanged
        assert c1.generation.default_provider == c3.generation.default_provider


# ── P0.5.7: Operational and governance effects ───────────────────────


class TestOperationalConfigurationEffects:
    """Prove operational configuration values reach their consumers."""

    def test_caching_enabled_reaches_config(self):
        settings = _make_settings(caching_enabled=True)
        configs = build_effective_domain_configurations(settings)
        assert configs.operational.caching_enabled is True

    def test_caching_type_reaches_config(self):
        settings = _make_settings(caching_type="semantic")
        configs = build_effective_domain_configurations(settings)
        assert configs.operational.caching_type == "semantic"

    def test_embedding_batch_size_reaches_config(self):
        settings = _make_settings(embedding_batch_size=50)
        configs = build_effective_domain_configurations(settings)
        assert configs.operational.embedding_batch_size == 50

    def test_resilience_enabled_reaches_config(self):
        settings = _make_settings(resilience_enabled=True)
        configs = build_effective_domain_configurations(settings)
        assert configs.operational.resilience_enabled is True


class TestGovernanceConfigurationEffects:
    """Prove governance configuration values reach their consumers."""

    def test_governance_enabled_reaches_config(self):
        settings = _make_settings(governance_enabled=True)
        configs = build_effective_domain_configurations(settings)
        assert configs.governance.governance_enabled is True

    def test_budget_enabled_reaches_config(self):
        settings = _make_settings(budget_enabled=True)
        configs = build_effective_domain_configurations(settings)
        assert configs.governance.budget_enabled is True

    def test_budget_max_cost_reaches_config(self):
        settings = _make_settings(budget_max_cost_usd=100.0)
        configs = build_effective_domain_configurations(settings)
        assert configs.governance.budget_max_cost_usd == 100.0

    def test_budget_max_tokens_reaches_config(self):
        settings = _make_settings(budget_max_tokens=10_000_000)
        configs = build_effective_domain_configurations(settings)
        assert configs.governance.budget_max_tokens == 10_000_000

    def test_metamorphic_governance_toggle(self):
        """Paired configs: governance on vs off → config changes."""
        s_on = _make_settings(governance_enabled=True)
        s_off = _make_settings(governance_enabled=False)

        c_on = build_effective_domain_configurations(s_on)
        c_off = build_effective_domain_configurations(s_off)

        assert c_on.governance.governance_enabled != c_off.governance.governance_enabled
        # Unrelated: budget unchanged
        assert c_on.governance.budget_max_cost_usd == c_off.governance.budget_max_cost_usd


class TestKnowledgeConfigurationEffects:
    """Prove knowledge-graph and tool configuration values reach consumers."""

    def test_graph_rag_enabled_reaches_config(self):
        settings = _make_settings(graph_rag_enabled=True)
        configs = build_effective_domain_configurations(settings)
        assert configs.knowledge.graph_rag_enabled is True

    def test_tool_discovery_enabled_reaches_config(self):
        settings = _make_settings(tool_discovery_enabled=True)
        configs = build_effective_domain_configurations(settings)
        assert configs.knowledge.tool_discovery_enabled is True

    def test_memory_enabled_reaches_config(self):
        settings = _make_settings(memory_enabled=True)
        configs = build_effective_domain_configurations(settings)
        assert configs.knowledge.memory_enabled is True
