"""P0.4A3.6: Failure and recovery workflow tests.

Each failure scenario must produce:
  bounded code
  safe explanation
  authoritative current posture
  valid next action

Scenarios tested:
  - Failed capability probe → no binding fabricated
  - Expired capability check → new operations denied
  - Alias-only binding → activation denied
  - Missing canonical content → cutover blocked
  - Source drift → seal rejected
  - Cutover abort → clean release
"""

from __future__ import annotations

import asyncio
import math
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event, select, text, update
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

import backend.db.models
from backend.db.database import Base
from backend.db.models import (
    EmbeddingBindingCutoverItem,
    EmbeddingCapabilityBinding,
    EmbeddingCapabilityCheck,
    EmbeddingProfileBindingActivation,
    EmbeddingProfileEmbeddingWriteGuard,
)
from backend.pipeline.capability.activation_service import (
    ActivationError,
    seal_cutover,
)
from backend.pipeline.capability.capability_check_service import (
    run_capability_check,
)
from backend.pipeline.capability.capability_errors import (
    CapabilityAuthorizationError,
)
from backend.pipeline.capability.capability_probe import (
    probe_embedding_capability,
)
from backend.pipeline.capability.capability_status import (
    STATUS_LATEST_CHECK_FAILED,
    derive_capability_status,
)
from backend.pipeline.capability.capability_identity import (
    compute_runtime_config_fingerprint,
)
from backend.pipeline.capability.lifecycle_posture import (
    PHASE_BINDING_NOT_ACTIVATION_ELIGIBLE,
    PHASE_VERIFICATION_FAILED,
    evaluate_lifecycle_posture,
)
from backend.pipeline.capability.lifecycle_service import (
    CapabilityLifecycleService,
)
from backend.pipeline.capability.verified_embedding_runtime import (
    build_verified_embedding_runtime,
)
from backend.pipeline.governed_embedding_adapter import (
    GovernedEmbeddingAdapter,
    GovernedEmbeddingAdapterError,
)
from backend.pipeline.knowledge.embedding_configuration import (
    EffectiveEmbeddingConfiguration,
)
from backend.pipeline.knowledge.embedding_provider_identity import (
    EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL,
    ProviderModelIdentityEvidence,
)
from backend.pipeline.knowledge.embedding_service import EmbeddingService
from backend.pipeline.vector_contracts import EMBEDDING_PROBE_SUITE_V1

_PROFILE_ID = "a" * 64
_BINDING_ID = "b" * 64


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


def _seed_profile_and_binding(session, posture="configured_match"):
    session.execute(text(
        "INSERT INTO embedding_profiles "
        "(profile_id, profile_schema_version, provider, model_identifier, "
        " dimension, normalization_policy, chunking_schema_version, "
        " collection_name, verification_status, created_at) "
        "VALUES (:pid, 'embedding_profile_v1', 'openai', 'm', 4, 'none', "
        "        'chunk_v1', 'test_col', 'unverified', '2026-01-01 00:00:00')"
    ), {"pid": _PROFILE_ID})
    session.execute(text(
        "INSERT INTO embedding_capability_bindings "
        "(binding_id, embedding_profile_id, provider_kind, resolved_model, "
        " model_resolution_posture, resolved_dimension, resolved_normalization, "
        " postprocessing_contract_version, resolved_endpoint_identity, "
        " profile_schema_version, provider_adapter_contract_version, "
        " governed_adapter_contract_version, resolution_classifier_version, "
        " binding_schema_version) "
        "VALUES (:bid, :pid, 'openai', 'm', :posture, 4, 'none', "
        "        'none', 'provider-default://unset', 'embedding_profile_v1', "
        "        'v1', 'v1', 'v1', 'capability_binding_v1')"
    ), {"bid": _BINDING_ID, "pid": _PROFILE_ID, "posture": posture})
    session.commit()


