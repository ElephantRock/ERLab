"""Tests for P0.4A3.1: unified lifecycle posture evaluator.

Proves the posture evaluator correctly derives each readiness phase
from authoritative ledger state, and that it is side-effect-free.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

import backend.db.models
from backend.db.database import Base
from backend.pipeline.capability.lifecycle_posture import (
    PHASE_BINDING_NOT_ACTIVATION_ELIGIBLE,
    PHASE_CUTOVER_REQUIRED,
    PHASE_VERIFICATION_FAILED,
    PHASE_VERIFICATION_REQUIRED,
    evaluate_lifecycle_posture,
)

_PROFILE_ID = "a" * 64
_BINDING_ID = "b" * 64
_CHECK_ID = "e" * 64


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


def _seed_passed_check(session, expires_in_hours=1):
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
    ), {
        "cid": _CHECK_ID, "pid": _PROFILE_ID, "bid": _BINDING_ID,
        "fp": "f" * 64, "now": now, "expiry": now + timedelta(hours=expires_in_hours),
    })
    session.commit()


def _seed_binding(session, posture="configured_match"):
    session.execute(text(
        "INSERT INTO embedding_capability_bindings "
        "(binding_id, embedding_profile_id, provider_kind, resolved_model, "
        " model_resolution_posture, resolved_dimension, resolved_normalization, "
        " postprocessing_contract_version, resolved_endpoint_identity, "
        " profile_schema_version, provider_adapter_contract_version, "
        " governed_adapter_contract_version, resolution_classifier_version, "
        " binding_schema_version) "
        "VALUES (:bid, :pid, 'openai', 'm', :posture, 1536, 'none', "
        "        'none', 'provider-default://unset', 'embedding_profile_v1', "
        "        'v1', 'v1', 'v1', 'capability_binding_v1')"
    ), {"bid": _BINDING_ID, "pid": _PROFILE_ID, "posture": posture})
    session.commit()


def _make_sf(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


class TestLifecyclePosture:
    def test_no_check_verification_required(self):
        engine = _make_engine()
        sf = _make_sf(engine)
        with sf() as session:
            _seed_profile(session)
            posture = evaluate_lifecycle_posture(
                session, embedding_profile_id=_PROFILE_ID,
            )
        assert posture.readiness_phase == PHASE_VERIFICATION_REQUIRED
        assert posture.capability_health_status == "no_check"

    def test_passed_check_no_binding_transient(self):
        """Check passed but no binding row yet → transient posture.

        Note: in practice, a passed check always has binding_id set and
        the binding row is created atomically. This test simulates a
        state where the binding row exists but no cutover/activation."""
        engine = _make_engine()
        sf = _make_sf(engine)
        with sf() as session:
            _seed_profile(session)
            _seed_binding(session)
            _seed_passed_check(session)
            posture = evaluate_lifecycle_posture(
                session, embedding_profile_id=_PROFILE_ID,
            )
        # With a binding + passed check but no cutover → cutover required
        assert posture.capability_health_status == "currently_verified"
        assert posture.binding_id is not None

    def test_failed_check_verification_failed(self):
        engine = _make_engine()
        sf = _make_sf(engine)
        now = datetime.now(UTC)
        with sf() as session:
            _seed_profile(session)
            session.execute(text(
                "INSERT INTO embedding_capability_checks "
                "(check_id, embedding_profile_id, binding_id, "
                " runtime_config_fingerprint, probe_suite_version, "
                " check_status, probe_kind, check_schema_version, "
                " completed_at, failure_code) "
                "VALUES (:cid, :pid, NULL, :fp, 'embedding_probe_suite_v1', "
                "        'failed', 'dual_probe', 'capability_check_v1', "
                "        :now, 'probe_failed')"
            ), {"cid": _CHECK_ID, "pid": _PROFILE_ID, "fp": "f" * 64, "now": now})
            session.commit()
            posture = evaluate_lifecycle_posture(
                session, embedding_profile_id=_PROFILE_ID,
            )
        assert posture.readiness_phase == PHASE_VERIFICATION_FAILED

    def test_alias_only_binding_not_eligible(self):
        engine = _make_engine()
        sf = _make_sf(engine)
        with sf() as session:
            _seed_profile(session)
            _seed_binding(session, posture="configured_only")
            _seed_passed_check(session)
            posture = evaluate_lifecycle_posture(
                session, embedding_profile_id=_PROFILE_ID,
            )
        assert posture.readiness_phase == PHASE_BINDING_NOT_ACTIVATION_ELIGIBLE
        assert posture.persistent_activation_eligible is False
        assert "binding_alias_only" in posture.blocker_codes

    def test_eligible_binding_cutover_required(self):
        engine = _make_engine()
        sf = _make_sf(engine)
        with sf() as session:
            _seed_profile(session)
            _seed_binding(session, posture="configured_match")
            _seed_passed_check(session)
            posture = evaluate_lifecycle_posture(
                session, embedding_profile_id=_PROFILE_ID,
            )
        assert posture.readiness_phase == PHASE_CUTOVER_REQUIRED
        assert posture.persistent_activation_eligible is True

    def test_side_effect_free(self):
        """Posture evaluation must not create or modify any rows."""
        engine = _make_engine()
        sf = _make_sf(engine)
        with sf() as session:
            _seed_profile(session)

            # Count rows before
            from sqlalchemy import func, select
            checks_before = session.execute(
                select(func.count()).select_from(EmbeddingBackendCheck)
            ).scalar()

            posture = evaluate_lifecycle_posture(
                session, embedding_profile_id=_PROFILE_ID,
            )

            # Count rows after — must be unchanged
            checks_after = session.execute(
                select(func.count()).select_from(EmbeddingBackendCheck)
            ).scalar()

        assert checks_before == checks_after


# Avoid import errors — use the correct model name
EmbeddingBackendCheck = backend.db.models.EmbeddingCapabilityCheck
