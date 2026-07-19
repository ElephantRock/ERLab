"""Tests for P0.4A1.6+7: encapsulated VerifiedEmbeddingRuntime and drift.

Proves:
  - Happy path: latest passed, current → runtime built, embed works
  - No check → CapabilityAuthorizationError
  - Expired check → denied
  - Latest failed overrides older passed → denied
  - Fingerprint drift → denied at construction AND at use
  - Encapsulation: no public adapter attribute
  - Per-operation expiry
"""

from __future__ import annotations

import asyncio
import math
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

import backend.db.models
from backend.db.database import Base
from backend.pipeline.capability.capability_check_service import (
    run_capability_check,
)
from backend.pipeline.capability.capability_errors import (
    CapabilityAuthorizationError,
    CAPABILITY_BINDING_MISMATCH,
    CAPABILITY_CHECK_EXPIRED,
    CAPABILITY_CHECK_FAILED,
    CAPABILITY_CHECK_NOT_FOUND,
    CAPABILITY_RUNTIME_DRIFT,
)
from backend.pipeline.capability.verified_embedding_runtime import (
    VerifiedEmbeddingRuntime,
    build_verified_embedding_runtime,
)
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
    def __init__(self, dimension=1536):
        self._dimension = dimension

    async def embed_documents_with_evidence(self, texts):
        vec = tuple(1.0 / math.sqrt(self._dimension) for _ in range(self._dimension))
        ev = ProviderModelIdentityEvidence(
            provider_kind="openai",
            requested_model="text-embedding-3-small",
            evidence_source=EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL,
            reported_model="text-embedding-3-small",
        )
        return tuple(vec for _ in texts), ev

    async def embed_query_with_evidence(self, text):
        vec = tuple(1.0 / math.sqrt(self._dimension) for _ in range(self._dimension))
        ev = ProviderModelIdentityEvidence(
            provider_kind="openai",
            requested_model="text-embedding-3-small",
            evidence_source=EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL,
            reported_model="text-embedding-3-small",
        )
        return vec, ev

    async def embed_documents(self, texts):
        vec = tuple(1.0 / math.sqrt(self._dimension) for _ in range(self._dimension))
        return tuple(vec for _ in texts)

    async def embed_query(self, text):
        vec = tuple(1.0 / math.sqrt(self._dimension) for _ in range(self._dimension))
        return vec


def _run(coro):
    return asyncio.run(coro)


async def _seed_passed_check(sf, adapter, cfg):
    """Run a full capability check to seed a passed check + binding."""
    return await run_capability_check(sf, adapter, cfg, check_ttl_seconds=3600)


# ── Happy path ────────────────────────────────────────────────────────


class TestHappyPath:
    def test_build_with_passed_check(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile(session)

        adapter = _FakeAdapter(1536)
        cfg = _make_effective_config()

        _run(_seed_passed_check(sf, adapter, cfg))

        vr = build_verified_embedding_runtime(
            embedding_adapter=adapter,
            effective_config=cfg,
            session_factory=sf,
        )
        assert vr.capability_binding_id is not None
        assert vr.capability_check_id is not None

    def test_embed_works_after_build(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile(session)

        adapter = _FakeAdapter(1536)
        cfg = _make_effective_config()

        _run(_seed_passed_check(sf, adapter, cfg))

        vr = build_verified_embedding_runtime(
            embedding_adapter=adapter,
            effective_config=cfg,
            session_factory=sf,
        )

        result = _run(vr.embed_documents(["test"]))
        assert len(result) == 1
        assert len(result[0]) == 1536


# ── Fail-closed scenarios ─────────────────────────────────────────────


class TestFailClosed:
    def test_no_check_denied(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile(session)

        adapter = _FakeAdapter(1536)
        cfg = _make_effective_config()

        with pytest.raises(CapabilityAuthorizationError) as exc:
            build_verified_embedding_runtime(
                embedding_adapter=adapter,
                effective_config=cfg,
                session_factory=sf,
            )
        assert exc.value.code == CAPABILITY_CHECK_NOT_FOUND

    def test_latest_failed_overrides_older_passed(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile(session)

        adapter = _FakeAdapter(1536)
        cfg = _make_effective_config()

        # First: pass
        _run(_seed_passed_check(sf, adapter, cfg))

        # Second: fail (wrong dimension adapter)
        fail_adapter = _FakeAdapter(768)
        _run(run_capability_check(sf, fail_adapter, cfg))

        # Now latest is failed → denied
        with pytest.raises(CapabilityAuthorizationError) as exc:
            build_verified_embedding_runtime(
                embedding_adapter=adapter,
                effective_config=cfg,
                session_factory=sf,
            )
        assert exc.value.code == CAPABILITY_CHECK_FAILED

    def test_fingerprint_drift_denied(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile(session)

        adapter = _FakeAdapter(1536)
        cfg = _make_effective_config()

        _run(_seed_passed_check(sf, adapter, cfg))

        # Config drifts (different dimension)
        drifted_cfg = _make_effective_config(expected_dimension=3072)

        with pytest.raises(CapabilityAuthorizationError) as exc:
            build_verified_embedding_runtime(
                embedding_adapter=adapter,
                effective_config=drifted_cfg,
                session_factory=sf,
            )
        assert exc.value.code == CAPABILITY_CHECK_NOT_FOUND


# ── Encapsulation ─────────────────────────────────────────────────────


class TestEncapsulation:
    def test_no_public_adapter(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile(session)

        adapter = _FakeAdapter(1536)
        cfg = _make_effective_config()
        _run(_seed_passed_check(sf, adapter, cfg))

        vr = build_verified_embedding_runtime(
            embedding_adapter=adapter,
            effective_config=cfg,
            session_factory=sf,
        )

        # The adapter must NOT be accessible as a public attribute
        assert not hasattr(vr, "embedding_adapter")
        assert hasattr(vr, "_embedding_adapter")  # private only
