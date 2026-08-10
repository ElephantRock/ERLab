"""Tests for P0.2.6: run-level search reconciliation.

Proves:
  - Migration 019 preserves existing rows (no fabricated scopes/reconciliations)
  - Execution scope registration (canonical normalization, replay, drift)
  - Reconciliation snapshot building (all set equations)
  - Execution posture derivation (healthy, degraded, no_usable_sources)
  - Reconciled row passes all CHECK constraints
  - Blocked/failed states handled correctly
  - Replay/drift protection
  - Zero-result run reconciles successfully
"""

from __future__ import annotations

import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.db.database import Base
from backend.db.models import (
    ExecutionDiscoveryLinkage,
    PaperDiscovery,
    PipelineRun,
    RunPaper,
    RunSearchReconciliation,
    SearchQuery,
    SearchQueryExecution,
    SearchQueryExecutionScope,
)
from backend.db.models import (
    Paper as DBPaper,
)
from backend.pipeline.literature.run_reconciliation import (
    ExecutionScopeDriftError,
    canonical_source_json,
    canonical_source_set,
    ensure_execution_scope,
    ensure_pending_reconciliation,
    reconcile_run_search,
    source_set_hash,
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


def _make_run(engine):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        _run_counter[0] += 1
        run = PipelineRun(
            run_id_str=f"r_p026_{_run_counter[0]}", domain="AI",
            status="completed", config_json="{}", stages_completed="[]",
            provenance_version="provenance_v1",
        )
        session.add(run); session.commit()
        return run.id
    finally:
        session.close()


def _make_query(engine, run_id, query_key="qk"):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        sq = SearchQuery(run_id=run_id, query_key=query_key, query_text="test")
        session.add(sq); session.commit()
        return sq.id
    finally:
        session.close()


def _make_completed_execution(
    engine, sq_id, source, status="success", source_unique=1,
    exec_id_override=None,
):
    """Create a terminal reconciled execution with linked discoveries."""
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        now = datetime.now(UTC)
        ex = SearchQueryExecution(
            search_query_id=sq_id, source=source, status=status,
            attempt_count=1, completed_at=now,
            translated_query='{"schema":"source_query_v1"}',
            execution_metadata_version="execution_v1",
            accounting_status="reconciled", accounting_schema_version="accounting_v1",
            raw_result_count=source_unique, normalized_result_count=source_unique,
            rejected_result_count=0, source_unique_count=source_unique,
        )
        session.add(ex); session.flush()
        exec_id = ex.id

        # Linkage ledger: linked
        ledger = ExecutionDiscoveryLinkage(
            execution_id=exec_id,
            linkage_schema_version="linkage_v1",
            status="linked",
            expected_discovery_count=source_unique,
            linked_discovery_count=source_unique,
            completed_at=now,
        )
        session.add(ledger)
        session.commit()
        return exec_id
    finally:
        session.close()


def _make_paper(engine, source_id, title="Paper"):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        paper = DBPaper(source_id=source_id, source="arxiv", title=title,
                        authors="[]", keywords="[]", ingested=0)
        session.add(paper); session.commit()
        return paper.id
    finally:
        session.close()


def _make_governed_discovery(engine, run_id, paper_id, sq_id, exec_id, source, srk):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        disc = PaperDiscovery(
            run_id=run_id, paper_id=paper_id, search_query_id=sq_id,
            execution_id=exec_id, source=source, source_result_key=srk,
            linkage_schema_version="linkage_v1",
            discovery_origin="remote_search",
            discovery_key=f"dk_{srk[:8]}",
        )
        session.add(disc); session.commit()
    finally:
        session.close()


def _make_run_paper(engine, run_id, paper_id):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        rp = RunPaper(run_id=run_id, paper_id=paper_id, inclusion_origin="remote_search")
        session.add(rp); session.commit()
    finally:
        session.close()


# ── 1. Scope registration ────────────────────────────────────────────


def test_canonical_source_set_normalizes():
    assert canonical_source_set(["arxiv", "ARXIV", " OpenAlex ", "openalex"]) == ["arxiv", "openalex"]


def test_canonical_source_json_sorted():
    j = canonical_source_json(canonical_source_set(["openalex", "arxiv"]))
    assert j == '["arxiv","openalex"]'


def test_source_set_hash_deterministic():
    h1 = source_set_hash(canonical_source_set(["arxiv", "openalex"]))
    h2 = source_set_hash(canonical_source_set(["openalex", "arxiv"]))
    assert h1 == h2
    assert len(h1) == 64


def test_ensure_execution_scope_creates():
    engine = _make_engine()
    run_id = _make_run(engine)
    sq_id = _make_query(engine, run_id)
    ensure_execution_scope(engine, sq_id, ["arxiv", "openalex"])

    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        scope = s.get(SearchQueryExecutionScope, sq_id)
        assert scope is not None
        assert scope.intended_source_count == 2
        assert "arxiv" in scope.intended_sources_json
    finally:
        s.close()


def test_ensure_execution_scope_replay_noop():
    engine = _make_engine()
    run_id = _make_run(engine)
    sq_id = _make_query(engine, run_id)
    ensure_execution_scope(engine, sq_id, ["arxiv", "openalex"])
    # Same set → no-op
    ensure_execution_scope(engine, sq_id, ["openalex", "arxiv"])

    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        count = s.execute(text(
            "SELECT COUNT(*) FROM search_query_execution_scopes WHERE search_query_id = :sqid"
        ), {"sqid": sq_id}).scalar()
        assert count == 1
    finally:
        s.close()


def test_ensure_execution_scope_drift_rejected():
    engine = _make_engine()
    run_id = _make_run(engine)
    sq_id = _make_query(engine, run_id)
    ensure_execution_scope(engine, sq_id, ["arxiv", "openalex"])

    with pytest.raises(ExecutionScopeDriftError):
        ensure_execution_scope(engine, sq_id, ["arxiv", "pubmed"])


# ── 2. Reconciliation snapshot ───────────────────────────────────────


def test_zero_result_run_reconciles():
    """A run where all executions succeed with zero results reconciles."""
    engine = _make_engine()
    run_id = _make_run(engine)
    sq_id = _make_query(engine, run_id)

    # Scope: one intended source
    ensure_execution_scope(engine, sq_id, ["arxiv"])

    # Execution: success with 0 unique results
    _make_completed_execution(engine, sq_id, "arxiv", status="success", source_unique=0)

    status = reconcile_run_search(engine, run_id)
    assert status == "reconciled"

    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        rsr = s.get(RunSearchReconciliation, run_id)
        assert rsr.status == "reconciled"
        assert rsr.execution_posture == "healthy"
        assert rsr.run_paper_count == 0
        assert rsr.source_unique_result_count == 0
        assert rsr.linked_discovery_count == 0
        assert rsr.input_fingerprint is not None
    finally:
        s.close()


def test_successful_run_with_results_reconciles():
    """A run with 1 query, 1 source, 2 unique results → 2 papers → 2 RunPaper."""
    engine = _make_engine()
    run_id = _make_run(engine)
    sq_id = _make_query(engine, run_id)

    ensure_execution_scope(engine, sq_id, ["arxiv"])
    exec_id = _make_completed_execution(engine, sq_id, "arxiv", source_unique=2)

    # Create 2 papers + discoveries + RunPaper
    for i in range(2):
        pid = _make_paper(engine, f"p{i}", title=f"Paper {i}")
        _make_governed_discovery(engine, run_id, pid, sq_id, exec_id, "arxiv", f"srk_{i}")
        _make_run_paper(engine, run_id, pid)

    status = reconcile_run_search(engine, run_id)
    assert status == "reconciled"

    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        rsr = s.get(RunSearchReconciliation, run_id)
        assert rsr.run_paper_count == 2
        assert rsr.remote_canonical_paper_count == 2
        assert rsr.source_unique_result_count == 2
        assert rsr.linked_discovery_count == 2
        assert rsr.unexplained_membership_count == 0
        assert rsr.unowned_discovery_paper_count == 0
    finally:
        s.close()


def test_degraded_posture_with_failed_execution():
    """One success + one failed → degraded posture."""
    engine = _make_engine()
    run_id = _make_run(engine)
    sq_id = _make_query(engine, run_id)

    ensure_execution_scope(engine, sq_id, ["arxiv", "openalex"])

    # arxiv: success with 1 result
    exec1 = _make_completed_execution(engine, sq_id, "arxiv", source_unique=1)

    # openalex: failed with 0 results
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        now = datetime.now(UTC)
        ex2 = SearchQueryExecution(
            search_query_id=sq_id, source="openalex", status="failed",
            attempt_count=1, completed_at=now,
            translated_query='{"schema":"source_query_v1"}',
            execution_metadata_version="execution_v1",
            failure_category="transport", failure_code="connection_error",
            error_detail="connection refused",
            accounting_status="incomplete",
        )
        session.add(ex2); session.flush()
        ledger2 = ExecutionDiscoveryLinkage(
            execution_id=ex2.id, linkage_schema_version="linkage_v1",
            status="not_applicable", completed_at=now,
        )
        session.add(ledger2)
        session.commit()
    finally:
        session.close()

    # Create the 1 paper/discovery/RunPaper for arxiv
    pid = _make_paper(engine, "p1")
    _make_governed_discovery(engine, run_id, pid, sq_id, exec1, "arxiv", "srk1")
    _make_run_paper(engine, run_id, pid)

    status = reconcile_run_search(engine, run_id)
    assert status == "reconciled"

    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        rsr = s.get(RunSearchReconciliation, run_id)
        assert rsr.execution_posture == "degraded"
        assert rsr.success_execution_count == 1
        assert rsr.failed_execution_count == 1
    finally:
        s.close()


def test_no_usable_sources_posture():
    """All failed → no_usable_sources posture, still reconciled."""
    engine = _make_engine()
    run_id = _make_run(engine)
    sq_id = _make_query(engine, run_id)

    ensure_execution_scope(engine, sq_id, ["arxiv"])

    # Only failed execution
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        now = datetime.now(UTC)
        ex = SearchQueryExecution(
            search_query_id=sq_id, source="arxiv", status="failed",
            attempt_count=1, completed_at=now,
            translated_query='{"schema":"source_query_v1"}',
            error_detail="connection refused",
            failure_category="transport", failure_code="connection_error",
            execution_metadata_version="execution_v1",
            accounting_status="incomplete",
        )
        session.add(ex); session.flush()
        session.add(ExecutionDiscoveryLinkage(
            execution_id=ex.id, linkage_schema_version="linkage_v1",
            status="not_applicable", completed_at=now,
        ))
        session.commit()
    finally:
        session.close()

    status = reconcile_run_search(engine, run_id)
    assert status == "reconciled"

    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        rsr = s.get(RunSearchReconciliation, run_id)
        assert rsr.execution_posture == "no_usable_sources"
        assert rsr.run_paper_count == 0
    finally:
        s.close()


def test_replay_after_reconciled_is_noop():
    """Re-reconciling a reconciled run with the same fingerprint is a no-op."""
    engine = _make_engine()
    run_id = _make_run(engine)
    sq_id = _make_query(engine, run_id)
    ensure_execution_scope(engine, sq_id, ["arxiv"])
    _make_completed_execution(engine, sq_id, "arxiv", source_unique=0)

    status1 = reconcile_run_search(engine, run_id)
    assert status1 == "reconciled"

    Session = sessionmaker(bind=engine)
    s1 = Session()
    rsr1 = s1.get(RunSearchReconciliation, run_id)
    fp1 = rsr1.input_fingerprint
    completed1 = rsr1.completed_at
    s1.close()

    status2 = reconcile_run_search(engine, run_id)
    assert status2 == "reconciled"

    s2 = Session()
    rsr2 = s2.get(RunSearchReconciliation, run_id)
    assert rsr2.input_fingerprint == fp1
    assert rsr2.completed_at == completed1  # unchanged
    s2.close()


def test_ensure_pending_reconciliation_creates():
    engine = _make_engine()
    run_id = _make_run(engine)
    ensure_pending_reconciliation(engine, run_id)

    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        rsr = s.get(RunSearchReconciliation, run_id)
        assert rsr is not None
        assert rsr.status == "pending"
    finally:
        s.close()


# ── 3. DB constraint tests ───────────────────────────────────────────


def test_reconciled_row_requires_all_counts():
    """A reconciled row missing counts is rejected."""
    from sqlalchemy.exc import IntegrityError as SAIntegrityError

    engine = _make_engine()
    run_id = _make_run(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        with pytest.raises(SAIntegrityError):
            s.execute(text(
                "INSERT INTO run_search_reconciliations "
                "(run_id, reconciliation_schema_version, status, reconciliation_attempt_count) "
                "VALUES (:rid, 'run_reconciliation_v1', 'reconciled', 0)"
            ), {"rid": run_id})
            s.commit()
    finally:
        s.close()


def test_failed_requires_issue_code():
    from sqlalchemy.exc import IntegrityError as SAIntegrityError

    engine = _make_engine()
    run_id = _make_run(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        with pytest.raises(SAIntegrityError):
            s.execute(text(
                "INSERT INTO run_search_reconciliations "
                "(run_id, reconciliation_schema_version, status, reconciliation_attempt_count, completed_at) "
                "VALUES (:rid, 'run_reconciliation_v1', 'failed', 0, CURRENT_TIMESTAMP)"
            ), {"rid": run_id})
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


def test_migration_019_preserves_legacy():
    from alembic import command

    tmpdir = tempfile.mkdtemp()
    db_url = f"sqlite:///{Path(tmpdir) / 'p026.db'}"
    cfg = _alembic_cfg(db_url)

    with _patched_settings(db_url):
        command.upgrade(cfg, "018")
        engine = create_engine(db_url)
        with engine.connect() as c:
            c.execute(text(
                "INSERT INTO pipeline_runs "
                "(run_id_str,domain,status,config_json,stages_completed,created_at,provenance_version) "
                "VALUES ('r1','AI','completed','{}','[]',CURRENT_TIMESTAMP,'provenance_v1')"))
            c.commit()

        command.upgrade(cfg, "019")
        engine = create_engine(db_url)
        with engine.connect() as c:
            # No scopes or reconciliations fabricated
            s = c.execute(text("SELECT COUNT(*) FROM search_query_execution_scopes")).scalar()
            r = c.execute(text("SELECT COUNT(*) FROM run_search_reconciliations")).scalar()
            assert s == 0 and r == 0, "no fabrications"


def test_migration_019_round_trip():
    from alembic import command

    tmpdir = tempfile.mkdtemp()
    db_url = f"sqlite:///{Path(tmpdir) / 'rt.db'}"
    cfg = _alembic_cfg(db_url)

    with _patched_settings(db_url):
        command.upgrade(cfg, "018")
        command.upgrade(cfg, "019")
        command.downgrade(cfg, "018")
        command.upgrade(cfg, "019")
        insp = inspect(create_engine(db_url))
        assert insp.has_table("run_search_reconciliations")
        assert insp.has_table("search_query_execution_scopes")
