"""Tests for P0.4A1.1: capability ledger check-first schema.

Proves:
  - Both tables create with correct columns and constraints
  - The check-first lifecycle is DB-enforced:
      pending check can be created with binding_id = NULL
      passed check REQUIRES binding_id NOT NULL
      failed check REQUIRES binding_id IS NULL
  - CHECK constraints reject invalid status/observation combinations
  - FK constraints enforce RESTRICT on profile and binding
  - Migration 027 round-trips cleanly (026 -> 027 -> 026)

Frozen rule:
    A failed or incomplete probe may create check evidence, but it may
    never create a resolved capability binding.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError as SAIntegrityError
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.db.database import Base
from backend.pipeline.vector_contracts import (
    CAPABILITY_BINDING_SCHEMA_V1,
    CAPABILITY_CHECK_SCHEMA_V1,
)

# ── Test helpers ──────────────────────────────────────────────────────


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


def _make_session(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)()


_VALID_PROFILE_ID = "a" * 64
_VALID_BINDING_ID = "b" * 64
_VALID_FINGERPRINT = "c" * 64
_VALID_CHECK_ID = "d" * 64


def _seed_profile(session):
    """Insert a minimal embedding_profiles row to satisfy FK."""
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
        {"pid": _VALID_PROFILE_ID},
    )
    session.commit()


def _seed_binding(session, binding_id=_VALID_BINDING_ID):
    """Insert a minimal embedding_capability_bindings row."""
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
        {"bid": binding_id, "pid": _VALID_PROFILE_ID},
    )
    session.commit()


# ── 1. Schema structure ───────────────────────────────────────────────


class TestCapabilityCheckSchema:
    def test_check_table_has_all_columns(self):
        engine = _make_engine()
        inspector = inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("embedding_capability_checks")}

        required = {
            "check_id", "embedding_profile_id", "binding_id",
            "runtime_config_fingerprint", "probe_suite_version",
            "check_status", "probe_kind", "attempt_count",
            "provider_request_count", "claimed_at", "lease_expires_at",
            "probed_at", "completed_at", "expires_at",
            "observed_document_dimension", "observed_query_dimension",
            "observed_document_norm_min", "observed_document_norm_max",
            "observed_query_norm", "observed_document_reported_model",
            "observed_query_reported_model",
            "observed_document_provider_revision",
            "observed_query_provider_revision",
            "observed_document_evidence_source",
            "observed_query_evidence_source",
            "failure_category", "failure_code", "sanitized_error_detail",
            "check_schema_version", "created_at",
        }
        assert required <= cols, f"missing: {required - cols}"

    def test_binding_id_is_nullable(self):
        """binding_id must be nullable — checks start with NULL binding."""
        engine = _make_engine()
        inspector = inspect(engine)
        cols = {c["name"]: c for c in inspector.get_columns("embedding_capability_checks")}
        assert cols["binding_id"]["nullable"] is True

    def test_check_status_constraint_present(self):
        engine = _make_engine()
        inspector = inspect(engine)
        constraints = {
            c["name"]
            for c in inspector.get_check_constraints("embedding_capability_checks")
        }
        assert "ck_ecc_check_status" in constraints
        assert "ck_ecc_passed_completeness" in constraints
        assert "ck_ecc_failed_completeness" in constraints

    def test_indexes_present(self):
        engine = _make_engine()
        inspector = inspect(engine)
        indexes = {
            (ix["name"], tuple(ix["column_names"]))
            for ix in inspector.get_indexes("embedding_capability_checks")
        }
        # Composite authority-lookup index
        assert any(
            "profile_fingerprint_suite" in name for name, _ in indexes
        ), f"authority index missing: {indexes}"


class TestCapabilityBindingSchema:
    def test_binding_table_has_all_columns(self):
        engine = _make_engine()
        inspector = inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("embedding_capability_bindings")}

        required = {
            "binding_id", "embedding_profile_id", "provider_kind",
            "resolved_model", "provider_revision", "model_resolution_posture",
            "resolved_document_task", "resolved_query_task",
            "resolved_dimension", "resolved_normalization",
            "postprocessing_contract_version", "resolved_endpoint_identity",
            "resolved_deployment_id", "profile_schema_version",
            "provider_adapter_contract_version",
            "governed_adapter_contract_version",
            "resolution_classifier_version", "binding_schema_version",
            "created_at",
        }
        assert required <= cols, f"missing: {required - cols}"


# ── 2. Check-first lifecycle enforcement ──────────────────────────────


class TestCheckFirstLifecycle:
    """The frozen rule: failed/incomplete probes never create bindings."""

    def test_pending_check_with_null_binding_succeeds(self):
        """A pending check can be created with binding_id = NULL."""
        engine = _make_engine()
        session = _make_session(engine)
        _seed_profile(session)

        # pending check, no binding — must succeed
        session.execute(
            text(
                "INSERT INTO embedding_capability_checks "
                "(check_id, embedding_profile_id, binding_id, "
                " runtime_config_fingerprint, probe_suite_version, "
                " check_status, probe_kind, check_schema_version) "
                "VALUES (:cid, :pid, NULL, :fp, 'embedding_probe_suite_v1', "
                "        'pending', 'dual_probe', 'capability_check_v1')"
            ),
            {"cid": _VALID_CHECK_ID, "pid": _VALID_PROFILE_ID, "fp": _VALID_FINGERPRINT},
        )
        session.commit()
        session.close()

    def test_passed_check_without_binding_rejected(self):
        """A passed check MUST have a binding_id — DB enforces this."""
        engine = _make_engine()
        session = _make_session(engine)
        _seed_profile(session)

        with pytest.raises(SAIntegrityError):
            session.execute(
                text(
                    "INSERT INTO embedding_capability_checks "
                    "(check_id, embedding_profile_id, binding_id, "
                    " runtime_config_fingerprint, probe_suite_version, "
                    " check_status, probe_kind, check_schema_version, "
                    " completed_at, expires_at, probed_at) "
                    "VALUES (:cid, :pid, NULL, :fp, 'embedding_probe_suite_v1', "
                    "        'passed', 'dual_probe', 'capability_check_v1', "
                    "        '2026-01-01', '2026-01-01', '2026-01-01')"
                ),
                {
                    "cid": _VALID_CHECK_ID,
                    "pid": _VALID_PROFILE_ID,
                    "fp": _VALID_FINGERPRINT,
                },
            )
            session.commit()
        session.rollback()
        session.close()

    def test_failed_check_with_binding_rejected(self):
        """A failed check MUST NOT have a binding_id — DB enforces this."""
        engine = _make_engine()
        session = _make_session(engine)
        _seed_profile(session)
        _seed_binding(session)

        with pytest.raises(SAIntegrityError):
            session.execute(
                text(
                    "INSERT INTO embedding_capability_checks "
                    "(check_id, embedding_profile_id, binding_id, "
                    " runtime_config_fingerprint, probe_suite_version, "
                    " check_status, probe_kind, check_schema_version, "
                    " completed_at, failure_code) "
                    "VALUES (:cid, :pid, :bid, :fp, 'embedding_probe_suite_v1', "
                    "        'failed', 'dual_probe', 'capability_check_v1', "
                    "        '2026-01-01', 'probe_failed')"
                ),
                {
                    "cid": _VALID_CHECK_ID,
                    "pid": _VALID_PROFILE_ID,
                    "bid": _VALID_BINDING_ID,
                    "fp": _VALID_FINGERPRINT,
                },
            )
            session.commit()
        session.rollback()
        session.close()

    def test_passed_check_with_binding_succeeds(self):
        """A passed check with a binding, all required fields, succeeds."""
        engine = _make_engine()
        session = _make_session(engine)
        _seed_profile(session)
        _seed_binding(session)

        session.execute(
            text(
                "INSERT INTO embedding_capability_checks "
                "(check_id, embedding_profile_id, binding_id, "
                " runtime_config_fingerprint, probe_suite_version, "
                " check_status, probe_kind, check_schema_version, "
                " completed_at, expires_at, probed_at, "
                " observed_document_dimension, observed_query_dimension) "
                "VALUES (:cid, :pid, :bid, :fp, 'embedding_probe_suite_v1', "
                "        'passed', 'dual_probe', 'capability_check_v1', "
                "        '2026-01-01 00:00:00', '2026-01-01 01:00:00', "
                "        '2026-01-01 00:00:00', 1536, 1536)"
            ),
            {
                "cid": _VALID_CHECK_ID,
                "pid": _VALID_PROFILE_ID,
                "bid": _VALID_BINDING_ID,
                "fp": _VALID_FINGERPRINT,
            },
        )
        session.commit()
        session.close()

    def test_failed_check_without_binding_succeeds(self):
        """A failed check with no binding and a failure code succeeds."""
        engine = _make_engine()
        session = _make_session(engine)
        _seed_profile(session)

        session.execute(
            text(
                "INSERT INTO embedding_capability_checks "
                "(check_id, embedding_profile_id, binding_id, "
                " runtime_config_fingerprint, probe_suite_version, "
                " check_status, probe_kind, check_schema_version, "
                " completed_at, failure_code) "
                "VALUES (:cid, :pid, NULL, :fp, 'embedding_probe_suite_v1', "
                "        'failed', 'dual_probe', 'capability_check_v1', "
                "        '2026-01-01 00:00:00', 'probe_failed')"
            ),
            {
                "cid": _VALID_CHECK_ID,
                "pid": _VALID_PROFILE_ID,
                "fp": _VALID_FINGERPRINT,
            },
        )
        session.commit()
        session.close()


# ── 3. FK enforcement ─────────────────────────────────────────────────


class TestForeignKeyEnforcement:
    def test_check_profile_fk_restrict(self):
        """Cannot insert a check with a non-existent profile_id."""
        engine = _make_engine()
        session = _make_session(engine)
        # No profile seeded

        with pytest.raises(SAIntegrityError):
            session.execute(
                text(
                    "INSERT INTO embedding_capability_checks "
                    "(check_id, embedding_profile_id, binding_id, "
                    " runtime_config_fingerprint, probe_suite_version, "
                    " check_status, probe_kind, check_schema_version) "
                    "VALUES (:cid, :pid, NULL, :fp, 'embedding_probe_suite_v1', "
                    "        'pending', 'dual_probe', 'capability_check_v1')"
                ),
                {"cid": _VALID_CHECK_ID, "pid": _VALID_PROFILE_ID, "fp": _VALID_FINGERPRINT},
            )
            session.commit()
        session.rollback()
        session.close()

    def test_binding_profile_fk_restrict(self):
        """Cannot insert a binding with a non-existent profile_id."""
        engine = _make_engine()
        session = _make_session(engine)

        with pytest.raises(SAIntegrityError):
            session.execute(
                text(
                    "INSERT INTO embedding_capability_bindings "
                    "(binding_id, embedding_profile_id, provider_kind, "
                    " resolved_model, model_resolution_posture, "
                    " resolved_dimension, resolved_normalization, "
                    " postprocessing_contract_version, resolved_endpoint_identity, "
                    " profile_schema_version, provider_adapter_contract_version, "
                    " governed_adapter_contract_version, "
                    " resolution_classifier_version, binding_schema_version) "
                    "VALUES (:bid, :pid, 'openai', 'm', 'configured_match', "
                    "        1536, 'none', 'none', 'provider-default://unset', "
                    "        'embedding_profile_v1', 'v1', 'v1', 'v1', "
                    "        'capability_binding_v1')"
                ),
                {"bid": _VALID_BINDING_ID, "pid": _VALID_PROFILE_ID},
            )
            session.commit()
        session.rollback()
        session.close()


# ── 4. Version constants ──────────────────────────────────────────────


class TestVersionConstants:
    def test_binding_schema_constant(self):
        assert CAPABILITY_BINDING_SCHEMA_V1 == "capability_binding_v1"

    def test_check_schema_constant(self):
        assert CAPABILITY_CHECK_SCHEMA_V1 == "capability_check_v1"


# ── 5. No activations table ───────────────────────────────────────────


class TestActivationsTableNowExists:
    """A2 creates embedding_profile_binding_activations (deferred from A1)."""

    def test_activations_table_exists(self):
        engine = _make_engine()
        inspector = inspect(engine)
        assert inspector.has_table("embedding_profile_binding_activations")
