"""P0.4A3.4: Clean-deployment bootstrap proof.

Proves that a clean deployment (empty database, no capability claims)
starts without fabricated truth, and that the first verification
creates the first binding/check through the governed path.

Required initial posture (clean DB):
  capability checks       0
  capability bindings     0
  activations             0
  cutovers                0
  v2 vector records       0
  historical backfills    0

Required behavior:
  - No capability claims exist at startup
  - Governed embedding without a verified runtime fails closed
  - First verification creates the first check and binding
  - The unverified probe context is reachable only through the
    capability verification service / CLI / explicit tests
"""

from __future__ import annotations

import asyncio
import math
import sys
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

import backend.db.models
from backend.db.database import Base
from backend.db.models import (
    EmbeddingBindingCutover,
    EmbeddingCapabilityBinding,
    EmbeddingCapabilityCheck,
    EmbeddingProfileBindingActivation,
    VectorIndexRecord,
)
from backend.pipeline.capability.capability_check_service import (
    run_capability_check,
)
from backend.pipeline.capability.capability_errors import (
    CapabilityAuthorizationError,
)
from backend.pipeline.capability.verified_embedding_runtime import (
    build_verified_embedding_runtime,
)
from backend.pipeline.capability.lifecycle_posture import (
    PHASE_VERIFICATION_REQUIRED,
    evaluate_lifecycle_posture,
)
from backend.pipeline.governed_embedding_adapter import GovernedEmbeddingAdapter
from backend.pipeline.knowledge.embedding_configuration import (
    EffectiveEmbeddingConfiguration,
    EmbeddingAdapterCapabilitySnapshot,
    EmbeddingProfileSnapshot,
    EmbeddingRuntimeSettingsSnapshot,
    resolve_effective_embedding_configuration,
)
from backend.pipeline.knowledge.embedding_provider_identity import (
    EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL,
    ProviderModelIdentityEvidence,
)
from backend.pipeline.knowledge.embedding_service import EmbeddingService
from backend.pipeline.vector_contracts import VECTOR_INDEX_V1

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
    session.execute(text(
        "INSERT INTO embedding_profiles "
        "(profile_id, profile_schema_version, provider, model_identifier, "
        " dimension, normalization_policy, chunking_schema_version, "
        " collection_name, verification_status, created_at) "
        "VALUES (:pid, 'embedding_profile_v1', 'openai', 'm', 1536, 'none', "
        "        'chunk_v1', 'test_col', 'unverified', '2026-01-01 00:00:00')"
    ), {"pid": _PROFILE_ID})
    session.commit()


def _make_effective_config() -> EffectiveEmbeddingConfiguration:
    return EffectiveEmbeddingConfiguration(
        embedding_profile_id=_PROFILE_ID,
        profile_schema_version="embedding_profile_v1",
        provider_kind="openai",
        requested_model="text-embedding-3-small",
        expected_dimension=4,
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


class _ControlledProvider:
    """Deterministic test provider — returns stable vectors + evidence."""

    def __init__(self, dimension: int = 4):
        self._dim = dimension
        self.request_count = 0

    async def embed(self, texts):
        self.request_count += 1
        return [self._vector() for _ in texts]

    async def embed_with_evidence(self, texts):
        self.request_count += 1
        from backend.pipeline.knowledge.embedding_provider_identity import (
            ProviderEmbeddingBatch,
        )
        return ProviderEmbeddingBatch(
            embeddings=tuple(self._vector() for _ in texts),
            identity_evidence=ProviderModelIdentityEvidence(
                provider_kind="openai",
                requested_model="text-embedding-3-small",
                evidence_source=EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL,
                reported_model="text-embedding-3-small",
            ),
        )

    def _vector(self):
        val = 0.5
        return [val] * self._dim

    @property
    def dimension(self):
        return self._dim

    @property
    def provider_name(self):
        return "openai:controlled"


def _make_adapter(provider, dim=4):
    emb_service = EmbeddingService(provider)
    return GovernedEmbeddingAdapter(
        embedding_service=emb_service,
        provider_kind="openai",
        requested_model="text-embedding-3-small",
        configured_dimension=dim,
    )


def _run(coro):
    return asyncio.run(coro)


# ── 1. Clean deployment: zero capability claims ─────────────────────


class TestCleanDeploymentZeroClaims:
    def test_no_capability_claims_on_clean_db(self):
        """A freshly created database has zero capability claims."""
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)

        with sf() as session:
            checks = session.execute(
                select(func.count()).select_from(EmbeddingCapabilityCheck)
            ).scalar()
            bindings = session.execute(
                select(func.count()).select_from(EmbeddingCapabilityBinding)
            ).scalar()
            activations = session.execute(
                select(func.count()).select_from(EmbeddingProfileBindingActivation)
            ).scalar()
            cutovers = session.execute(
                select(func.count()).select_from(EmbeddingBindingCutover)
            ).scalar()
            v2_vectors = session.execute(
                select(func.count()).select_from(VectorIndexRecord).where(
                    VectorIndexRecord.index_schema_version == "vector_index_v2"
                )
            ).scalar()

        assert checks == 0, f"expected 0 checks, got {checks}"
        assert bindings == 0, f"expected 0 bindings, got {bindings}"
        assert activations == 0, f"expected 0 activations, got {activations}"
        assert cutovers == 0, f"expected 0 cutovers, got {cutovers}"
        assert v2_vectors == 0, f"expected 0 v2 vectors, got {v2_vectors}"

    def test_clean_posture_is_verification_required(self):
        """A profile with no checks reports verification_required."""
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)

        with sf() as session:
            _seed_profile(session)
            posture = evaluate_lifecycle_posture(
                session, embedding_profile_id=_PROFILE_ID,
            )

        assert posture.readiness_phase == PHASE_VERIFICATION_REQUIRED
        assert posture.capability_health_status == "no_check"


