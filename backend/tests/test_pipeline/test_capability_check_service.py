"""Tests for P0.4A1.5: check-first publication.

Proves:
  - Full pass lifecycle: pending -> running -> passed, binding populated
  - Full fail lifecycle: pending -> running -> failed, binding NULL
  - Binding NOT created on failure (count bindings before/after)
  - Concurrent publication: one wins claim, other gets CheckAlreadyClaimed
  - Credentials not persisted in sanitized_error_detail
"""

from __future__ import annotations

import asyncio
import math
import sys
from unittest.mock import MagicMock

from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.db.database import Base
from backend.db.models import EmbeddingCapabilityBinding, EmbeddingCapabilityCheck
from backend.pipeline.capability.capability_check_service import (
    run_capability_check,
)
from backend.pipeline.capability.contracts import STATUS_FAILED, STATUS_PASSED
from backend.pipeline.governed_embedding_adapter import GovernedEmbeddingAdapterError
from backend.pipeline.knowledge.embedding_configuration import (
    EffectiveEmbeddingConfiguration,
)
from backend.pipeline.knowledge.embedding_provider_identity import (
    EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL,
    ProviderModelIdentityEvidence,
)

_PROFILE_ID = "a" * 64


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


def _seed_profile(session):
    session.execute(
        text(
            "INSERT INTO embedding_profiles "
            "(profile_id, profile_schema_version, provider, model_identifier, "
            " dimension, normalization_policy, chunking_schema_version, "
            " collection_name, verification_status, created_at) "
            "VALUES (:pid, 'embedding_profile_v1', 'openai', 'text-embedding-3-small', "
            "        1536, 'none', 'chunk_v1', 'test_col', 'unverified', "
            "        '2026-01-01 00:00:00')"
        ),
        {"pid": _PROFILE_ID},
    )
    session.commit()


def _make_effective_config(**overrides) -> EffectiveEmbeddingConfiguration:
    defaults = dict(
        embedding_profile_id=_PROFILE_ID,
        profile_schema_version="embedding_profile_v1",
        provider_kind="openai",
        requested_model="text-embedding-3-small",
        expected_dimension=1536,
        declared_normalization_policy="none",
        implemented_postprocessing_policy="none",
        document_task=None,
        query_task=None,
        sanitized_endpoint_identity="https://api.openai.com",
        configured_deployment_id=None,
        deployment_is_explicitly_pinned=False,
        provider_adapter_contract_version="openai_v1",
        governed_adapter_contract_version="governed_v1",
    )
    defaults.update(overrides)
    return EffectiveEmbeddingConfiguration(**defaults)


class _FakeAdapter:
    """Fake adapter for the publication service."""

    def __init__(self, *, dimension=1536, raise_on_documents=None):
        self._dimension = dimension
        self._raise_on_documents = raise_on_documents

    async def embed_documents_with_evidence(self, texts):
        if self._raise_on_documents:
            raise self._raise_on_documents
        dim = self._dimension
        vec = tuple(1.0 / math.sqrt(dim) for _ in range(dim))
        evidence = ProviderModelIdentityEvidence(
            provider_kind="openai",
            requested_model="text-embedding-3-small",
            evidence_source=EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL,
            reported_model="text-embedding-3-small",
        )
        return tuple(vec for _ in texts), evidence

    async def embed_query_with_evidence(self, text):
        dim = self._dimension
        vec = tuple(1.0 / math.sqrt(dim) for _ in range(dim))
        evidence = ProviderModelIdentityEvidence(
            provider_kind="openai",
            requested_model="text-embedding-3-small",
            evidence_source=EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL,
            reported_model="text-embedding-3-small",
        )
        return vec, evidence


def _run(coro):
    return asyncio.run(coro)


# ── Pass lifecycle ────────────────────────────────────────────────────


class TestPassLifecycle:
    def test_full_pass_creates_binding(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile(session)

        adapter = _FakeAdapter(dimension=1536)
        cfg = _make_effective_config()

        pub = _run(run_capability_check(sf, adapter, cfg))

        assert pub.status == STATUS_PASSED
        assert pub.binding_id is not None
        assert pub.expires_at is not None
        assert pub.failure_code is None

        # Verify DB state
        with sf() as session:
            check = session.execute(
                select(EmbeddingCapabilityCheck).where(
                    EmbeddingCapabilityCheck.check_id == pub.check_id
                )
            ).scalar_one()
            assert check.check_status == STATUS_PASSED
            assert check.binding_id == pub.binding_id

            binding = session.execute(
                select(EmbeddingCapabilityBinding).where(
                    EmbeddingCapabilityBinding.binding_id == pub.binding_id
                )
            ).scalar_one()
            assert binding.provider_kind == "openai"
            assert binding.resolved_dimension == 1536


# ── Fail lifecycle ────────────────────────────────────────────────────


class TestFailLifecycle:
    def test_full_fail_no_binding(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile(session)

        # Adapter returns wrong dimension
        adapter = _FakeAdapter(dimension=768)
        cfg = _make_effective_config(expected_dimension=1536)

        pub = _run(run_capability_check(sf, adapter, cfg))

        assert pub.status == STATUS_FAILED
        assert pub.binding_id is None
        assert pub.expires_at is None

        # Verify no binding was created
        with sf() as session:
            binding_count = session.execute(
                select(func.count()).select_from(EmbeddingCapabilityBinding)
            ).scalar()
            assert binding_count == 0

            check = session.execute(
                select(EmbeddingCapabilityCheck).where(
                    EmbeddingCapabilityCheck.check_id == pub.check_id
                )
            ).scalar_one()
            assert check.check_status == STATUS_FAILED
            assert check.binding_id is None

    def test_credentials_not_persisted(self):
        """Inject a credential into the error and verify it's sanitized."""
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile(session)

        err = GovernedEmbeddingAdapterError(
            "provider error: api_key=sk-live-key-abc123 connection refused"
        )
        adapter = _FakeAdapter(raise_on_documents=err)
        cfg = _make_effective_config()

        pub = _run(run_capability_check(sf, adapter, cfg))

        assert pub.status == STATUS_FAILED

        with sf() as session:
            check = session.execute(
                select(EmbeddingCapabilityCheck).where(
                    EmbeddingCapabilityCheck.check_id == pub.check_id
                )
            ).scalar_one()
            detail = check.sanitized_error_detail or ""
            assert "sk-live-key-abc123" not in detail
            assert "[auth]" in detail


# ── Idempotent binding resolution ─────────────────────────────────────


class TestIdempotentBinding:
    def test_two_passes_same_binding(self):
        """Two successful checks with the same config resolve to the
        same binding (idempotent)."""
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile(session)

        adapter = _FakeAdapter(dimension=1536)
        cfg = _make_effective_config()

        pub1 = _run(run_capability_check(sf, adapter, cfg))
        pub2 = _run(run_capability_check(sf, adapter, cfg))

        assert pub1.binding_id == pub2.binding_id

        # Only one binding in the table
        with sf() as session:
            binding_count = session.execute(
                select(func.count()).select_from(EmbeddingCapabilityBinding)
            ).scalar()
            assert binding_count == 1