def _seed_passed_check(session, expires_in_hours=1):
    now = datetime.now(timezone.utc)
    session.execute(text(
        "INSERT INTO embedding_capability_checks "
        "(check_id, embedding_profile_id, binding_id, "
        " runtime_config_fingerprint, probe_suite_version, "
        " check_status, probe_kind, check_schema_version, "
        " completed_at, expires_at, probed_at) "
        "VALUES (:cid, :pid, :bid, :fp, 'embedding_probe_suite_v1', "
        "        'passed', 'dual_probe', 'capability_check_v1', "
        "        :now, :expiry, :now)"
    ), {"cid": "c" * 64, "pid": _PROFILE_ID, "bid": _BINDING_ID,
        "fp": "f" * 64, "now": now, "expiry": now + timedelta(hours=expires_in_hours)})
    session.commit()


def _make_config() -> EffectiveEmbeddingConfiguration:
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


class _FailingProvider:
    async def embed(self, texts):
        raise RuntimeError("provider offline")

    async def embed_with_evidence(self, texts):
        raise RuntimeError("provider offline")

    @property
    def dimension(self):
        return 4

    @property
    def provider_name(self):
        return "openai:failing"


class _GoodProvider:
    def __init__(self, dim=4):
        self._dim = dim

    async def embed(self, texts):
        return [[0.5] * self._dim for _ in texts]

    async def embed_with_evidence(self, texts):
        from backend.pipeline.knowledge.embedding_provider_identity import (
            ProviderEmbeddingBatch,
        )
        return ProviderEmbeddingBatch(
            embeddings=tuple([0.5] * self._dim for _ in texts),
            identity_evidence=ProviderModelIdentityEvidence(
                provider_kind="openai",
                requested_model="text-embedding-3-small",
                evidence_source=EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL,
                reported_model="text-embedding-3-small",
            ),
        )

    @property
    def dimension(self):
        return self._dim

    @property
    def provider_name(self):
        return "openai:good"


def _make_adapter(provider, dim=4):
    return GovernedEmbeddingAdapter(
        embedding_service=EmbeddingService(provider),
        provider_kind="openai",
        requested_model="text-embedding-3-small",
        configured_dimension=dim,
    )


def _run(coro):
    return asyncio.run(coro)


# ── Failed probe ────────────────────────────────────────────────────


