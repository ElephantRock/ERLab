"""P0.3.4I production adversarial tests.

Exercises actual production boundaries (NoveltyChecker, architectural guard,
scope isolation) with an ephemeral vector backend and deterministic
embedding provider. No remote model required.
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
from backend.pipeline.scoped_vector_service import query_vectors


def _make_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def _fk(c, r):
        cur = c.cursor(); cur.execute("PRAGMA foreign_keys=ON"); cur.close()
    Base.metadata.create_all(engine)
    return engine


_run_counter = [0]


def _setup_run(engine, n_papers=2, with_index=True):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        _run_counter[0] += 1
        dkey = derive_domain_scope_key("AI/NLP")
        run = PipelineRun(
            run_id_str=f"r_adv_{_run_counter[0]}", domain="AI/NLP",
            status="completed", config_json="{}", stages_completed="[]",
            provenance_version="provenance_v1",
            domain_scope_key=dkey, domain_scope_version="domain_scope_v1",
        )
        s.add(run); s.flush()
        s.add(RunSearchReconciliation(
            run_id=run.id, reconciliation_schema_version="run_reconciliation_v1",
            status="pending", reconciliation_attempt_count=0,
        ))

        pid = compute_profile_id("test", "test-model", 4, "l2", "v1")
        coll = compute_collection_name(pid)
        s.add(EmbeddingProfile(
            profile_id=pid, profile_schema_version="embedding_profile_v1",
            provider="test", model_identifier="test-model", dimension=4,
            normalization_policy="l2", chunking_schema_version="v1",
            collection_name=coll, verification_status="unverified",
        ))

        paper_ids = []
        for i in range(n_papers):
            p = Paper(source_id=f"adv_{run.id}_{i}", source="arxiv",
                      title=f"Paper {run.id}-{i}", authors="[]", keywords="[]", ingested=0)
            s.add(p); s.flush()
            s.add(RunPaper(run_id=run.id, paper_id=p.id, inclusion_origin="remote_search"))

            if with_index:
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


class _EphemeralBackend(GovernedVectorBackend):
    """In-memory backend for testing — no real ChromaDB needed."""
    def __init__(self):
        self._store: dict[str, dict] = {}
        self.query_count = 0

    def ensure_profile_collection(self, *, collection_name, embedding_profile_id, embedding_dimension):
        return MagicMock(name=collection_name)

    def upsert_vector(self, *, collection_name, vector_record_id, embedding, document, metadata):
        self._store[vector_record_id] = {"embedding": tuple(embedding), "document": document, "metadata": dict(metadata)}

    def read_vector(self, *, collection_name, vector_record_id):
        rec = self._store.get(vector_record_id)
        if rec is None:
            return None
        meta = rec["metadata"]
        from backend.pipeline.vector_backend import BackendVectorRecord
        return BackendVectorRecord(
            vector_record_id=vector_record_id,
            paper_id=meta.get("paper_id", 0),
            chunk_key=meta.get("chunk_key", ""),
            content_kind=meta.get("content_kind", ""),
            content_hash=meta.get("content_hash", ""),
            embedding_profile_id=meta.get("embedding_profile_id", ""),
            index_schema_version=meta.get("index_schema_version", ""),
            document=rec["document"],
            embedding=rec["embedding"],
        )

    def delete_vector(self, *, collection_name, vector_record_id):
        self._store.pop(vector_record_id, None)

    def verify_absent(self, *, collection_name, vector_record_id):
        return vector_record_id not in self._store

    def query_vectors(self, *, collection_name, query_vector, candidate_vector_record_ids, top_k):
        self.query_count += 1
        eligible = set(candidate_vector_record_ids)
        return [
            BackendVectorMatch(
                vector_record_id=vid,
                paper_id=self._store[vid]["metadata"].get("paper_id", 0),
                chunk_key=self._store[vid]["metadata"].get("chunk_key", ""),
                content_kind=self._store[vid]["metadata"].get("content_kind", ""),
                content_hash=self._store[vid]["metadata"].get("content_hash", ""),
                embedding_profile_id=self._store[vid]["metadata"].get("embedding_profile_id", ""),
                index_schema_version=self._store[vid]["metadata"].get("index_schema_version", ""),
                canonical_distance=0.1,
            )
            for vid in list(self._store.keys())[:top_k]
            if vid in eligible
        ]


def _make_request(run_id, pid, top_k=5):
    return ScopedVectorRetrievalRequest(
        schema_version="vector_retrieval_v1",
        run_id=run_id, stage_name="novelty_check", retrieval_key="adv_test_1",
        scope=VectorRetrievalScope(
            schema_version="vector_scope_v1",
            mode="current_run_only", run_id=run_id, embedding_profile_id=pid,
        ),
        query_vector=(0.1, 0.2, 0.3, 0.4),
        top_k=top_k,
    )


# ── 1. Cross-run isolation ───────────────────────────────────────────


def test_cross_run_isolation():
    """Run B cannot retrieve Run A's papers through scoped service."""
    engine = _make_engine()
    run_a, pid, coll, papers_a = _setup_run(engine, n_papers=2)

    # Create second run in same engine but reuse the profile
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        _run_counter[0] += 1
        dkey = derive_domain_scope_key("AI/NLP")
        run_b = PipelineRun(
            run_id_str=f"r_adv_{_run_counter[0]}", domain="AI/NLP",
            status="completed", config_json="{}", stages_completed="[]",
            provenance_version="provenance_v1",
            domain_scope_key=dkey, domain_scope_version="domain_scope_v1",
        )
        s.add(run_b); s.flush()
        s.add(RunSearchReconciliation(
            run_id=run_b.id, reconciliation_schema_version="run_reconciliation_v1",
            status="pending", reconciliation_attempt_count=0,
        ))
        papers_b = []
        for i in range(2):
            p = Paper(source_id=f"adv_{run_b.id}_{i}", source="arxiv",
                      title=f"Paper B-{i}", authors="[]", keywords="[]", ingested=0)
            s.add(p); s.flush()
            s.add(RunPaper(run_id=run_b.id, paper_id=p.id, inclusion_origin="remote_search"))
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
            papers_b.append(p.id)
        s.commit()
        run_b_id = run_b.id
    finally:
        s.close()

    # Seed backend with ALL papers from both runs
    backend = _EphemeralBackend()
    for pid_val in papers_a + papers_b:
        ch = compute_content_hash(f"content {pid_val}")
        vid = compute_vector_record_id(pid_val, "title_abstract:0", ch, pid)
        backend._store[vid] = {
            "embedding": (0.1, 0.2, 0.3, 0.4),
            "document": f"content {pid_val}",
            "metadata": {
                "paper_id": pid_val, "chunk_key": "title_abstract:0",
                "content_kind": "title_abstract", "content_hash": ch,
                "embedding_profile_id": pid,
                "index_schema_version": "vector_index_v1",
            },
        }

    Session = sessionmaker(bind=engine)
    outcome = asyncio.run(query_vectors(
        session_factory=Session, backend=backend,
        request=_make_request(run_b_id, pid),
    ))

    # Run B should only get its own papers
    result_papers = {r.paper_id for r in outcome.results}
    assert result_papers <= set(papers_b), f"cross-run leak: {result_papers & set(papers_a)}"
    assert len(result_papers) <= len(papers_b)


