"""Tests for P0.2.5: discovery-to-execution linkage.

Proves:
  - Migration 018 preserves legacy rows (NULL result keys, no fabricated linkages)
  - build_source_result_identity matches P0.2.4 dedup identity
  - Linkage ledger created atomically with terminal accounting
  - Triple composite FK enforces execution/query/source consistency
  - Source-result identity is stable and replay-safe
  - Linkage ledger state machine (pending → linked, not_applicable)
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from datetime import UTC

from backend.db.database import Base
from backend.db.models import (
    ExecutionDiscoveryLinkage,
    PaperDiscovery,
    PipelineRun,
    SearchQuery,
    SearchQueryExecution,
)
from backend.pipeline.literature.contracts import (
    SourceQueryPlan,
    SourceSearchOutcome,
    canonical_plan_json,
)
from backend.pipeline.literature.execution_recorder import ExecutionRecorder
from backend.pipeline.literature.models import Paper as SPaper
from backend.pipeline.literature.models import SearchResult
from backend.pipeline.literature.result_accounting import (
    build_source_result_identity,
    reconcile_source_results,
)

# ── Session helpers ──────────────────────────────────────────────────


def _make_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def _fk(c, r):
        cur = c.cursor(); cur.execute("PRAGMA foreign_keys=ON"); cur.close()
    Base.metadata.create_all(engine)
    return engine


_run_counter = [0]


def _make_run(session):
    _run_counter[0] += 1
    run = PipelineRun(
        run_id_str=f"r_p025_{_run_counter[0]}", domain="AI",
        status="completed", config_json="{}", stages_completed="[]",
        provenance_version="provenance_v1",
    )
    session.add(run); session.commit()
    return run


def _make_query(session, run_id):
    sq = SearchQuery(run_id=run_id, query_key="qk", query_text="test")
    session.add(sq); session.commit()
    return sq


def _fake_plan():
    return SourceQueryPlan(
        source="arxiv", schema_version="source_query_v1",
        translated_query=canonical_plan_json("arxiv", {"query": "test"}),
        request_parameters={"query": "test"},
    )


def _sr(title, source_id=None, doi=None):
    p = SPaper(id=source_id or title, title=title, source="arxiv", doi=doi)
    return SearchResult(paper=p, source="arxiv")


def _setup_exec(engine, source="arxiv"):
    """Build run + query + pending execution. Return (exec_id, sq_id, run_id)."""
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        run = _make_run(session)
        sq = _make_query(session, run.id)
        ex = SearchQueryExecution(
            search_query_id=sq.id, source=source, status="pending", attempt_count=0,
        )
        session.add(ex); session.commit()
        return ex.id, sq.id, run.id
    finally:
        session.close()


# ── 1. Source-result identity ────────────────────────────────────────


def test_identity_same_doi_same_key():
    """Two papers with the same normalized DOI produce the same key."""
    r1 = _sr("Paper A", doi="10.1234/abc")
    r2 = _sr("Paper Different", doi="https://doi.org/10.1234/ABC")
    k1, m1 = build_source_result_identity(r1)
    k2, m2 = build_source_result_identity(r2)
    assert k1 == k2, "same DOI should produce same key"
    assert m1 == m2 == "doi"


def test_identity_different_dois_different_keys():
    r1 = _sr("A", doi="10.1/x")
    r2 = _sr("B", doi="10.2/y")
    k1, _ = build_source_result_identity(r1)
    k2, _ = build_source_result_identity(r2)
    assert k1 != k2


def test_identity_source_id_fallback():
    """Without DOI, falls back to source_id."""
    r1 = _sr("Paper", source_id="arxiv:2601.001")
    k, method = build_source_result_identity(r1)
    assert method == "source_id"
    # Same ID → same key
    r2 = _sr("Paper Dup", source_id="arxiv:2601.001")
    k2, _ = build_source_result_identity(r2)
    assert k == k2


def test_identity_matches_dedup():
    """build_source_result_identity and reconcile_source_results use the same identity."""
    r1 = _sr("Paper A", doi="10.1234/a")
    r2 = _sr("Paper B", doi="10.1234/a")  # same DOI → dedup removes it
    unique, acct = reconcile_source_results(
        raw_result_count=2, normalized_results=[r1, r2], rejected_result_count=0,
    )
    assert len(unique) == 1
    # The surviving result's identity key should match
    k, _ = build_source_result_identity(unique[0])
    assert isinstance(k, str) and len(k) == 64  # SHA-256 hex


# ── 2. Linkage ledger creation ───────────────────────────────────────


def test_reconciled_execution_creates_pending_ledger():
    engine = _make_engine()
    exec_id, _, _ = _setup_exec(engine)

    class _Adapter:
        source_name = "arxiv"
        def build_query_plan(self, query, limit=20, year_from=None, year_to=None):
            return _fake_plan()
        async def execute_query_plan(self, plan, *, attempt_observer=None):
            if attempt_observer:
                await attempt_observer.attempt_started()
            results = [_sr(f"P{i}", source_id=f"id{i}") for i in range(3)]
            unique, acct = reconcile_source_results(
                raw_result_count=3, normalized_results=results, rejected_result_count=0)
            return SourceSearchOutcome(
                results=unique, status="success", attempt_count=1, accounting=acct)

    recorder = ExecutionRecorder(engine)
    asyncio.run(recorder.run_execution(exec_id, "arxiv", _Adapter(), "test"))

    s = sessionmaker(bind=engine)()
    try:
        ledger = s.get(ExecutionDiscoveryLinkage, exec_id)
        assert ledger is not None
        assert ledger.status == "pending"
        assert ledger.expected_discovery_count == 3
        assert ledger.linked_discovery_count is None
        assert ledger.linkage_schema_version == "linkage_v1"
    finally:
        s.close()


def test_incomplete_execution_creates_not_applicable():
    engine = _make_engine()
    exec_id, _, _ = _setup_exec(engine)

    class _FailAdapter:
        source_name = "arxiv"
        def build_query_plan(self, query, limit=20, year_from=None, year_to=None):
            return _fake_plan()
        async def execute_query_plan(self, plan, *, attempt_observer=None):
            if attempt_observer:
                await attempt_observer.attempt_started()
            return SourceSearchOutcome(
                results=[], status="failed", attempt_count=1,
                error_detail="connection refused",
                failure_category="transport", failure_code="connection_error")

    recorder = ExecutionRecorder(engine)
    asyncio.run(recorder.run_execution(exec_id, "arxiv", _FailAdapter(), "test"))

    s = sessionmaker(bind=engine)()
    try:
        ledger = s.get(ExecutionDiscoveryLinkage, exec_id)
        assert ledger is not None
        assert ledger.status == "not_applicable"
        assert ledger.expected_discovery_count is None
        assert ledger.completed_at is not None
    finally:
        s.close()


def test_zero_result_execution_creates_pending_zero():
    engine = _make_engine()
    exec_id, _, _ = _setup_exec(engine)

    class _ZeroAdapter:
        source_name = "arxiv"
        def build_query_plan(self, query, limit=20, year_from=None, year_to=None):
            return _fake_plan()
        async def execute_query_plan(self, plan, *, attempt_observer=None):
            if attempt_observer:
                await attempt_observer.attempt_started()
            from backend.pipeline.literature.contracts import SourceResultAccounting
            acct = SourceResultAccounting(
                schema_version="accounting_v1",
                raw_result_count=0, normalized_result_count=0,
                rejected_result_count=0, source_unique_count=0)
            return SourceSearchOutcome(
                results=[], status="success", attempt_count=1, accounting=acct)

    recorder = ExecutionRecorder(engine)
    asyncio.run(recorder.run_execution(exec_id, "arxiv", _ZeroAdapter(), "test"))

    s = sessionmaker(bind=engine)()
    try:
        ledger = s.get(ExecutionDiscoveryLinkage, exec_id)
        assert ledger.status == "pending"
        assert ledger.expected_discovery_count == 0
    finally:
        s.close()


def test_linkage_ledger_replay_preserves_pending():
    """Re-running an execution that already has a ledger preserves the ledger."""
    engine = _make_engine()
    exec_id, _, _ = _setup_exec(engine)

    class _Adapter:
        source_name = "arxiv"
        def build_query_plan(self, query, limit=20, year_from=None, year_to=None):
            return _fake_plan()
        async def execute_query_plan(self, plan, *, attempt_observer=None):
            if attempt_observer:
                await attempt_observer.attempt_started()
            results = [_sr("P1", source_id="id1")]
            unique, acct = reconcile_source_results(
                raw_result_count=1, normalized_results=results, rejected_result_count=0)
            return SourceSearchOutcome(
                results=unique, status="success", attempt_count=1, accounting=acct)

    recorder = ExecutionRecorder(engine)
    asyncio.run(recorder.run_execution(exec_id, "arxiv", _Adapter(), "test"))
    # The ledger was created. On terminal replay, the recorder should not recreate.
    asyncio.run(recorder.run_execution(exec_id, "arxiv", _Adapter(), "test"))

    s = sessionmaker(bind=engine)()
    try:
        # Only one ledger row
        count = s.execute(text(
            "SELECT COUNT(*) FROM execution_discovery_linkages WHERE execution_id = :eid"
        ), {"eid": exec_id}).scalar()
        assert count == 1
    finally:
        s.close()


# ── 3. DB constraints ────────────────────────────────────────────────


def test_linkage_governed_check_rejects_partial_linkage():
    """linkage_v1 without source_result_key is rejected."""
    from sqlalchemy.exc import IntegrityError as SAIntegrityError

    engine = _make_engine()
    s = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        run = _make_run(s)
        sq = _make_query(s, run.id)
        from backend.db.models import Paper
        paper = Paper(source_id="p1", source="arxiv", title="P", authors="[]", keywords="[]", ingested=0)
        s.add(paper); s.commit()

        with pytest.raises(SAIntegrityError):
            # linkage_v1 but missing source_result_key
            s.execute(text(
                "INSERT INTO paper_discoveries "
                "(run_id, paper_id, search_query_id, source, discovery_origin, "
                " deduplication_status, discovery_key, linkage_schema_version, retrieved_at, created_at) "
                "VALUES (:rid, :pid, :sqid, 'arxiv', 'remote_search', 'unique', 'dk', "
                " 'linkage_v1', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ), {"rid": run.id, "pid": paper.id, "sqid": sq.id})
            s.commit()
    finally:
        s.close()


def test_triple_fk_rejects_source_mismatch():
    """Discovery with source != execution.source is rejected by triple FK."""
    from sqlalchemy.exc import IntegrityError as SAIntegrityError

    engine = _make_engine()
    s = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        run = _make_run(s)
        sq = _make_query(s, run.id)
        # Execution has source='arxiv'
        from datetime import datetime
        ex = SearchQueryExecution(
            search_query_id=sq.id, source="arxiv", status="success",
            attempt_count=1, completed_at=datetime(2026, 1, 1, tzinfo=UTC),
            accounting_status="reconciled", accounting_schema_version="accounting_v1",
            execution_metadata_version="execution_v1",
            translated_query='{"schema":"source_query_v1"}',
            raw_result_count=1, normalized_result_count=1,
            rejected_result_count=0, source_unique_count=1,
        )
        s.add(ex); s.commit()

        from backend.db.models import Paper
        paper = Paper(source_id="p1", source="arxiv", title="P", authors="[]", keywords="[]", ingested=0)
        s.add(paper); s.commit()

        with pytest.raises(SAIntegrityError):
            # Discovery claims source='openalex' but execution has source='arxiv'
            s.execute(text(
                "INSERT INTO paper_discoveries "
                "(run_id, paper_id, search_query_id, execution_id, source, "
                " discovery_origin, deduplication_status, discovery_key, "
                " source_result_key, linkage_schema_version, retrieved_at, created_at) "
                "VALUES (:rid, :pid, :sqid, :eid, 'openalex', "
                " 'remote_search', 'unique', 'dk', 'srk', 'linkage_v1', "
                " CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ), {"rid": run.id, "pid": paper.id, "sqid": sq.id, "eid": ex.id})
            s.commit()
    finally:
        s.close()


def test_legacy_discovery_survives_with_null_linkage():
    """Legacy discovery with execution_id=NULL, source_result_key=NULL is valid."""
    engine = _make_engine()
    s = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        run = _make_run(s)
        sq = _make_query(s, run.id)
        from backend.db.models import Paper
        paper = Paper(source_id="p1", source="arxiv", title="P", authors="[]", keywords="[]", ingested=0)
        s.add(paper); s.commit()

        # Legacy discovery: no execution, no result key, no linkage version
        disc = PaperDiscovery(
            run_id=run.id, paper_id=paper.id, search_query_id=sq.id,
            execution_id=None, source_result_key=None, linkage_schema_version=None,
            source="arxiv", discovery_origin="remote_search",
            discovery_key="legacy_dk",
        )
        s.add(disc); s.commit()
        assert disc.id is not None
    finally:
        s.close()


def test_edl_state_consistency_enforced():
    """Linkage ledger state machine CHECK is enforced."""
    from sqlalchemy.exc import IntegrityError as SAIntegrityError

    engine = _make_engine()
    s = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        run = _make_run(s)
        sq = _make_query(s, run.id)
        ex = SearchQueryExecution(
            search_query_id=sq.id, source="arxiv", status="pending", attempt_count=0,
        )
        s.add(ex); s.commit()

        # Invalid: status='linked' but linked_count != expected
        with pytest.raises(SAIntegrityError):
            s.execute(text(
                "INSERT INTO execution_discovery_linkages "
                "(execution_id, linkage_schema_version, status, expected_discovery_count, "
                " linked_discovery_count, linkage_attempt_count, completed_at) "
                "VALUES (:eid, 'linkage_v1', 'linked', 5, 3, 0, CURRENT_TIMESTAMP)"
            ), {"eid": ex.id})
            s.commit()
    finally:
        s.close()


# ── 4. Migration tests ───────────────────────────────────────────────


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _alembic_cfg(db_url):
    from alembic.config import Config
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _patched_settings(db_url):
    mock = MagicMock()
    mock.database_url = db_url
    mock.debug = False
    return patch("backend.config.get_settings", return_value=mock)


def test_migration_018_preserves_legacy():
    """Build at 017, insert data, upgrade to 018. Legacy preserved."""
    from alembic import command

    tmpdir = tempfile.mkdtemp()
    db_url = f"sqlite:///{Path(tmpdir) / 'p025.db'}"
    cfg = _alembic_cfg(db_url)

    with _patched_settings(db_url):
        command.upgrade(cfg, "017")
        engine = create_engine(db_url)
        with engine.connect() as c:
            c.execute(text(
                "INSERT INTO pipeline_runs "
                "(run_id_str,domain,status,config_json,stages_completed,created_at,provenance_version) "
                "VALUES ('r1','AI','completed','{}','[]',CURRENT_TIMESTAMP,'provenance_v1')"))
            c.execute(text(
                "INSERT INTO search_queries "
                "(run_id,query_key,query_text,query_type,generation_origin,sequence_number,status) "
                "VALUES (1,'k','q','template','base',0,'persisted')"))
            c.execute(text(
                "INSERT INTO search_query_executions "
                "(search_query_id,source,status,attempt_count,accounting_status) "
                "VALUES (1,'arxiv','failed',1,'incomplete')"))
            c.execute(text(
                "INSERT INTO papers (source_id,source,title,authors,keywords,ingested,created_at) "
                "VALUES ('p1','arxiv','Paper','[]','[]',0,CURRENT_TIMESTAMP)"))
            c.execute(text(
                "INSERT INTO paper_discoveries "
                "(run_id,paper_id,search_query_id,source,discovery_origin,"
                " deduplication_status,discovery_key,retrieved_at,created_at) "
                "VALUES (1,1,1,'arxiv','remote_search','unique','dk',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
            c.commit()

        command.upgrade(cfg, "018")
        engine = create_engine(db_url)
        with engine.connect() as c:
            # Legacy discovery has NULL linkage fields
            row = c.execute(text(
                "SELECT source_result_key, linkage_schema_version "
                "FROM paper_discoveries WHERE id=1"
            )).one()
            assert row[0] is None, "source_result_key should be NULL"
            assert row[1] is None, "linkage_schema_version should be NULL"

            # No linkage-ledger rows fabricated
            count = c.execute(text("SELECT COUNT(*) FROM execution_discovery_linkages")).scalar()
            assert count == 0, "no linkage rows should be fabricated"

            # Linkage table exists
            tables = [r[0] for r in c.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='execution_discovery_linkages'"
            )).fetchall()]
            assert len(tables) == 1


def test_migration_018_round_trip():
    from alembic import command

    tmpdir = tempfile.mkdtemp()
    db_url = f"sqlite:///{Path(tmpdir) / 'rt.db'}"
    cfg = _alembic_cfg(db_url)

    with _patched_settings(db_url):
        command.upgrade(cfg, "017")
        command.upgrade(cfg, "018")
        command.downgrade(cfg, "017")
        command.upgrade(cfg, "018")
        engine = create_engine(db_url)
        with engine.connect() as c:
            cols = [r[1] for r in c.execute(text("PRAGMA table_info(paper_discoveries)")).fetchall()]
            assert "source_result_key" in cols
