"""Tests for P0.4A1.8: capability status derivation.

Proves the status vocabulary works correctly for each state:
  no_check, currently_verified, expired, latest_check_failed,
  check_running.
"""

from __future__ import annotations

import asyncio
import math
import sys
from unittest.mock import MagicMock

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.db.database import Base
from backend.pipeline.capability.capability_check_service import (
    run_capability_check,
)
from backend.pipeline.capability.capability_identity import (
    compute_runtime_config_fingerprint,
)
from backend.pipeline.capability.capability_status import (
    STATUS_CURRENTLY_VERIFIED,
    STATUS_EXPIRED,
    STATUS_LATEST_CHECK_FAILED,
    STATUS_NO_CHECK,
    derive_capability_status,
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


def _run(coro):
    return asyncio.run(coro)


class TestDeriveCapabilityStatus:
    def test_no_check(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile(session)

        cfg = _make_effective_config()
        fp = compute_runtime_config_fingerprint(cfg)

        with sf() as session:
            status = derive_capability_status(
                session,
                embedding_profile_id=_PROFILE_ID,
                current_runtime_config_fingerprint=fp,
            )
        assert status.derived_status == STATUS_NO_CHECK

    def test_currently_verified(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile(session)

        cfg = _make_effective_config()
        adapter = _FakeAdapter(1536)
        _run(run_capability_check(sf, adapter, cfg, check_ttl_seconds=3600))

        fp = compute_runtime_config_fingerprint(cfg)
        with sf() as session:
            status = derive_capability_status(
                session,
                embedding_profile_id=_PROFILE_ID,
                current_runtime_config_fingerprint=fp,
            )
        assert status.derived_status == STATUS_CURRENTLY_VERIFIED
        assert status.latest_check_binding_id is not None

    def test_expired(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile(session)

        cfg = _make_effective_config()
        adapter = _FakeAdapter(1536)
        # TTL = 0 seconds → immediately expired
        _run(run_capability_check(sf, adapter, cfg, check_ttl_seconds=0))

        fp = compute_runtime_config_fingerprint(cfg)
        # Need to wait a tiny bit so now > expires_at
        import time
        time.sleep(0.01)

        with sf() as session:
            status = derive_capability_status(
                session,
                embedding_profile_id=_PROFILE_ID,
                current_runtime_config_fingerprint=fp,
            )
        assert status.derived_status == STATUS_EXPIRED

    def test_latest_check_failed(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile(session)

        cfg = _make_effective_config()
        fail_adapter = _FakeAdapter(768)  # wrong dimension → fail
        _run(run_capability_check(sf, fail_adapter, cfg))

        fp = compute_runtime_config_fingerprint(cfg)
        with sf() as session:
            status = derive_capability_status(
                session,
                embedding_profile_id=_PROFILE_ID,
                current_runtime_config_fingerprint=fp,
            )
        assert status.derived_status == STATUS_LATEST_CHECK_FAILED
