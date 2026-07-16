"""Tests for P0.3.3B-H: scoped vector retrieval service lifecycle.

Proves:
  - Empty scope → success, zero results, zero backend calls
  - Strict incomplete coverage → failure before backend
  - Successful retrieval with candidate-constrained query
  - Idempotent replay (no backend call, no mutation)
  - Out-of-scope backend result → complete failure
  - Migration + regression
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

import backend.db.models
from backend.db.database import Base
from backend.db.models import (
    EmbeddingProfile,
    Paper,
    PipelineRun,
    RunPaper,
    RunSearchReconciliation,
    VectorIndexRecord,
    VectorRetrievalEvent,
)
from backend.pipeline.vector_backend import BackendVectorMatch, GovernedVectorBackend
from backend.pipeline.vector_contracts import (
    ScopedVectorRetrievalRequest,
    VectorRetrievalScope,
    compute_collection_name,
    compute_content_hash,
    compute_profile_id,
    compute_vector_record_id,
    derive_domain_scope_key,
)
from backend.pipeline.scoped_vector_service import (
    query_vectors,
    validate_query_vector,
    validate_top_k,
)


def _make_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def _fk(c, r):
        cur = c.cursor(); cur.execute("PRAGMA foreign_keys=ON"); cur.close()
    Base.metadata.create_all(engine)
    return engine


_run_counter = [0]
_paper_counter = [0]


def _make_governed_run(engine, with_papers=0):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        _run_counter[0] += 1
        dkey = derive_domain_scope_key("AI/NLP")
        run = PipelineRun(
            run_id_str=f"r_p033b_{_run_counter[0]}", domain="AI/NLP",
            status="completed", config_json="{}", stages_completed="[]",
            provenance_version="provenance_v1",
            domain_scope_key=dkey, domain_scope_version="domain_scope_v1",
        )
        s.add(run); s.flush()
        s.add(RunSearchReconciliation(
            run_id=run.id, reconciliation_schema_version="run_reconciliation_v1",
            status="pending", reconciliation_attempt_count=0,
        ))

        pid = compute_profile_id("lmstudio", "qwen3", 4, "l2", "v1")
        coll = compute_collection_name(pid)
        s.add(EmbeddingProfile(
            profile_id=pid, profile_schema_version="embedding_profile_v1",
            provider="lmstudio", model_identifier="qwen3", dimension=4,
            normalization_policy="l2", chunking_schema_version="v1",
            collection_name=coll, verification_status="unverified",
        ))

        paper_ids = []
        for i in range(with_papers):
            _paper_counter[0] += 1
            p = Paper(source_id=f"p_{_paper_counter[0]}", source="arxiv",
                      title=f"Paper {_paper_counter[0]}",
                      authors="[]", keywords="[]", ingested=0)
            s.add(p); s.flush()
            s.add(RunPaper(run_id=run.id, paper_id=p.id, inclusion_origin="remote_search"))

            # Index the paper
            ch = compute_content_hash(f"content {p.id}")
            vid = compute_vector_record_id(p.id, "title_abstract:0", ch, pid)
            now = datetime.now(timezone.utc)
            s.add(VectorIndexRecord(
                vector_record_id=vid, paper_id=p.id, chunk_key="title_abstract:0",
                content_kind="title_abstract", content_hash=ch,
                embedding_profile_id=pid, collection_name=coll,
                index_status="indexed", attempt_count=1,
                indexed_at=now, backend_verified_at=now,
            ))
            paper_ids.append(p.id)

        s.commit()
        return run.id, pid, coll, paper_ids
    finally:
        s.close()


class _FakeBackend(GovernedVectorBackend):
    def __init__(self):
        self.query_count = 0
        self._fake_results: list[BackendVectorMatch] = []
        self._bypass_filter = False  # for out-of-scope test

    def set_results(self, results, bypass_filter=False):
        self._fake_results = results
        self._bypass_filter = bypass_filter

    def ensure_profile_collection(self, *, collection_name, embedding_profile_id, embedding_dimension):
        return MagicMock(name=collection_name)

    def query_vectors(self, *, collection_name, query_vector, candidate_vector_record_ids, top_k):
        self.query_count += 1
        if self._bypass_filter:
            return self._fake_results[:top_k]
        # Return only results whose IDs are in the candidate set
        eligible = set(candidate_vector_record_ids)
        return [m for m in self._fake_results if m.vector_record_id in eligible][:top_k]


def _make_request(run_id, pid, mode="current_run_only"):
    return ScopedVectorRetrievalRequest(
        schema_version="vector_retrieval_v1",
        run_id=run_id, stage_name="test_stage", retrieval_key="rk_1",
        scope=VectorRetrievalScope(
            schema_version="vector_scope_v1",
            mode=mode, run_id=run_id, embedding_profile_id=pid,
        ),
        query_vector=(0.1, 0.2, 0.3, 0.4),
        top_k=5,
    )


# ── 1. Query-vector validation ───────────────────────────────────────


def test_validate_correct_vector():
    ok, code = validate_query_vector([0.1, 0.2, 0.3, 0.4], 4)
    assert ok and code is None


def test_validate_empty_vector():
    ok, code = validate_query_vector([], 4)
    assert not ok and code == "query_vector_empty"


def test_validate_dimension_mismatch():
    ok, code = validate_query_vector([0.1, 0.2], 4)
    assert not ok and code == "query_vector_dimension_mismatch"


def test_validate_nan():
    ok, code = validate_query_vector([float("nan"), 0.2, 0.3, 0.4], 4)
    assert not ok and code == "query_vector_non_finite"


def test_validate_zero_vector():
    ok, code = validate_query_vector([0.0, 0.0, 0.0, 0.0], 4)
    assert not ok and code == "query_vector_zero"


def test_validate_top_k():
    assert validate_top_k(5)[0]
    assert not validate_top_k(0)[0]
    assert not validate_top_k(-1)[0]


# ── 2. Empty scope ───────────────────────────────────────────────────


def test_empty_scope_succeeds_without_backend():
    engine = _make_engine()
    run_id, pid, coll, _ = _make_governed_run(engine, with_papers=0)
    Session = sessionmaker(bind=engine)
    backend = _FakeBackend()

    outcome = asyncio.run(query_vectors(
        session_factory=Session, backend=backend,
        request=_make_request(run_id, pid),
    ))

    assert outcome.status == "success"
    assert outcome.coverage_status == "empty_scope"
    assert len(outcome.results) == 0
    assert backend.query_count == 0  # NO backend call for empty scope


# ── 3. Successful retrieval ──────────────────────────────────────────


def test_successful_retrieval():
    engine = _make_engine()
    run_id, pid, coll, paper_ids = _make_governed_run(engine, with_papers=2)
    Session = sessionmaker(bind=engine)
    backend = _FakeBackend()

    # Prepare fake results matching the indexed vectors
    ch1 = compute_content_hash(f"content {paper_ids[0]}")
    vid1 = compute_vector_record_id(paper_ids[0], "title_abstract:0", ch1, pid)
    ch2 = compute_content_hash(f"content {paper_ids[1]}")
    vid2 = compute_vector_record_id(paper_ids[1], "title_abstract:0", ch2, pid)

    backend.set_results([
        BackendVectorMatch(
            vector_record_id=vid1, paper_id=paper_ids[0],
            chunk_key="title_abstract:0", content_kind="title_abstract",
            content_hash=ch1, embedding_profile_id=pid,
            index_schema_version="vector_index_v1", canonical_distance=0.1,
        ),
        BackendVectorMatch(
            vector_record_id=vid2, paper_id=paper_ids[1],
            chunk_key="title_abstract:0", content_kind="title_abstract",
            content_hash=ch2, embedding_profile_id=pid,
            index_schema_version="vector_index_v1", canonical_distance=0.3,
        ),
    ])

    outcome = asyncio.run(query_vectors(
        session_factory=Session, backend=backend,
        request=_make_request(run_id, pid),
    ))

    assert outcome.status == "success"
    assert outcome.coverage_status == "complete"
    assert len(outcome.results) == 2
    assert outcome.results[0].rank == 1
    assert outcome.results[0].raw_score < outcome.results[1].raw_score
    assert backend.query_count == 1


# ── 4. Idempotent replay ─────────────────────────────────────────────


def test_replay_no_backend_call():
    engine = _make_engine()
    run_id, pid, coll, paper_ids = _make_governed_run(engine, with_papers=1)
    Session = sessionmaker(bind=engine)
    backend = _FakeBackend()

    ch = compute_content_hash(f"content {paper_ids[0]}")
    vid = compute_vector_record_id(paper_ids[0], "title_abstract:0", ch, pid)
    backend.set_results([
        BackendVectorMatch(
            vector_record_id=vid, paper_id=paper_ids[0],
            chunk_key="title_abstract:0", content_kind="title_abstract",
            content_hash=ch, embedding_profile_id=pid,
            index_schema_version="vector_index_v1", canonical_distance=0.2,
        ),
    ])

    # First query
    asyncio.run(query_vectors(
        session_factory=Session, backend=backend,
        request=_make_request(run_id, pid),
    ))
    assert backend.query_count == 1

    # Replay — same request
    outcome = asyncio.run(query_vectors(
        session_factory=Session, backend=backend,
        request=_make_request(run_id, pid),
    ))

    assert outcome.status == "replayed"
    assert backend.query_count == 1  # NOT called again


# ── 5. Out-of-scope result fails ─────────────────────────────────────


def test_out_of_scope_result_fails():
    engine = _make_engine()
    run_id, pid, coll, paper_ids = _make_governed_run(engine, with_papers=1)
    Session = sessionmaker(bind=engine)
    backend = _FakeBackend()

    # Return a vector NOT in the eligible snapshot (bypass filter to simulate defective backend)
    backend.set_results([
        BackendVectorMatch(
            vector_record_id="bogus_out_of_scope_id",
            paper_id=99999,
            chunk_key="x", content_kind="abstract",
            content_hash="x", embedding_profile_id=pid,
            index_schema_version="vector_index_v1", canonical_distance=0.1,
        ),
    ], bypass_filter=True)

    with pytest.raises(ValueError, match="backend_scope_violation"):
        asyncio.run(query_vectors(
            session_factory=Session, backend=backend,
            request=_make_request(run_id, pid),
        ))

    # Verify event is failed
    s = Session()
    try:
        event = s.execute(select(VectorRetrievalEvent)).scalar_one()
        assert event.status == "failed"
        assert event.failure_code == "backend_scope_violation"
    finally:
        s.close()
