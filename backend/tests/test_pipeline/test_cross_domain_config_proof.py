"""Tests for P0.5B WP4+WP6: durable evidence + cross-domain proof."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

import backend.db.models
from backend.db.database import Base
from backend.db.models import ConfigurationResolutionSnapshot, ConfigurationResolutionItem
from backend.pipeline.config.config_inspector import build_resolution_snapshot
from backend.pipeline.config.effective_resolver import (
    ORIGIN_DEFAULT,
    ORIGIN_ENV,
    ResolvedConfigurationValue,
    SourceCandidate,
    TIER_DECLARED_DEFAULT,
    TIER_DEPLOYMENT,
)


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def _fk(c, r):
        cur = c.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    return engine


class TestDurableEvidence:
    def test_snapshot_tables_exist(self):
        engine = _make_engine()
        from sqlalchemy import inspect
        inspector = inspect(engine)
        assert inspector.has_table("configuration_resolution_snapshots")
        assert inspector.has_table("configuration_resolution_items")

    def test_snapshot_creation(self):
        """Build a resolution snapshot and verify it can be persisted."""
        resolved = {
            "retrieval.retrieval_mode": ResolvedConfigurationValue(
                field_id="retrieval.retrieval_mode",
                effective_value="hybrid",
                value_fingerprint="abc123",
                winning_semantic_tier=TIER_DEPLOYMENT,
                winning_physical_origin=ORIGIN_ENV,
                default_applied=False,
                normalization_applied=False,
                deprecated_alias_used=False,
            ),
            "openai_api_key": ResolvedConfigurationValue(
                field_id="openai_api_key",
                effective_value="sk-secret",
                value_fingerprint="def456",
                winning_semantic_tier=TIER_DEPLOYMENT,
                winning_physical_origin=ORIGIN_ENV,
                default_applied=False,
                normalization_applied=False,
                deprecated_alias_used=False,
            ),
        }

        snapshot = build_resolution_snapshot(
            scope_kind="retrieval_event",
            scope_id="test-event-1",
            resolved_values=resolved,
            field_classifications={
                "retrieval.retrieval_mode": "behavioral",
                "openai_api_key": "credential",
            },
        )

        assert snapshot.scope_kind == "retrieval_event"
        assert snapshot.scope_id == "test-event-1"
        assert len(snapshot.items) == 2

        # Secret field must not have value_representation
        secret_item = [i for i in snapshot.items if i.field_id == "openai_api_key"][0]
        assert secret_item.value_representation is None
        assert secret_item.value_fingerprint is None

        # Non-secret field has representation
        mode_item = [i for i in snapshot.items if i.field_id == "retrieval.retrieval_mode"][0]
        assert mode_item.value_representation is not None
        assert "hybrid" in mode_item.value_representation

    def test_snapshot_persisted_to_db(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)

        resolved = {
            "test.field": ResolvedConfigurationValue(
                field_id="test.field", effective_value=42, value_fingerprint="abc",
                winning_semantic_tier=TIER_DECLARED_DEFAULT,
                winning_physical_origin=ORIGIN_DEFAULT,
                default_applied=True, normalization_applied=False,
                deprecated_alias_used=False,
            ),
        }

        snapshot = build_resolution_snapshot(
            scope_kind="search_execution",
            scope_id="exec-1",
            resolved_values=resolved,
        )

        # Persist
        with sf() as session:
            orm_snapshot = ConfigurationResolutionSnapshot(
                snapshot_id=snapshot.snapshot_id,
                scope_kind=snapshot.scope_kind,
                scope_id=snapshot.scope_id,
                registry_schema_version=snapshot.registry_schema_version,
                precedence_policy_version=snapshot.precedence_policy_version,
                effective_configuration_fingerprint=snapshot.effective_configuration_fingerprint,
            )
            session.add(orm_snapshot)
            session.flush()  # ensure the snapshot row exists before items reference it
            for item in snapshot.items:
                session.add(ConfigurationResolutionItem(
                    snapshot_id=snapshot.snapshot_id,
                    field_id=item.field_id,
                    effect_class=item.effect_class,
                    winning_semantic_tier=item.winning_semantic_tier,
                    winning_physical_origin=item.winning_physical_origin,
                    default_applied=item.default_applied,
                    normalization_applied=item.normalization_applied,
                    value_representation=item.value_representation,
                    value_fingerprint=item.value_fingerprint,
                    shadowed_source_count=item.shadowed_source_count,
                ))
            session.commit()

        # Read back
        with sf() as session:
            saved = session.execute(
                select(ConfigurationResolutionSnapshot).where(
                    ConfigurationResolutionSnapshot.snapshot_id == snapshot.snapshot_id
                )
            ).scalar_one()
            assert saved.scope_kind == "search_execution"
            assert saved.effective_configuration_fingerprint == snapshot.effective_configuration_fingerprint

            items = session.execute(
                select(ConfigurationResolutionItem).where(
                    ConfigurationResolutionItem.snapshot_id == snapshot.snapshot_id
                )
            ).scalars().all()
            assert len(items) == 1
            assert items[0].field_id == "test.field"
            assert items[0].default_applied is True


class TestCrossDomainProof:
    def test_paired_configurations_produce_intended_deltas(self):
        """Two settings with different reranker_enabled should produce
        different effective configs — proving configuration reaches domain."""
        from backend.config import Settings
        from backend.pipeline.config.effective_configurations import (
            build_effective_domain_configurations,
        )

        s_on = Settings(openai_api_key="test", database_url="sqlite:///test.db", reranker_enabled=True)
        s_off = Settings(openai_api_key="test", database_url="sqlite:///test.db", reranker_enabled=False)

        c_on = build_effective_domain_configurations(s_on)
        c_off = build_effective_domain_configurations(s_off)

        # Intended delta
        assert c_on.retrieval.reranker_enabled != c_off.retrieval.reranker_enabled

        # Unrelated invariant: governance unchanged
        assert c_on.governance.governance_enabled == c_off.governance.governance_enabled

    def test_paired_generation_rounds_delta(self):
        """Different generation_rounds → different effective config."""
        from backend.config import Settings
        from backend.pipeline.config.effective_configurations import (
            build_effective_domain_configurations,
        )

        s1 = Settings(openai_api_key="test", database_url="sqlite:///test.db", generation_rounds=1)
        s3 = Settings(openai_api_key="test", database_url="sqlite:///test.db", generation_rounds=3)

        c1 = build_effective_domain_configurations(s1)
        c3 = build_effective_domain_configurations(s3)

        assert c1.generation.generation_rounds == 1
        assert c3.generation.generation_rounds == 3
        assert c1.generation.default_provider == c3.generation.default_provider
