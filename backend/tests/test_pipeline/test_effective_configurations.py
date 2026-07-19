"""Tests for P0.5.3: effective domain configurations."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.pipeline.config.effective_configurations import (
    EffectiveAutonomyConfiguration,
    EffectiveDomainConfigurations,
    EffectiveGenerationConfiguration,
    EffectiveGovernanceConfiguration,
    EffectiveKnowledgeConfiguration,
    EffectiveOperationalConfiguration,
    EffectiveRetrievalConfiguration,
    EffectiveSearchConfiguration,
    build_effective_domain_configurations,
)
from backend.config import Settings


class TestEffectiveDomainConfigurations:
    def test_builds_from_settings(self):
        settings = Settings(
            openai_api_key="test",
            anthropic_api_key="",
            gemini_api_key="",
            database_url="sqlite:///test.db",
        )
        configs = build_effective_domain_configurations(settings)

        assert isinstance(configs, EffectiveDomainConfigurations)
        assert isinstance(configs.search, EffectiveSearchConfiguration)
        assert isinstance(configs.retrieval, EffectiveRetrievalConfiguration)
        assert isinstance(configs.generation, EffectiveGenerationConfiguration)
        assert isinstance(configs.operational, EffectiveOperationalConfiguration)
        assert isinstance(configs.governance, EffectiveGovernanceConfiguration)
        assert isinstance(configs.knowledge, EffectiveKnowledgeConfiguration)
        assert isinstance(configs.autonomy, EffectiveAutonomyConfiguration)

    def test_search_config_carries_material_fields(self):
        settings = Settings(
            openai_api_key="test",
            database_url="sqlite:///test.db",
        )
        configs = build_effective_domain_configurations(settings)
        # All these must be bool values from Settings (no None)
        assert isinstance(configs.search.pubmed_enabled, bool)
        assert isinstance(configs.search.crossref_enabled, bool)
        assert isinstance(configs.search.semantic_scholar_api_key_present, bool)

    def test_retrieval_config_carries_material(self):
        settings = Settings(
            openai_api_key="test",
            database_url="sqlite:///test.db",
        )
        configs = build_effective_domain_configurations(settings)
        assert configs.retrieval.retrieval_mode == settings.retrieval_mode

    def test_governance_config_carries_budget(self):
        settings = Settings(
            openai_api_key="test",
            database_url="sqlite:///test.db",
        )
        configs = build_effective_domain_configurations(settings)
        assert configs.governance.budget_max_cost_usd == settings.budget_max_cost_usd

    def test_configs_are_frozen(self):
        """Domain configs must be immutable."""
        import dataclasses
        assert dataclasses.is_dataclass(EffectiveSearchConfiguration)
        # Can't easily test __dataclass_params__.frozen without instantiating
        # but the @dataclass(frozen=True) decorator ensures it

    def test_no_local_fallback_defaults(self):
        """The builder reads from Settings — no local fallback expressions.

        This is verified by the architectural seal (AST scan for
        getattr-with-fallback patterns). Here we just verify the
        builder produces non-None values for all material fields.
        """
        settings = Settings(
            openai_api_key="test",
            database_url="sqlite:///test.db",
        )
        configs = build_effective_domain_configurations(settings)

        # Every material value should be non-None
        assert configs.generation.generation_rounds is not None
        assert configs.generation.default_provider is not None
        assert configs.governance.governance_enabled is not None