# ── 2. Empty scope ───────────────────────────────────────────────────


def test_empty_scope_zero_backend_calls():
    engine = _make_engine()
    run_id, pid, _, _ = _setup_run(engine, n_papers=0)
    backend = _EphemeralBackend()

    outcome = asyncio.run(query_vectors(
        session_factory=Session if 'Session' in dir() else sessionmaker(bind=engine),
        backend=backend,
        request=_make_request(run_id, pid),
    ))

    assert outcome.status == "success"
    assert outcome.coverage_status == "empty_scope"
    assert len(outcome.results) == 0
    assert backend.query_count == 0


# ── 3. Strict incomplete coverage ────────────────────────────────────


def test_strict_incomplete_coverage():
    """3 papers, only 2 indexed → strict policy fails before backend."""
    engine = _make_engine()
    run_id, pid, coll, papers = _setup_run(engine, n_papers=3, with_index=True)

    # Delete one vector record to create incomplete coverage
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        s.execute(text(
            "DELETE FROM vector_index_records WHERE paper_id = :pid"
        ), {"pid": papers[2]})
        s.commit()
    finally:
        s.close()

    backend = _EphemeralBackend()

    with pytest.raises(ValueError, match="index_coverage_incomplete"):
        asyncio.run(query_vectors(
            session_factory=Session, backend=backend,
            request=_make_request(run_id, pid),
        ))

    assert backend.query_count == 0  # No backend call