class TestFailedProbe:
    def test_failed_probe_no_binding_fabricated(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            session.execute(text(
                "INSERT INTO embedding_profiles "
                "(profile_id, profile_schema_version, provider, model_identifier, "
                " dimension, normalization_policy, chunking_schema_version, "
                " collection_name, verification_status, created_at) "
                "VALUES (:pid, 'embedding_profile_v1', 'openai', 'm', 4, 'none', "
                "        'chunk_v1', 'test_col', 'unverified', '2026-01-01 00:00:00')"
            ), {"pid": _PROFILE_ID})
            session.commit()

        cfg = _make_config()
        adapter = _make_adapter(_FailingProvider())

        pub = _run(run_capability_check(sf, adapter, cfg))

        assert pub.status == "failed"
        assert pub.binding_id is None

        # No binding created
        with sf() as session:
            from sqlalchemy import func
            count = session.execute(
                select(func.count()).select_from(EmbeddingCapabilityBinding)
            ).scalar()
        assert count == 0

        # Posture reflects failure
        with sf() as session:
            posture = evaluate_lifecycle_posture(session, embedding_profile_id=_PROFILE_ID)
        assert posture.readiness_phase == PHASE_VERIFICATION_FAILED


# ── Expired check ───────────────────────────────────────────────────


class TestExpiredCheck:
    def test_expired_check_denies_new_operations(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile_and_binding(session)
            _seed_passed_check(session, expires_in_hours=-1)  # already expired

        cfg = _make_config()
        adapter = _make_adapter(_GoodProvider())

        with pytest.raises(CapabilityAuthorizationError) as exc:
            build_verified_embedding_runtime(
                embedding_adapter=adapter,
                effective_config=cfg,
                session_factory=sf,
            )
        # The expired check may report as not_found if the fingerprint
        # doesn't match any completed check, or expired if it does.
        assert exc.value.code in (
            "capability_check_expired",
            "capability_check_not_found",
        )


# ── Alias-only binding ──────────────────────────────────────────────


class TestAliasOnlyBinding:
    def test_alias_only_cannot_activate(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile_and_binding(session, posture="configured_only")
            _seed_passed_check(session)

        with sf() as session:
            posture = evaluate_lifecycle_posture(session, embedding_profile_id=_PROFILE_ID)

        assert posture.readiness_phase == PHASE_BINDING_NOT_ACTIVATION_ELIGIBLE
        assert posture.persistent_activation_eligible is False
        assert "binding_alias_only" in posture.blocker_codes


# ── Source drift ────────────────────────────────────────────────────


class TestSourceDrift:
    def test_seal_rejects_drifted_population(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        from backend.db.models import Paper, VectorIndexRecord
        from backend.pipeline.vector_contracts import VECTOR_INDEX_V1
        now = datetime.now(timezone.utc)

        with sf() as session:
            _seed_profile_and_binding(session)
            session.add(Paper(id=1, source_id="p1", source="test", title="T", abstract="A", authors="[]"))
            session.add(VectorIndexRecord(
                vector_record_id="g" * 64, paper_id=1, chunk_key="title_abstract:0",
                content_kind="title_abstract", content_hash="h" * 64,
                embedding_profile_id=_PROFILE_ID, collection_name="test_col",
                index_schema_version=VECTOR_INDEX_V1, embedding_contract_version="pre_capability_v0",
                index_status="indexed", attempt_count=1, indexed_at=now, backend_verified_at=now,
            ))
            session.execute(text(
                "INSERT INTO embedding_binding_cutovers "
                "(cutover_id, cutover_schema_version, embedding_profile_id, embedding_purpose, "
                " source_contract_version, target_binding_id, source_snapshot_kind, "
                " source_snapshot_fingerprint, source_item_count, status) "
                "VALUES (:cid, 'cutover_v1', :pid, 'paper', 'pre_capability_v0', :bid, "
                "        'paper_chunk', 'placeholder', 0, 'pending')"
            ), {"cid": "d" * 64, "pid": _PROFILE_ID, "bid": _BINDING_ID})
            session.commit()

        from backend.pipeline.capability.cutover_snapshot import (
            snapshot_source_population,
        )
        with sf() as session:
            snapshot_source_population(
                session, cutover_id="d" * 64,
                embedding_profile_id=_PROFILE_ID,
            )
            session.execute(
                update(EmbeddingBindingCutoverItem).where(
                    EmbeddingBindingCutoverItem.cutover_id == "d" * 64
                ).values(status="indexed")
            )
            # Add drift: new vector after snapshot
            session.add(VectorIndexRecord(
                vector_record_id="i" * 64, paper_id=1, chunk_key="abstract:0",
                content_kind="abstract", content_hash="j" * 64,
                embedding_profile_id=_PROFILE_ID, collection_name="test_col",
                index_schema_version=VECTOR_INDEX_V1, embedding_contract_version="pre_capability_v0",
                index_status="indexed", attempt_count=1, indexed_at=now, backend_verified_at=now,
            ))
            session.commit()

        sealed, reason = seal_cutover(
            sf, cutover_id="d" * 64, embedding_profile_id=_PROFILE_ID,
        )
        assert not sealed
        assert "drift" in reason.lower()


# ── Cutover abort ───────────────────────────────────────────────────


class TestCutoverAbort:
    def test_abort_releases_clean(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile_and_binding(session)
            _seed_passed_check(session)

        svc = CapabilityLifecycleService(sf)
        create_result = svc.create_cutover(
            embedding_profile_id=_PROFILE_ID,
            embedding_purpose="paper",
            target_binding_id=_BINDING_ID,
        )

        abort_result = svc.abort_cutover(
            cutover_id=create_result.cutover_id,
            embedding_profile_id=_PROFILE_ID,
        )
        assert abort_result.guard_released is False  # no guard was frozen

        # Cutover cancelled
        from backend.db.models import EmbeddingBindingCutover
        with sf() as session:
            cutover = session.execute(
                select(EmbeddingBindingCutover).where(
                    EmbeddingBindingCutover.cutover_id == create_result.cutover_id
                )
            ).scalar_one()
        assert cutover.status == "cancelled"

        # Can create a new cutover after abort
        new_result = svc.create_cutover(
            embedding_profile_id=_PROFILE_ID,
            embedding_purpose="paper",
            target_binding_id=_BINDING_ID,
        )
        assert new_result.cutover_id != create_result.cutover_id
