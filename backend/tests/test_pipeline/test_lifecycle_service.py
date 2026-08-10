"""Tests for P0.4A3.2: capability lifecycle orchestration service.

Proves the service coordinates existing A1/A2 services without
duplicating invariants, and that it is the sole mutation path for
lifecycle tables.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.db.database import Base
from backend.db.models import (
    EmbeddingBindingCutover,
    EmbeddingProfileBindingActivation,
)
from backend.pipeline.capability.lifecycle_service import (
    CapabilityLifecycleService,
    LifecycleError,
)

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


def _seed_profile_and_binding(session):
    session.execute(text(
        "INSERT INTO embedding_profiles "
        "(profile_id, profile_schema_version, provider, model_identifier, "
        " dimension, normalization_policy, chunking_schema_version, "
        " collection_name, verification_status, created_at) "
        "VALUES (:pid, 'embedding_profile_v1', 'openai', 'm', 1536, 'none', "
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
        "VALUES (:bid, :pid, 'openai', 'm', 'configured_match', 1536, 'none', "
        "        'none', 'provider-default://unset', 'embedding_profile_v1', "
        "        'v1', 'v1', 'v1', 'capability_binding_v1')"
    ), {"bid": _BINDING_ID, "pid": _PROFILE_ID})
    # Seed a passed check so posture is valid
    now = datetime.now(UTC)
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
        "fp": "f" * 64, "now": now, "expiry": now + timedelta(hours=1)})
    session.commit()


class TestCreateCutover:
    def test_creates_new_cutover(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile_and_binding(session)

        svc = CapabilityLifecycleService(sf)
        result = svc.create_cutover(
            embedding_profile_id=_PROFILE_ID,
            embedding_purpose="paper",
            target_binding_id=_BINDING_ID,
        )
        assert result.created is True
        assert len(result.cutover_id) == 32  # uuid hex

    def test_idempotent_returns_existing(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile_and_binding(session)

        svc = CapabilityLifecycleService(sf)
        r1 = svc.create_cutover(
            embedding_profile_id=_PROFILE_ID,
            embedding_purpose="paper",
            target_binding_id=_BINDING_ID,
        )
        r2 = svc.create_cutover(
            embedding_profile_id=_PROFILE_ID,
            embedding_purpose="paper",
            target_binding_id=_BINDING_ID,
        )
        assert r1.cutover_id == r2.cutover_id
        assert r2.created is False


class TestAbortCutover:
    def test_abort_rejects_candidate(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile_and_binding(session)

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

        with sf() as session:
            cutover = session.execute(
                select(EmbeddingBindingCutover).where(
                    EmbeddingBindingCutover.cutover_id == create_result.cutover_id
                )
            ).scalar_one()
            assert cutover.status == "cancelled"

            activation = session.execute(
                select(EmbeddingProfileBindingActivation).where(
                    EmbeddingProfileBindingActivation.activation_id == create_result.activation_id
                )
            ).scalar_one()
            assert activation.status == "rejected"

    def test_abort_active_raises(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile_and_binding(session)

        svc = CapabilityLifecycleService(sf)
        create_result = svc.create_cutover(
            embedding_profile_id=_PROFILE_ID,
            embedding_purpose="paper",
            target_binding_id=_BINDING_ID,
        )

        # Manually mark cutover as active
        with sf() as session:
            session.execute(text(
                "UPDATE embedding_binding_cutovers SET status = 'active' "
                "WHERE cutover_id = :cid"
            ), {"cid": create_result.cutover_id})
            session.commit()

        with pytest.raises(LifecycleError, match="already_active"):
            svc.abort_cutover(
                cutover_id=create_result.cutover_id,
                embedding_profile_id=_PROFILE_ID,
            )


class TestInspect:
    def test_inspect_returns_posture(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile_and_binding(session)

        svc = CapabilityLifecycleService(sf)
        posture = svc.inspect(embedding_profile_id=_PROFILE_ID)
        assert posture.embedding_profile_id == _PROFILE_ID
        assert posture.capability_health_status == "currently_verified"