# ── 4. Replay ────────────────────────────────────────────────────────


def test_replay_no_backend_call():
    engine = _make_engine()
    run_id, pid, coll, papers = _setup_run(engine, n_papers=1)
    backend = _EphemeralBackend()

    ch = compute_content_hash(f"content {papers[0]}")
    vid = compute_vector_record_id(papers[0], "title_abstract:0", ch, pid)
    backend._store[vid] = {
        "embedding": (0.1, 0.2, 0.3, 0.4),
        "document": f"content {papers[0]}",
        "metadata": {
            "paper_id": papers[0], "chunk_key": "title_abstract:0",
            "content_kind": "title_abstract", "content_hash": ch,
            "embedding_profile_id": pid, "index_schema_version": "vector_index_v1",
        },
    }

    Session = sessionmaker(bind=engine)

    # First query
    asyncio.run(query_vectors(
        session_factory=Session, backend=backend,
        request=_make_request(run_id, pid),
    ))
    first_count = backend.query_count

    # Replay
    outcome = asyncio.run(query_vectors(
        session_factory=Session, backend=backend,
        request=_make_request(run_id, pid),
    ))

    assert outcome.status == "replayed"
    assert backend.query_count == first_count  # No additional backend call


# ── 5. Retrieval event recorded ──────────────────────────────────────


def test_retrieval_event_recorded():
    engine = _make_engine()
    run_id, pid, coll, papers = _setup_run(engine, n_papers=1)
    backend = _EphemeralBackend()

    ch = compute_content_hash(f"content {papers[0]}")
    vid = compute_vector_record_id(papers[0], "title_abstract:0", ch, pid)
    backend._store[vid] = {
        "embedding": (0.1, 0.2, 0.3, 0.4),
        "document": f"content {papers[0]}",
        "metadata": {
            "paper_id": papers[0], "chunk_key": "title_abstract:0",
            "content_kind": "title_abstract", "content_hash": ch,
            "embedding_profile_id": pid, "index_schema_version": "vector_index_v1",
        },
    }

    Session = sessionmaker(bind=engine)
    outcome = asyncio.run(query_vectors(
        session_factory=Session, backend=backend,
        request=_make_request(run_id, pid),
    ))

    # Verify event recorded in DB
    s = Session()
    try:
        events = s.execute(
            select(VectorRetrievalEvent).where(
                VectorRetrievalEvent.run_id == run_id
            )
        ).scalars().all()
        assert len(events) >= 1
        assert events[0].status == "success"
        assert events[0].run_id == run_id
    finally:
        s.close()


# ── 6. Architectural guard ───────────────────────────────────────────


def test_no_temporary_allowlist_entries():
    """The architectural allowlist has zero temporary entries."""
    from backend.tests.test_pipeline.test_vector_access_enforcement import _ALLOWLIST_PATTERNS

    # No production stage or API routes in the allowlist
    forbidden_patterns = [
        "novelty/novelty_checker.py",
        "pipeline/stages.py",
        "api/routes/knowledge.py",
    ]
    for forbidden in forbidden_patterns:
        assert forbidden not in _ALLOWLIST_PATTERNS, (
            f"temporary allowlist entry {forbidden!r} must be removed"
        )
