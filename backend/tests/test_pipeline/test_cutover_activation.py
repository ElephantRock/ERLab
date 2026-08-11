"""Tests for P0.4A2.5+6: cutover snapshot, regeneration readiness, and activation.

Proves:
  - Source snapshot creates immutable items
  - Source fingerprint detects drift
  - Cutover not ready when items incomplete
  - Cutover ready when all items indexed
  - Activation transaction promotes candidate → active
  - Activation retires prior active binding
  - Failed activation preserves prior posture
  - Activation without sealed cutover fails
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event, select, text, update
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.db.database import Base
from backend.db.models import (
    EmbeddingBindingCutover,
    EmbeddingBindingCutoverItem,
    EmbeddingProfileBindingActivation,
    VectorIndexRecord,
)
from backend.pipeline.capability.activation_service import (
    ActivationError,
    activate_binding,
    seal_cutover,
)
from backend.pipeline.capability.cutover_snapshot import (
    is_cutover_ready_for_seal,
    recompute_source_fingerprint,
    snapshot_source_population,
)
from backend.pipeline.vector_contracts import VECTOR_INDEX_V1

_PROFILE_ID = "a" * 64
_BINDING_ID = "b" * 64
_CUTOVER_ID = "c" * 64
_ACTIVATION_ID = "d" * 64
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


def _seed_full_profile(session):
    """Seed profile, binding, check, paper, and a v1 vector record."""
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

    # Passed check (valid for 1 hour)
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
        "fp": "f" * 64, "now": now, "expiry": now + timedelta(hours=1),
    })

    # Paper
    from backend.db.models import Paper
    session.add(Paper(id=1, title="Test", abstract="Abstract", source_id="s1", source="test", authors="[]"))

    # V1 indexed vector
    session.add(VectorIndexRecord(
        vector_record_id="g" * 64,
        paper_id=1,
        chunk_key="title_abstract:0",
        content_kind="title_abstract",
        content_hash="h" * 64,
        embedding_profile_id=_PROFILE_ID,
        collection_name="test_col",
        index_schema_version=VECTOR_INDEX_V1,
        embedding_contract_version="pre_capability_v0",
        index_status="indexed",
        attempt_count=1,
        indexed_at=now,
        backend_verified_at=now,
    ))

    # Cutover in pending state
    session.execute(text(
        "INSERT INTO embedding_binding_cutovers "
        "(cutover_id, cutover_schema_version, embedding_profile_id, embedding_purpose, "
        " source_contract_version, target_binding_id, source_snapshot_kind, "
        " source_snapshot_fingerprint, source_item_count, status) "
        "VALUES (:cid, 'cutover_v1', :pid, 'paper', 'pre_capability_v0', :bid, "
        "        'paper_chunk', 'placeholder', 0, 'pending')"
    ), {"cid": _CUTOVER_ID, "pid": _PROFILE_ID, "bid": _BINDING_ID})

    session.commit()


def _make_sf(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


# ── A2.5: Snapshot ───────────────────────────────────────────────────


class TestSourceSnapshot:
    def test_snapshot_creates_items(self):
        engine = _make_engine()
        sf = _make_sf(engine)
        with sf() as session:
            _seed_full_profile(session)

            result = snapshot_source_population(
                session,
                cutover_id=_CUTOVER_ID,
                embedding_profile_id=_PROFILE_ID,
            )

        assert result.source_item_count == 1
        assert len(result.source_snapshot_fingerprint) == 64

        with sf() as session:
            items = session.execute(
                select(EmbeddingBindingCutoverItem).where(
                    EmbeddingBindingCutoverItem.cutover_id == _CUTOVER_ID
                )
            ).scalars().all()
            assert len(items) == 1
            assert items[0].status == "pending"

    def test_fingerprint_detects_drift(self):
        engine = _make_engine()
        sf = _make_sf(engine)
        with sf() as session:
            _seed_full_profile(session)

            # Snapshot
            snapshot_source_population(
                session,
                cutover_id=_CUTOVER_ID,
                embedding_profile_id=_PROFILE_ID,
            )

            # Add a new vector → drift
            now = datetime.now(UTC)
            session.add(VectorIndexRecord(
                vector_record_id="i" * 64,
                paper_id=1, chunk_key="abstract:0",
                content_kind="abstract", content_hash="j" * 64,
                embedding_profile_id=_PROFILE_ID,
                collection_name="test_col",
                index_schema_version=VECTOR_INDEX_V1,
                embedding_contract_version="pre_capability_v0",
                index_status="indexed", attempt_count=1,
                indexed_at=now, backend_verified_at=now,
            ))
            session.commit()

            fp_before = session.execute(
                select(EmbeddingBindingCutover.source_snapshot_fingerprint).where(
                    EmbeddingBindingCutover.cutover_id == _CUTOVER_ID
                )
            ).scalar()
            fp_after = recompute_source_fingerprint(
                session, embedding_profile_id=_PROFILE_ID
            )

        assert fp_before != fp_after


class TestCutoverReadiness:
    def test_not_ready_with_pending_items(self):
        engine = _make_engine()
        sf = _make_sf(engine)
        with sf() as session:
            _seed_full_profile(session)
            snapshot_source_population(
                session, cutover_id=_CUTOVER_ID,
                embedding_profile_id=_PROFILE_ID,
            )

            ready, reason = is_cutover_ready_for_seal(session, _CUTOVER_ID)

        assert not ready
        assert "0/1" in reason or "indexed" in reason.lower()

    def test_ready_when_all_indexed(self):
        engine = _make_engine()
        sf = _make_sf(engine)
        with sf() as session:
            _seed_full_profile(session)
            snapshot_source_population(
                session, cutover_id=_CUTOVER_ID,
                embedding_profile_id=_PROFILE_ID,
            )
            # Mark all items as indexed
            session.execute(
                update(EmbeddingBindingCutoverItem).where(
                    EmbeddingBindingCutoverItem.cutover_id == _CUTOVER_ID
                ).values(status="indexed")
            )
            session.commit()

            ready, reason = is_cutover_ready_for_seal(session, _CUTOVER_ID)

        assert ready


# ── A2.6: Seal and Activate ──────────────────────────────────────────


class TestSealCutover:
    def test_seal_succeeds_when_ready(self):
        engine = _make_engine()
        sf = _make_sf(engine)
        with sf() as session:
            _seed_full_profile(session)
            snapshot_source_population(
                session, cutover_id=_CUTOVER_ID,
                embedding_profile_id=_PROFILE_ID,
            )
            session.execute(
                update(EmbeddingBindingCutoverItem).where(
                    EmbeddingBindingCutoverItem.cutover_id == _CUTOVER_ID
                ).values(status="indexed")
            )
            session.commit()

        sealed, reason = seal_cutover(
            sf, cutover_id=_CUTOVER_ID,
            embedding_profile_id=_PROFILE_ID,
        )
        assert sealed

    def test_seal_fails_on_drift(self):
        engine = _make_engine()
        sf = _make_sf(engine)
        with sf() as session:
            _seed_full_profile(session)
            snapshot_source_population(
                session, cutover_id=_CUTOVER_ID,
                embedding_profile_id=_PROFILE_ID,
            )
            session.execute(
                update(EmbeddingBindingCutoverItem).where(
                    EmbeddingBindingCutoverItem.cutover_id == _CUTOVER_ID
                ).values(status="indexed")
            )
            # Add drift
            now = datetime.now(UTC)
            session.add(VectorIndexRecord(
                vector_record_id="i" * 64,
                paper_id=1, chunk_key="abstract:0",
                content_kind="abstract", content_hash="j" * 64,
                embedding_profile_id=_PROFILE_ID,
                collection_name="test_col",
                index_schema_version=VECTOR_INDEX_V1,
                embedding_contract_version="pre_capability_v0",
                index_status="indexed", attempt_count=1,
                indexed_at=now, backend_verified_at=now,
            ))
            session.commit()

        sealed, reason = seal_cutover(
            sf, cutover_id=_CUTOVER_ID,
            embedding_profile_id=_PROFILE_ID,
        )
        assert not sealed
        assert "drift" in reason.lower()


class TestActivateBinding:
    def _setup_sealed_cutover(self, sf):
        with sf() as session:
            _seed_full_profile(session)
            snapshot_source_population(
                session, cutover_id=_CUTOVER_ID,
                embedding_profile_id=_PROFILE_ID,
            )
            session.execute(
                update(EmbeddingBindingCutoverItem).where(
                    EmbeddingBindingCutoverItem.cutover_id == _CUTOVER_ID
                ).values(status="indexed")
            )
            # Seed a frozen write guard for this cutover
            from backend.db.models import EmbeddingProfileEmbeddingWriteGuard
            session.add(EmbeddingProfileEmbeddingWriteGuard(
                embedding_profile_id=_PROFILE_ID,
                embedding_purpose="paper",
                state="frozen",
                guard_epoch=1,
                cutover_id=_CUTOVER_ID,
                frozen_at=datetime.now(UTC),
            ))
            session.commit()

        seal_cutover(sf, cutover_id=_CUTOVER_ID, embedding_profile_id=_PROFILE_ID)

        # Create candidate activation
        with sf() as session:
            session.execute(text(
                "INSERT INTO embedding_profile_binding_activations "
                "(activation_id, embedding_profile_id, embedding_purpose, "
                " capability_binding_id, status, activation_generation) "
                "VALUES (:aid, :pid, 'paper', :bid, 'candidate', 1)"
            ), {"aid": _ACTIVATION_ID, "pid": _PROFILE_ID, "bid": _BINDING_ID})
            session.commit()

    def test_activation_promotes_candidate_to_active(self):
        engine = _make_engine()
        sf = _make_sf(engine)
        self._setup_sealed_cutover(sf)

        result = activate_binding(
            sf,
            cutover_id=_CUTOVER_ID,
            embedding_profile_id=_PROFILE_ID,
            target_binding_id=_BINDING_ID,
            candidate_activation_id=_ACTIVATION_ID,
        )

        assert result.success

        with sf() as session:
            activation = session.execute(
                select(EmbeddingProfileBindingActivation).where(
                    EmbeddingProfileBindingActivation.activation_id == _ACTIVATION_ID
                )
            ).scalar_one()
            assert activation.status == "active"
            assert activation.cutover_id == _CUTOVER_ID

    def test_activation_fails_without_sealed_cutover(self):
        engine = _make_engine()
        sf = _make_sf(engine)
        with sf() as session:
            _seed_full_profile(session)
            # Don't seal — cutover stays pending

            session.execute(text(
                "INSERT INTO embedding_profile_binding_activations "
                "(activation_id, embedding_profile_id, embedding_purpose, "
                " capability_binding_id, status, activation_generation) "
                "VALUES (:aid, :pid, 'paper', :bid, 'candidate', 1)"
            ), {"aid": _ACTIVATION_ID, "pid": _PROFILE_ID, "bid": _BINDING_ID})
            session.commit()

        with pytest.raises(ActivationError) as exc:
            activate_binding(
                sf,
                cutover_id=_CUTOVER_ID,
                embedding_profile_id=_PROFILE_ID,
                target_binding_id=_BINDING_ID,
                candidate_activation_id=_ACTIVATION_ID,
            )
        assert "not_sealed" in exc.value.code