# ── 2. Governed embedding without verification fails closed ─────────


class TestUnverifiedEmbeddingFailsClosed:
    def test_no_check_denies_verified_runtime(self):
        """Without a passed capability check, VerifiedEmbeddingRuntime
        construction must fail with capability_check_not_found."""
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)

        with sf() as session:
            _seed_profile(session)

        cfg = _make_effective_config()
        provider = _ControlledProvider(dimension=4)
        adapter = _make_adapter(provider, dim=4)

        with pytest.raises(CapabilityAuthorizationError) as exc:
            build_verified_embedding_runtime(
                embedding_adapter=adapter,
                effective_config=cfg,
                session_factory=sf,
            )
        assert exc.value.code == "capability_check_not_found"


# ── 3. First verification creates first check + binding ──────────────


class TestFirstVerification:
    def test_first_verification_creates_check_and_binding(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)

        with sf() as session:
            _seed_profile(session)

        cfg = _make_effective_config()
        provider = _ControlledProvider(dimension=4)
        adapter = _make_adapter(provider, dim=4)

        # Before: zero claims
        with sf() as session:
            assert session.execute(
                select(func.count()).select_from(EmbeddingCapabilityCheck)
            ).scalar() == 0
            assert session.execute(
                select(func.count()).select_from(EmbeddingCapabilityBinding)
            ).scalar() == 0

        pub = _run(run_capability_check(sf, adapter, cfg))

        # After: one check, one binding
        assert pub.status == "passed"
        assert pub.binding_id is not None

        with sf() as session:
            assert session.execute(
                select(func.count()).select_from(EmbeddingCapabilityCheck)
            ).scalar() == 1
            assert session.execute(
                select(func.count()).select_from(EmbeddingCapabilityBinding)
            ).scalar() == 1

    def test_repeated_verification_no_duplicate_binding(self):
        """A second verification under the same config does not create
        a duplicate binding."""
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)

        with sf() as session:
            _seed_profile(session)

        cfg = _make_effective_config()
        provider = _ControlledProvider(dimension=4)
        adapter = _make_adapter(provider, dim=4)

        pub1 = _run(run_capability_check(sf, adapter, cfg))
        pub2 = _run(run_capability_check(sf, adapter, cfg))

        assert pub1.binding_id == pub2.binding_id

        with sf() as session:
            assert session.execute(
                select(func.count()).select_from(EmbeddingCapabilityCheck)
            ).scalar() == 2  # two checks
            assert session.execute(
                select(func.count()).select_from(EmbeddingCapabilityBinding)
            ).scalar() == 1  # one binding (idempotent)

    def test_verified_runtime_works_after_first_verification(self):
        """After the first successful verification, the verified runtime
        can be constructed and used for embedding."""
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)

        with sf() as session:
            _seed_profile(session)

        cfg = _make_effective_config()
        provider = _ControlledProvider(dimension=4)
        adapter = _make_adapter(provider, dim=4)

        _run(run_capability_check(sf, adapter, cfg))

        vr = build_verified_embedding_runtime(
            embedding_adapter=adapter,
            effective_config=cfg,
            session_factory=sf,
        )
        assert vr.capability_binding_id is not None

        # Embedding through the verified runtime works
        result = _run(vr.embed_query("test query"))
        assert len(result) == 4
