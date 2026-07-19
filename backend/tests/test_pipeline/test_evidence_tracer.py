"""Tests for P0.4A3.7: evidence tracing service."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

import backend.db.models
from backend.db.database import Base
from backend.pipeline.capability.evidence_tracer import (
    EvidenceTrace,
    trace_retrieval_evidence,
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


def _seed_minimal(session):
    """Seed a pipeline run + retrieval event (pre-capability posture)."""
    from backend.db.models import PipelineRun
    session.add(PipelineRun(
        run_id_str="test-run-1", status="running",
        provenance_version="provenance_v1",
    ))
    session.commit()
    run_id = session.execute(
        text("SELECT id FROM pipeline_runs WHERE run_id_str = 'test-run-1'")
    ).scalar()

    session.execute(text(
        "INSERT INTO embedding_profiles "
        "(profile_id, profile_schema_version, provider, model_identifier, "
        " dimension, normalization_policy, chunking_schema_version, "
        " collection_name, verification_status, created_at) "
        "VALUES (:pid, 'embedding_profile_v1', 'openai', 'm', 4, 'none', "
        "        'chunk_v1', 'test_col', 'unverified', '2026-01-01 00:00:00')"
    ), {"pid": _PROFILE_ID})
    session.commit()

    now = datetime.now(timezone.utc)
    session.execute(text(
        "INSERT INTO vector_retrieval_events "
        "(run_id, stage_name, retrieval_key, request_schema_version, "
        " scope_mode, scope_schema_version, scope_fingerprint, "
        " embedding_profile_id, profile_verification_status_snapshot, "
        " query_vector_fingerprint, input_fingerprint, "
        " requested_top_k, allow_partial_index_coverage, "
        " allowed_paper_count, indexed_paper_count, unindexed_paper_count, "
        " eligible_vector_record_count, coverage_status, status, attempt_count, "
        " created_at, updated_at, "
        " query_embedding_contract_version, vector_eligibility_contract_version) "
        "VALUES (:rid, 'test_stage', 'test_key', 'vector_retrieval_v1', "
        "        'current_run_only', 'scope_v1', :sf, :pid, 'unverified', "
        "        'qf', 'if', 5, 0, "
        "        1, 1, 0, 1, 'complete', 'success', 0, "
        "        :now, :now, "
        "        'pre_capability_v0', 'pre_capability_v0')"
    ), {"rid": run_id, "sf": "s" * 64, "pid": _PROFILE_ID,
        "qf": "q" * 64, "if": "i" * 64, "now": now})
    session.commit()

    event_id = session.execute(
        text("SELECT id FROM vector_retrieval_events WHERE retrieval_key = 'test_key'")
    ).scalar()

    return run_id, event_id


class TestEvidenceTracer:
    def test_trace_pre_capability_event(self):
        """Trace a pre-capability retrieval event — should be valid
        with pre_capability_v0 contracts."""
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            run_id, event_id = _seed_minimal(session)

            trace = trace_retrieval_evidence(session, event_id)

        assert trace.status == "valid"
        assert trace.query_embedding_contract_version == "pre_capability_v0"
        assert trace.vector_eligibility_contract_version == "pre_capability_v0"
        assert trace.query_capability_binding_id is None
        assert len(trace.integrity_errors) == 0

    def test_trace_nonexistent_event(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            trace = trace_retrieval_evidence(session, 99999)

        assert trace.status == "invalid"
        assert "retrieval_event_not_found" in trace.integrity_errors

    def test_trace_fails_closed_on_binding_mismatch(self):
        """If a result vector's binding doesn't match the query binding,
        the trace must report invalid."""
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            run_id, event_id = _seed_minimal(session)

            # Add a capability query binding to the event
            session.execute(text(
                "UPDATE vector_retrieval_events SET "
                "query_capability_binding_id = :bid "
                "WHERE id = :eid"
            ), {"bid": "a" * 64, "eid": event_id})
            session.commit()

            # Add a result with a DIFFERENT binding
            now2 = datetime.now(timezone.utc)

            # Seed Paper FIRST (FK for vector_index_records)
            from backend.db.models import Paper
            session.add(Paper(id=1, source_id="p1", source="test", title="T", abstract="A", authors="[]"))
            session.commit()

            # Seed the binding that the vector references (FK)
            session.execute(text(
                "INSERT INTO embedding_capability_bindings "
                "(binding_id, embedding_profile_id, provider_kind, resolved_model, "
                " model_resolution_posture, resolved_dimension, resolved_normalization, "
                " postprocessing_contract_version, resolved_endpoint_identity, "
                " profile_schema_version, provider_adapter_contract_version, "
                " governed_adapter_contract_version, resolution_classifier_version, "
                " binding_schema_version) "
                "VALUES (:bid2, :pid, 'openai', 'm', 'configured_match', 4, 'none', "
                "        'none', 'provider-default://unset', 'embedding_profile_v1', "
                "        'v1', 'v1', 'v1', 'capability_binding_v1')"
            ), {"bid2": "b" * 64, "pid": _PROFILE_ID})

            # Seed the check that the vector references (FK)
            session.execute(text(
                "INSERT INTO embedding_capability_checks "
                "(check_id, embedding_profile_id, binding_id, "
                " runtime_config_fingerprint, probe_suite_version, "
                " check_status, probe_kind, check_schema_version, "
                " completed_at, expires_at, probed_at) "
                "VALUES (:gcid, :pid, :bid2, :fp, 'embedding_probe_suite_v1', "
                "        'passed', 'dual_probe', 'capability_check_v1', "
                "        :now, :now2, :now)"
            ), {"gcid": "g" * 64, "pid": _PROFILE_ID, "bid2": "b" * 64,
                "fp": "f" * 64, "now": now2, "now2": now2})
            session.commit()

            session.execute(text(
                "INSERT INTO vector_index_records "
                "(vector_record_id, paper_id, chunk_key, content_kind, content_hash, "
                " embedding_profile_id, vector_store, collection_name, index_schema_version, "
                " embedding_contract_version, capability_binding_id, generation_capability_check_id, "
                " index_status, attempt_count, indexed_at, backend_verified_at, "
                " created_at, updated_at) "
                "VALUES (:vid, 1, 'test', 'title_abstract', :ch, :pid, 'chroma', 'col', "
                "        'vector_index_v2', 'capability_v1', :bid2, :gcid, "
                "        'indexed', 1, :now, :now, :now, :now)"
            ), {"vid": "v" * 64, "ch": "h" * 64, "pid": _PROFILE_ID,
                "bid2": "b" * 64, "gcid": "g" * 64, "now": now2})

            session.execute(text(
                "INSERT INTO vector_retrieval_eligible_records "
                "(retrieval_event_id, vector_record_id) "
                "VALUES (:eid, :vid)"
            ), {"eid": event_id, "vid": "v" * 64})

            session.execute(text(
                "INSERT INTO vector_retrieval_results "
                "(retrieval_event_id, rank, vector_record_id, canonical_distance) "
                "VALUES (:eid, 1, :vid, 0.5)"
            ), {"eid": event_id, "vid": "v" * 64})
            session.commit()

            trace = trace_retrieval_evidence(session, event_id)

        assert trace.status == "invalid"
        assert any("binding_mismatch" in e for e in trace.integrity_errors)
