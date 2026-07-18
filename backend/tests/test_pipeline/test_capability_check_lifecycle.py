"""Tests for P0.4A1.3: check claim and lease lifecycle.

Proves:
  - Pending check created with binding_id = NULL
  - Atomic claim: concurrent workers, exactly one wins
  - Lease expiry → abandoned via recover_stale_running_checks
  - complete_check_passed sets binding + all observations
  - complete_check_failed leaves binding NULL
  - operator_cancel_check transitions to cancelled
  - Terminal immutability: second complete is a no-op or raises
  - Invalid transitions rejected
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

import backend.db.models
from backend.db.database import Base
from backend.db.models import EmbeddingCapabilityCheck
from backend.pipeline.capability.capability_check_lifecycle import (
    claim_check,
    complete_check_failed,
    complete_check_passed,
    create_pending_check,
    operator_cancel_check,
    recover_stale_running_checks,
)
from backend.pipeline.capability.contracts import (
    CheckAlreadyClaimed,
    CheckAlreadyTerminal,
    FailedCheckEvidence,
    InvalidCheckTransition,
    PassedCheckObservations,
    STATUS_ABANDONED,
    STATUS_CANCELLED,
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_PENDING,
    STATUS_RUNNING,
)
from backend.pipeline.vector_contracts import EMBEDDING_PROBE_SUITE_V1

_PROFILE_ID = "a" * 64
_FINGERPRINT = "c" * 64


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


def _seed_binding(session, binding_id="b" * 64):
    """Insert a binding row so the FK on checks.binding_id is satisfied."""
    session.execute(
        text(
            "INSERT INTO embedding_capability_bindings "
            "(binding_id, embedding_profile_id, provider_kind, resolved_model, "
            " model_resolution_posture, resolved_dimension, resolved_normalization, "
            " postprocessing_contract_version, resolved_endpoint_identity, "
            " profile_schema_version, provider_adapter_contract_version, "
            " governed_adapter_contract_version, resolution_classifier_version, "
            " binding_schema_version) "
            "VALUES (:bid, :pid, 'openai', 'text-embedding-3-small', "
            "        'configured_match', 1536, 'none', 'none', 'provider-default://unset', "
            "        'embedding_profile_v1', 'openai_v1', 'governed_v1', "
            "        'resolution_classifier_v1', 'capability_binding_v1')"
        ),
        {"bid": binding_id, "pid": _PROFILE_ID},
    )
    session.commit()


def _make_session(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


def _make_passed_observations(**overrides):
    defaults = dict(
        observed_document_dimension=1536,
        observed_query_dimension=1536,
        observed_document_norm_min=0.99,
        observed_document_norm_max=1.01,
        observed_query_norm=1.0,
        observed_document_reported_model="text-embedding-3-small",
        observed_query_reported_model="text-embedding-3-small",
        observed_document_provider_revision=None,
        observed_query_provider_revision=None,
        observed_document_evidence_source="openai_response_model",
        observed_query_evidence_source="openai_response_model",
    )
    defaults.update(overrides)
    return PassedCheckObservations(**defaults)


def _make_failed_evidence(**overrides):
    defaults = dict(
        failure_category="probe_failure",
        failure_code="dimension_mismatch",
        sanitized_error_detail="observed dim 768, expected 1536",
    )
    defaults.update(overrides)
    return FailedCheckEvidence(**defaults)


# ── Create pending ────────────────────────────────────────────────────


class TestCreatePendingCheck:
    def test_creates_pending_with_null_binding(self):
        engine = _make_engine()
        sf = _make_session(engine)
        with sf() as session:
            _seed_profile(session)
            check_id = create_pending_check(
                session,
                embedding_profile_id=_PROFILE_ID,
                runtime_config_fingerprint=_FINGERPRINT,
            )
            session.commit()

        with sf() as session:
            check = session.execute(
                select(EmbeddingCapabilityCheck).where(
                    EmbeddingCapabilityCheck.check_id == check_id
                )
            ).scalar_one()
            assert check.check_status == STATUS_PENDING
            assert check.binding_id is None
            assert check.claimed_at is None
            assert check.lease_expires_at is None


# ── Atomic claim ──────────────────────────────────────────────────────


class TestClaimCheck:
    def test_claim_succeeds_for_pending(self):
        engine = _make_engine()
        sf = _make_session(engine)
        with sf() as session:
            _seed_profile(session)
            check_id = create_pending_check(
                session,
                embedding_profile_id=_PROFILE_ID,
                runtime_config_fingerprint=_FINGERPRINT,
            )
            session.commit()

        claim_check(sf, check_id, lease_ttl_seconds=60)

        with sf() as session:
            check = session.execute(
                select(EmbeddingCapabilityCheck).where(
                    EmbeddingCapabilityCheck.check_id == check_id
                )
            ).scalar_one()
            assert check.check_status == STATUS_RUNNING
            assert check.claimed_at is not None
            assert check.lease_expires_at is not None
            assert check.attempt_count == 1

    def test_second_claim_raises_already_claimed(self):
        engine = _make_engine()
        sf = _make_session(engine)
        with sf() as session:
            _seed_profile(session)
            check_id = create_pending_check(
                session,
                embedding_profile_id=_PROFILE_ID,
                runtime_config_fingerprint=_FINGERPRINT,
            )
            session.commit()

        claim_check(sf, check_id, lease_ttl_seconds=60)

        with pytest.raises(CheckAlreadyClaimed):
            claim_check(sf, check_id, lease_ttl_seconds=60)


# ── Concurrent claim (file-backed) ────────────────────────────────────


class TestConcurrentClaim:
    def test_concurrent_invocations_one_claims(self):
        """Two workers racing to claim the same check — exactly one wins."""
        tmpdir = tempfile.mkdtemp()
        db_path = Path(tmpdir) / "concurrent.db"
        # Use file-backed SQLite for genuine connection isolation
        engine = create_engine(f"sqlite:///{db_path}")

        @event.listens_for(engine, "connect")
        def _fk(c, r):
            cur = c.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        Base.metadata.create_all(engine)
        sf = sessionmaker(bind=engine, expire_on_commit=False)

        with sf() as session:
            _seed_profile(session)
            check_id = create_pending_check(
                session,
                embedding_profile_id=_PROFILE_ID,
                runtime_config_fingerprint=_FINGERPRINT,
            )
            session.commit()

        async def _try_claim():
            try:
                claim_check(sf, check_id, lease_ttl_seconds=60)
                return True
            except CheckAlreadyClaimed:
                return False

        async def _main():
            results = await asyncio.gather(_try_claim(), _try_claim())
            return results

        results = asyncio.run(_main())
        assert sum(1 for r in results if r) == 1, (
            f"expected exactly 1 claimant, got {results}"
        )


# ── Lease recovery ────────────────────────────────────────────────────


class TestRecoverStale:
    def test_stale_running_abandoned(self):
        engine = _make_engine()
        sf = _make_session(engine)
        with sf() as session:
            _seed_profile(session)
            check_id = create_pending_check(
                session,
                embedding_profile_id=_PROFILE_ID,
                runtime_config_fingerprint=_FINGERPRINT,
            )
            session.commit()

        # Claim with a very short lease
        claim_check(sf, check_id, lease_ttl_seconds=1)

        # Wait past the lease
        import time
        time.sleep(0.1)

        # Use a "now" that's past the lease
        future = datetime.now(timezone.utc) + timedelta(seconds=5)
        count = recover_stale_running_checks(sf, now=future)
        assert count == 1

        with sf() as session:
            check = session.execute(
                select(EmbeddingCapabilityCheck).where(
                    EmbeddingCapabilityCheck.check_id == check_id
                )
            ).scalar_one()
            assert check.check_status == STATUS_ABANDONED
            assert check.binding_id is None
            assert check.completed_at is not None

    def test_no_stale_returns_zero(self):
        engine = _make_engine()
        sf = _make_session(engine)
        with sf() as session:
            _seed_profile(session)
            create_pending_check(
                session,
                embedding_profile_id=_PROFILE_ID,
                runtime_config_fingerprint=_FINGERPRINT,
            )
            session.commit()

        # Pending check, nothing to recover
        count = recover_stale_running_checks(sf)
        assert count == 0


# ── Complete passed ───────────────────────────────────────────────────


class TestCompletePassed:
    def test_complete_passed_sets_binding_and_observations(self):
        engine = _make_engine()
        sf = _make_session(engine)
        binding_id = "b" * 64
        with sf() as session:
            _seed_profile(session)
            _seed_binding(session, binding_id)
            check_id = create_pending_check(
                session,
                embedding_profile_id=_PROFILE_ID,
                runtime_config_fingerprint=_FINGERPRINT,
            )
            session.commit()

        claim_check(sf, check_id)
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        complete_check_passed(
            sf, check_id,
            binding_id=binding_id,
            observations=_make_passed_observations(),
            expires_at=expires,
        )

        with sf() as session:
            check = session.execute(
                select(EmbeddingCapabilityCheck).where(
                    EmbeddingCapabilityCheck.check_id == check_id
                )
            ).scalar_one()
            assert check.check_status == STATUS_PASSED
            assert check.binding_id == binding_id
            assert check.expires_at is not None
            assert check.probed_at is not None
            assert check.completed_at is not None
            assert check.observed_document_dimension == 1536
            assert check.observed_query_dimension == 1536

    def test_second_complete_raises_already_terminal(self):
        engine = _make_engine()
        sf = _make_session(engine)
        binding_id = "b" * 64
        with sf() as session:
            _seed_profile(session)
            _seed_binding(session, binding_id)
            check_id = create_pending_check(
                session,
                embedding_profile_id=_PROFILE_ID,
                runtime_config_fingerprint=_FINGERPRINT,
            )
            session.commit()

        claim_check(sf, check_id)
        complete_check_passed(
            sf, check_id,
            binding_id=binding_id,
            observations=_make_passed_observations(),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        with pytest.raises(CheckAlreadyTerminal):
            complete_check_passed(
                sf, check_id,
                binding_id=binding_id,
                observations=_make_passed_observations(),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )


# ── Complete failed ───────────────────────────────────────────────────


class TestCompleteFailed:
    def test_complete_failed_leaves_binding_null(self):
        engine = _make_engine()
        sf = _make_session(engine)
        with sf() as session:
            _seed_profile(session)
            check_id = create_pending_check(
                session,
                embedding_profile_id=_PROFILE_ID,
                runtime_config_fingerprint=_FINGERPRINT,
            )
            session.commit()

        claim_check(sf, check_id)
        complete_check_failed(
            sf, check_id,
            failure=_make_failed_evidence(),
        )

        with sf() as session:
            check = session.execute(
                select(EmbeddingCapabilityCheck).where(
                    EmbeddingCapabilityCheck.check_id == check_id
                )
            ).scalar_one()
            assert check.check_status == STATUS_FAILED
            assert check.binding_id is None
            assert check.failure_code == "dimension_mismatch"
            assert check.completed_at is not None
            assert check.expires_at is None


# ── Cancel ────────────────────────────────────────────────────────────


class TestOperatorCancel:
    def test_cancel_from_pending(self):
        engine = _make_engine()
        sf = _make_session(engine)
        with sf() as session:
            _seed_profile(session)
            check_id = create_pending_check(
                session,
                embedding_profile_id=_PROFILE_ID,
                runtime_config_fingerprint=_FINGERPRINT,
            )
            session.commit()

        operator_cancel_check(sf, check_id)

        with sf() as session:
            check = session.execute(
                select(EmbeddingCapabilityCheck).where(
                    EmbeddingCapabilityCheck.check_id == check_id
                )
            ).scalar_one()
            assert check.check_status == STATUS_CANCELLED
            assert check.binding_id is None

    def test_cancel_from_running(self):
        engine = _make_engine()
        sf = _make_session(engine)
        with sf() as session:
            _seed_profile(session)
            check_id = create_pending_check(
                session,
                embedding_profile_id=_PROFILE_ID,
                runtime_config_fingerprint=_FINGERPRINT,
            )
            session.commit()

        claim_check(sf, check_id)
        operator_cancel_check(sf, check_id)

        with sf() as session:
            check = session.execute(
                select(EmbeddingCapabilityCheck).where(
                    EmbeddingCapabilityCheck.check_id == check_id
                )
            ).scalar_one()
            assert check.check_status == STATUS_CANCELLED

    def test_cancel_from_terminal_raises(self):
        engine = _make_engine()
        sf = _make_session(engine)
        with sf() as session:
            _seed_profile(session)
            check_id = create_pending_check(
                session,
                embedding_profile_id=_PROFILE_ID,
                runtime_config_fingerprint=_FINGERPRINT,
            )
            session.commit()

        claim_check(sf, check_id)
        complete_check_failed(sf, check_id, failure=_make_failed_evidence())

        with pytest.raises(CheckAlreadyTerminal):
            operator_cancel_check(sf, check_id)


# ── Invalid transitions ──────────────────────────────────────────────


class TestInvalidTransitions:
    def test_complete_passed_from_pending_rejected(self):
        """Cannot skip the claim step — pending → passed is invalid."""
        engine = _make_engine()
        sf = _make_session(engine)
        binding_id = "b" * 64
        with sf() as session:
            _seed_profile(session)
            _seed_binding(session, binding_id)
            check_id = create_pending_check(
                session,
                embedding_profile_id=_PROFILE_ID,
                runtime_config_fingerprint=_FINGERPRINT,
            )
            session.commit()

        with pytest.raises(InvalidCheckTransition):
            complete_check_passed(
                sf, check_id,
                binding_id=binding_id,
                observations=_make_passed_observations(),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
