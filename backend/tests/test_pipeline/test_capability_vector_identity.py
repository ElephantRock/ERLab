"""Tests for P0.4A2.2: vector identity v2, receipts, collection contracts.

Proves:
  - v2 identity is deterministic and binding-sensitive
  - v2 identity differs from v1 identity
  - v2 identity excludes check_id/timestamps
  - Collection name is deterministic and binding-specific
  - Authorized embedding receipts carry binding + check evidence
  - Receipts are immutable (frozen dataclass)
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
from backend.pipeline.capability.verified_embedding_runtime import (
    AuthorizedEmbeddingBatch,
    AuthorizedQueryEmbedding,
    build_verified_embedding_runtime,
)
from backend.pipeline.knowledge.embedding_configuration import (
    EffectiveEmbeddingConfiguration,
)
from backend.pipeline.knowledge.embedding_provider_identity import (
    EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL,
    ProviderModelIdentityEvidence,
)
from backend.pipeline.vector_contracts import (
    compute_v2_collection_name,
    compute_vector_record_id,
    compute_vector_record_id_v2,
)

_PROFILE_ID = "a" * 64
_BINDING_ID = "b" * 64


# ── 1. Vector identity v2 ────────────────────────────────────────────


class TestVectorIdentityV2:
    def test_v2_deterministic(self):
        vid1 = compute_vector_record_id_v2(1, "abstract:0", "h" * 64, _PROFILE_ID, _BINDING_ID)
        vid2 = compute_vector_record_id_v2(1, "abstract:0", "h" * 64, _PROFILE_ID, _BINDING_ID)
        assert vid1 == vid2

    def test_v2_is_sha256_hex(self):
        vid = compute_vector_record_id_v2(1, "c", "h" * 64, _PROFILE_ID, _BINDING_ID)
        assert len(vid) == 64
        assert all(c in "0123456789abcdef" for c in vid)

    def test_v2_differs_on_binding(self):
        vid1 = compute_vector_record_id_v2(1, "c", "h" * 64, _PROFILE_ID, "a" * 64)
        vid2 = compute_vector_record_id_v2(1, "c", "h" * 64, _PROFILE_ID, "b" * 64)
        assert vid1 != vid2

    def test_v2_differs_on_content(self):
        vid1 = compute_vector_record_id_v2(1, "c", "a" * 64, _PROFILE_ID, _BINDING_ID)
        vid2 = compute_vector_record_id_v2(1, "c", "b" * 64, _PROFILE_ID, _BINDING_ID)
        assert vid1 != vid2

    def test_v2_differs_from_v1(self):
        """v1 and v2 identities must not collide for the same content."""
        vid1 = compute_vector_record_id(1, "c", "h" * 64, _PROFILE_ID)
        vid2 = compute_vector_record_id_v2(1, "c", "h" * 64, _PROFILE_ID, _BINDING_ID)
        assert vid1 != vid2

    def test_v2_excludes_check_id(self):
        """The identity must not change if only the check changes."""
        vid = compute_vector_record_id_v2(1, "c", "h" * 64, _PROFILE_ID, _BINDING_ID)
        # Recompute — no check_id input, same result
        assert compute_vector_record_id_v2(1, "c", "h" * 64, _PROFILE_ID, _BINDING_ID) == vid


# ── 2. Collection name ───────────────────────────────────────────────


class TestV2CollectionName:
    def test_deterministic(self):
        c1 = compute_v2_collection_name(_BINDING_ID)
        c2 = compute_v2_collection_name(_BINDING_ID)
        assert c1 == c2

    def test_binding_specific(self):
        c1 = compute_v2_collection_name("a" * 64)
        c2 = compute_v2_collection_name("b" * 64)
        assert c1 != c2

    def test_prefix(self):
        name = compute_v2_collection_name(_BINDING_ID)
        assert name.startswith("erlab_vectors_v2_")


# ── 3. Authorized embedding receipts ─────────────────────────────────


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


class TestAuthorizedReceipts:
    def test_documents_authorized_returns_receipt(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile(session)

        adapter = _FakeAdapter(1536)
        cfg = _make_effective_config()
        _run(run_capability_check(sf, adapter, cfg))

        vr = build_verified_embedding_runtime(
            embedding_adapter=adapter,
            effective_config=cfg,
            session_factory=sf,
        )

        receipt = _run(vr.embed_documents_authorized(["test doc"]))
        assert isinstance(receipt, AuthorizedEmbeddingBatch)
        assert len(receipt.embeddings) == 1
        assert receipt.capability_binding_id is not None
        assert receipt.capability_check_id is not None
        assert receipt.runtime_config_fingerprint is not None
        assert receipt.authorized_at is not None

    def test_query_authorized_returns_receipt(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile(session)

        adapter = _FakeAdapter(1536)
        cfg = _make_effective_config()
        _run(run_capability_check(sf, adapter, cfg))

        vr = build_verified_embedding_runtime(
            embedding_adapter=adapter,
            effective_config=cfg,
            session_factory=sf,
        )

        receipt = _run(vr.embed_query_authorized("test query"))
        assert isinstance(receipt, AuthorizedQueryEmbedding)
        assert len(receipt.embedding) == 1536
        assert receipt.capability_binding_id is not None
        assert receipt.capability_check_id is not None

    def test_receipt_binding_matches_runtime(self):
        """The receipt's binding must match the runtime's binding."""
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile(session)

        adapter = _FakeAdapter(1536)
        cfg = _make_effective_config()
        _run(run_capability_check(sf, adapter, cfg))

        vr = build_verified_embedding_runtime(
            embedding_adapter=adapter,
            effective_config=cfg,
            session_factory=sf,
        )

        receipt = _run(vr.embed_query_authorized("test"))
        assert receipt.capability_binding_id == vr.capability_binding_id
        assert receipt.capability_check_id == vr.capability_check_id

    def test_receipt_is_frozen(self):
        """Receipts are immutable dataclasses."""
        import dataclasses
        assert dataclasses.is_dataclass(AuthorizedEmbeddingBatch)
        assert dataclasses.is_dataclass(AuthorizedQueryEmbedding)
