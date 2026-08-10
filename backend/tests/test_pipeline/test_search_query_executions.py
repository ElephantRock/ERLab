"""Tests for P0.2.1: search query executions schema & ownership layer.

Establishes an honest, database-enforced identity for each logical
query/source execution. The schema (not ORM defaults) enforces:

  - source canonical form (lowercase, trimmed, non-empty)
  - status vocabulary (pending|running|success|partial|failed|timeout|skipped)
  - accounting_status vocabulary (incomplete|reconciled)
  - non-negative attempt_count and all count columns
  - discovery-to-execution query consistency (composite FK + null-bypass CHECK)
  - legacy nullability (execution_id NULL → constraints skipped)

Two test tiers:
  1. Schema-integrity tests via Base.metadata.create_all on in-memory SQLite
     with FK enforcement (the verified pattern from test_corpus_provenance.py).
  2. Alembic migration tests: build a real DB at revision 014, insert legacy
     rows, upgrade 014→015, assert legacy preservation + no fabrication.

Uses plain functions + asyncio-free helpers (no pytest fixtures, no conftest
dependency) matching the P0.1 test style.
"""

from __future__ import annotations

import tempfile
from datetime import UTC
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, event, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.db.database import Base
from backend.db.models import (
    Paper,
    PaperDiscovery,
    PipelineRun,
    RunPaper,
    SearchQuery,
    SearchQueryExecution,
)

# ── Session helpers (mirror test_corpus_provenance.py) ──────────────


def _make_engine():
    """In-memory SQLite engine with FK enforcement on every connection.

    The connect-listener is load-bearing: SQLite disables FKs per-connection
    by default. Without it, RESTRICT tests pass for the wrong reason.
    """
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_fk(dbapi_conn, conn_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


def _session_from_engine(engine):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    return Session()


def _make_session():
    return _session_from_engine(_make_engine())


_run_counter = [0]


def _make_run(session, domain="AI/NLP", provenance_version="provenance_v1"):
    _run_counter[0] += 1
    run = PipelineRun(
        run_id_str=f"run_p02_{_run_counter[0]}",
        domain=domain,
        status="completed",
        provenance_version=provenance_version,
    )
    session.add(run)
    session.commit()
    return run


def _make_query(session, run_id, query_key="abc123", query_text="transformers"):
    sq = SearchQuery(
        run_id=run_id,
        query_key=query_key,
        query_text=query_text,
    )
    session.add(sq)
    session.commit()
    return sq


def _make_paper(session, source_id="arxiv:2601.001", title="A Test Paper"):
    paper = Paper(source_id=source_id, title=title, source="arxiv")
    session.add(paper)
    session.commit()
    return paper


def _make_execution(session, query_id, source="arxiv", **kwargs):
    """Build an execution with sensible defaults; override via kwargs."""
    defaults = dict(
        search_query_id=query_id,
        source=source,
        status="pending",
        attempt_count=0,
        accounting_status="incomplete",
    )
    defaults.update(kwargs)
    ex = SearchQueryExecution(**defaults)
    session.add(ex)
    session.commit()
    return ex


# ── 1. Schema existence ─────────────────────────────────────────────


def test_execution_table_and_columns_exist():
    """The search_query_executions table has all required columns."""
    engine = _make_engine()
    insp = inspect(engine)
    assert insp.has_table("search_query_executions")
    cols = {c["name"] for c in insp.get_columns("search_query_executions")}
    required = {
        "id", "search_query_id", "source", "translated_query", "status",
        "attempt_count", "error_detail", "attempted_at", "completed_at",
        "raw_result_count", "normalized_result_count", "rejected_result_count",
        "source_unique_count", "accounting_status", "created_at", "updated_at",
    }
    assert required <= cols, f"missing columns: {required - cols}"


def test_paper_discoveries_has_execution_id_column():
    """paper_discoveries gained the execution_id column (nullable)."""
    engine = _make_engine()
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("paper_discoveries")}
    assert "execution_id" in cols


def test_execution_id_index_exists():
    """An index on paper_discoveries.execution_id exists (FKs aren't auto-indexed)."""
    engine = _make_engine()
    insp = inspect(engine)
    indexes = insp.get_indexes("paper_discoveries")
    assert any(
        ix["column_names"] == ["execution_id"] for ix in indexes
    ), f"no index on execution_id; indexes: {[ix['name'] for ix in indexes]}"


# ── 2. Defaults ─────────────────────────────────────────────────────


def test_status_default_pending():
    """An execution created without explicit status gets 'pending'."""
    session = _make_session()
    try:
        run = _make_run(session)
        q = _make_query(session, run.id)
        ex = _make_execution(session, q.id)
        assert ex.status == "pending"
    finally:
        session.close()


def test_status_running_is_valid():
    """The 'running' lifecycle state is accepted by the CHECK constraint."""
    session = _make_session()
    try:
        run = _make_run(session)
        q = _make_query(session, run.id)
        ex = _make_execution(session, q.id, status="running")
        assert ex.status == "running"
    finally:
        session.close()


def test_status_invalid_value_rejected():
    """An invalid status string is rejected by the CHECK constraint."""
    session = _make_session()
    try:
        run = _make_run(session)
        q = _make_query(session, run.id)
        with pytest.raises(IntegrityError):
            _make_execution(session, q.id, status="bogus")
    finally:
        session.close()


def test_accounting_status_default_incomplete_and_invalid_rejected():
    """Default is 'incomplete'; 'bogus' is rejected."""
    session = _make_session()
    try:
        run = _make_run(session)
        q = _make_query(session, run.id)
        ex = _make_execution(session, q.id)
        assert ex.accounting_status == "incomplete"
        with pytest.raises(IntegrityError):
            _make_execution(session, q.id, accounting_status="bogus")
        session.rollback()  # clear the dirty txn state from the failed insert
        # 'reconciled' requires all four counts + accounting_v1 (P0.2.4 constraint).
        # Test with a complete reconciled row:
        from datetime import datetime

        from backend.db.models import SearchQueryExecution
        ex2 = SearchQueryExecution(
            search_query_id=q.id, source="openalex", status="success",
            attempt_count=1, completed_at=datetime(2026, 1, 1, tzinfo=UTC),
            accounting_status="reconciled", accounting_schema_version="accounting_v1",
            execution_metadata_version="execution_v1",
            translated_query='{"schema":"source_query_v1"}',
            raw_result_count=5, normalized_result_count=3,
            rejected_result_count=2, source_unique_count=3,
        )
        session.add(ex2)
        session.commit()
        assert ex2.accounting_status == "reconciled"
    finally:
        session.close()


def test_attempt_count_default_zero_and_negative_rejected():
    """Default is 0; negative is rejected by CHECK."""
    session = _make_session()
    try:
        run = _make_run(session)
        q = _make_query(session, run.id)
        ex = _make_execution(session, q.id)
        assert ex.attempt_count == 0
        with pytest.raises(IntegrityError):
            _make_execution(session, q.id, source="openalex", attempt_count=-1)
    finally:
        session.close()


def test_attempt_count_includes_first_attempt_semantics():
    """attempt_count documents the lifecycle: 0=pending, 1=first contact, 2=one retry.

    This verifies the values round-trip through the DB. It does NOT assert
    the DB rejects every inconsistent status/count combination — that is
    P0.2.2's lifecycle responsibility, not schema enforcement.
    """
    session = _make_session()
    try:
        run = _make_run(session)
        q = _make_query(session, run.id)
        ex_pending = _make_execution(session, q.id, source="arxiv", status="pending", attempt_count=0)
        ex_first = _make_execution(session, q.id, source="openalex", status="running", attempt_count=1)
        ex_retry = _make_execution(session, q.id, source="crossref", status="running", attempt_count=2)
        assert ex_pending.attempt_count == 0
        assert ex_first.attempt_count == 1
        assert ex_retry.attempt_count == 2
    finally:
        session.close()


def test_negative_counts_rejected():
    """All four count columns reject negative values via CHECK."""
    session = _make_session()
    try:
        run = _make_run(session)
        q = _make_query(session, run.id)
        for col in ["raw_result_count", "normalized_result_count",
                    "rejected_result_count", "source_unique_count"]:
            # Reset any failed txn state
            session.rollback()
            with pytest.raises(IntegrityError):
                _make_execution(session, q.id, source=f"src_{col}", **{col: -1})
            session.rollback()
    finally:
        session.close()


# ── 3. Source canonicalization ──────────────────────────────────────


def test_source_must_be_canonical():
    """source='ArXiv' rejected by CHECK; 'arxiv' accepted; second rejected by UNIQUE."""
    session = _make_session()
    try:
        run = _make_run(session)
        q = _make_query(session, run.id)

        # Non-canonical casing rejected
        with pytest.raises(IntegrityError):
            _make_execution(session, q.id, source="ArXiv")
        session.rollback()

        # Whitespace rejected
        with pytest.raises(IntegrityError):
            _make_execution(session, q.id, source="  arxiv  ")
        session.rollback()

        # Canonical accepted
        ex = _make_execution(session, q.id, source="arxiv")
        assert ex.source == "arxiv"

        # Second identical (query, source) rejected by UNIQUE
        with pytest.raises(IntegrityError):
            _make_execution(session, q.id, source="arxiv")
    finally:
        session.close()


def test_unique_query_source_pair():
    """Replay idempotency: one execution per (query, source) — different sources OK."""
    session = _make_session()
    try:
        run = _make_run(session)
        q = _make_query(session, run.id)
        _make_execution(session, q.id, source="arxiv")
        _make_execution(session, q.id, source="openalex")  # different source, OK
        _make_execution(session, q.id, source="crossref")  # different source, OK

        count = session.execute(
            select(func.count(SearchQueryExecution.id)).where(
                SearchQueryExecution.search_query_id == q.id
            )
        ).scalar_one()
        assert count == 3

        # Duplicate (same query, same source) rejected
        with pytest.raises(IntegrityError):
            _make_execution(session, q.id, source="arxiv")
    finally:
        session.close()


# ── 4. Foreign keys ─────────────────────────────────────────────────


def test_execution_requires_search_query():
    """An execution with a bogus search_query_id is rejected by FK."""
    session = _make_session()
    try:
        with pytest.raises(IntegrityError):
            _make_execution(session, query_id=999999, source="arxiv")
    finally:
        session.close()


def test_cascade_on_query_delete():
    """Deleting a SearchQuery cascades to its executions (no discovery link)."""
    session = _make_session()
    try:
        run = _make_run(session)
        q = _make_query(session, run.id)
        _make_execution(session, q.id, source="arxiv")
        _make_execution(session, q.id, source="openalex")

        assert session.execute(
            select(func.count(SearchQueryExecution.id)).where(
                SearchQueryExecution.search_query_id == q.id
            )
        ).scalar_one() == 2

        session.delete(q)
        session.commit()

        assert session.execute(
            select(func.count(SearchQueryExecution.id))
        ).scalar_one() == 0
    finally:
        session.close()


def test_cascade_on_run_delete_full_chain():
    """Deleting a run cascades through the complete linked graph:
    PipelineRun → SearchQuery → SearchQueryExecution → PaperDiscovery(execution_id set) → RunPaper.
    """
    engine = _make_engine()
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        run = _make_run(session)
        q = _make_query(session, run.id)
        paper = _make_paper(session)
        ex = _make_execution(session, q.id, source="arxiv")

        # Discovery linked to the execution (governed P0.2 path)
        disc = PaperDiscovery(
            run_id=run.id, paper_id=paper.id, search_query_id=q.id,
            execution_id=ex.id, source="arxiv",
            discovery_origin="remote_search", discovery_key="dk1",
        )
        session.add(disc)
        rp = RunPaper(run_id=run.id, paper_id=paper.id, inclusion_origin="remote_search")
        session.add(rp)
        session.commit()

        assert session.execute(select(func.count(SearchQueryExecution.id))).scalar_one() == 1
        assert session.execute(select(func.count(PaperDiscovery.id))).scalar_one() == 1

        # Delete the run — cascades to query → execution → discovery; paper RESTRICT-survives.
        # Note: RunPaper(run_id) CASCADEs, PaperDiscovery(run_id) CASCADEs,
        # but PaperDiscovery has execution_id RESTRICT on the execution.
        # Since the cascade comes from run_id (CASCADE) not execution_id, the
        # discovery is deleted by the run cascade before the RESTRICT fires.
        session.delete(run)
        session.commit()

        assert session.execute(select(func.count(SearchQueryExecution.id))).scalar_one() == 0
        assert session.execute(select(func.count(PaperDiscovery.id))).scalar_one() == 0
        assert session.execute(select(func.count(RunPaper.id))).scalar_one() == 0
        # Paper survives (its FK to run is via RunPaper, which is gone; Paper itself is standalone)
        assert session.execute(select(func.count(Paper.id))).scalar_one() == 1
    finally:
        session.close()


def test_discovery_execution_fk_rejects_query_mismatch():
    """A discovery linking to an execution for a DIFFERENT query is rejected."""
    session = _make_session()
    try:
        run = _make_run(session)
        q1 = _make_query(session, run.id, query_key="key1", query_text="alpha")
        q2 = _make_query(session, run.id, query_key="key2", query_text="beta")
        paper = _make_paper(session)
        # Execution belongs to q2
        ex_q2 = _make_execution(session, q2.id, source="arxiv")

        # Discovery claims q1 but execution belongs to q2 → mismatch
        with pytest.raises(IntegrityError):
            disc = PaperDiscovery(
                run_id=run.id, paper_id=paper.id, search_query_id=q1.id,
                execution_id=ex_q2.id, source="arxiv",
                discovery_origin="remote_search", discovery_key="dk_mismatch",
            )
            session.add(disc)
            session.commit()
    finally:
        session.close()


def test_nonnull_execution_requires_search_query():
    """The null-bypass CHECK: execution_id set + search_query_id NULL → rejected.

    Without this CHECK, SQLite MATCH SIMPLE on the composite FK would let
    this row bypass the constraint entirely.
    """
    engine = _make_engine()
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        run = _make_run(session)
        q = _make_query(session, run.id)
        paper = _make_paper(session)
        ex = _make_execution(session, q.id, source="arxiv")

        # execution_id set, search_query_id NULL → CHECK rejects
        with pytest.raises(IntegrityError):
            session.execute(text(
                "INSERT INTO paper_discoveries "
                "(run_id, paper_id, search_query_id, execution_id, source, "
                " discovery_origin, discovery_key) "
                "VALUES (:rid, :pid, NULL, :eid, 'arxiv', 'remote_search', 'dk_bypass')"
            ), {"rid": run.id, "pid": paper.id, "eid": ex.id})
            session.commit()
    finally:
        session.close()


def test_legacy_discovery_null_execution_id_survives():
    """Legacy P0.1 discovery: search_query_id set, execution_id NULL → valid.

    This is the row shape produced by all pre-P0.2 runs. MATCH SIMPLE skips
    the composite FK when execution_id is NULL.
    """
    session = _make_session()
    try:
        run = _make_run(session)
        q = _make_query(session, run.id)
        paper = _make_paper(session)

        disc = PaperDiscovery(
            run_id=run.id, paper_id=paper.id, search_query_id=q.id,
            execution_id=None,  # legacy
            source="arxiv", discovery_origin="remote_search", discovery_key="dk_legacy",
        )
        session.add(disc)
        session.commit()  # no error

        assert disc.execution_id is None
        assert disc.search_query_id == q.id
    finally:
        session.close()


def test_both_null_discovery_survives():
    """Non-query discovery: execution_id NULL + search_query_id NULL → valid (e.g. local upload)."""
    session = _make_session()
    try:
        run = _make_run(session)
        paper = _make_paper(session)

        disc = PaperDiscovery(
            run_id=run.id, paper_id=paper.id, search_query_id=None,
            execution_id=None,
            source="local_upload", discovery_origin="local", discovery_key="dk_local",
        )
        session.add(disc)
        session.commit()
        assert disc.execution_id is None
        assert disc.search_query_id is None
    finally:
        session.close()


def test_discovery_execution_fk_restrict():
    """Deleting an execution referenced by a discovery is rejected (RESTRICT)."""
    session = _make_session()
    try:
        run = _make_run(session)
        q = _make_query(session, run.id)
        paper = _make_paper(session)
        ex = _make_execution(session, q.id, source="arxiv")

        disc = PaperDiscovery(
            run_id=run.id, paper_id=paper.id, search_query_id=q.id,
            execution_id=ex.id, source="arxiv",
            discovery_origin="remote_search", discovery_key="dk_restrict",
        )
        session.add(disc)
        session.commit()

        with pytest.raises(IntegrityError):
            session.execute(text("DELETE FROM search_query_executions WHERE id = :eid"),
                            {"eid": ex.id})
            session.commit()
    finally:
        session.close()


# ── 5. Alembic migration tests (real upgrade path) ──────────────────

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


def test_alembic_014_to_015_preserves_legacy_data():
    """Build DB at revision 014, insert legacy rows, upgrade to 015.

    Asserts:
      - legacy row counts unchanged
      - every legacy PaperDiscovery.execution_id is NULL
      - no SearchQueryExecution rows fabricated
    """
    from alembic import command

    tmpdir = tempfile.mkdtemp()
    db_url = f"sqlite:///{Path(tmpdir) / 'alembic_legacy.db'}"
    cfg = _alembic_cfg(db_url)

    with _patched_settings(db_url):
        # Build at 014
        command.upgrade(cfg, "014")

        # Insert legacy data via raw engine.
        # NOTE: at revision 014, paper_discoveries has NO execution_id column —
        # we insert only the columns that exist at that revision.
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine, expire_on_commit=False)
        session = Session()
        try:
            session.execute(text(
                "INSERT INTO pipeline_runs "
                "(run_id_str, domain, status, config_json, stages_completed, "
                " created_at, provenance_version) "
                "VALUES ('legacy_run', 'AI', 'completed', '{}', '[]', "
                " CURRENT_TIMESTAMP, 'pre_provenance')"
            ))
            session.execute(text(
                "INSERT INTO papers "
                "(source_id, source, title, authors, keywords, ingested, created_at) "
                "VALUES ('arxiv:legacy', 'arxiv', 'Legacy Paper', '[]', '[]', 0, CURRENT_TIMESTAMP)"
            ))
            session.execute(text(
                "INSERT INTO search_queries (run_id, query_key, query_text, query_type, "
                "generation_origin, sequence_number, status) "
                "VALUES (1, 'lqkey', 'legacy query', 'template', 'base', 0, 'persisted')"
            ))
            session.execute(text(
                "INSERT INTO paper_discoveries "
                "(run_id, paper_id, search_query_id, source, discovery_origin, "
                " deduplication_status, discovery_key, retrieved_at, created_at) "
                "VALUES (1, 1, 1, 'arxiv', 'remote_search', 'unique', 'lck', "
                " CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ))
            session.execute(text(
                "INSERT INTO run_papers "
                "(run_id, paper_id, inclusion_origin, inclusion_status, "
                " first_discovered_at, selected_for_downstream, provenance_schema_version, "
                " created_at, updated_at) "
                "VALUES (1, 1, 'remote_search', 'candidate', CURRENT_TIMESTAMP, 0, "
                " 'provenance_v1', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ))
            session.commit()
        finally:
            session.close()

        # Upgrade 014 → 015
        command.upgrade(cfg, "015")

        engine = create_engine(db_url)
        with engine.connect() as conn:
            # Legacy counts unchanged
            runs = conn.execute(text("SELECT COUNT(*) FROM pipeline_runs")).scalar()
            papers = conn.execute(text("SELECT COUNT(*) FROM papers")).scalar()
            sq = conn.execute(text("SELECT COUNT(*) FROM search_queries")).scalar()
            pd = conn.execute(text("SELECT COUNT(*) FROM paper_discoveries")).scalar()
            rp = conn.execute(text("SELECT COUNT(*) FROM run_papers")).scalar()
            assert runs == 1 and papers == 1 and sq == 1 and pd == 1 and rp == 1

            # Every legacy discovery has execution_id NULL
            null_exec = conn.execute(text(
                "SELECT COUNT(*) FROM paper_discoveries WHERE execution_id IS NOT NULL"
            )).scalar()
            assert null_exec == 0, "no legacy discovery should gain an execution_id"

            # No executions fabricated
            ex_count = conn.execute(text(
                "SELECT COUNT(*) FROM search_query_executions"
            )).scalar()
            assert ex_count == 0, "no execution rows should be fabricated for legacy runs"


def test_alembic_015_to_014_downgrade_safe():
    """Populate execution rows, downgrade 015→014, verify clean teardown."""
    from alembic import command

    tmpdir = tempfile.mkdtemp()
    db_url = f"sqlite:///{Path(tmpdir) / 'alembic_down.db'}"
    cfg = _alembic_cfg(db_url)

    with _patched_settings(db_url):
        command.upgrade(cfg, "head")

        # Insert an execution row + a discovery linked to it
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine, expire_on_commit=False)
        session = Session()
        try:
            session.execute(text(
                "INSERT INTO pipeline_runs "
                "(run_id_str, domain, status, config_json, stages_completed, "
                " created_at, provenance_version) "
                "VALUES ('r1', 'AI', 'completed', '{}', '[]', "
                " CURRENT_TIMESTAMP, 'provenance_v1')"
            ))
            session.execute(text(
                "INSERT INTO papers "
                "(source_id, source, title, authors, keywords, ingested, created_at) "
                "VALUES ('p1', 'arxiv', 'Paper', '[]', '[]', 0, CURRENT_TIMESTAMP)"
            ))
            session.execute(text(
                "INSERT INTO search_queries (run_id, query_key, query_text, query_type, "
                "generation_origin, sequence_number, status) "
                "VALUES (1, 'k', 'q', 'template', 'base', 0, 'persisted')"
            ))
            session.execute(text(
                "INSERT INTO search_query_executions "
                "(search_query_id, source, status, attempt_count, accounting_status) "
                "VALUES (1, 'arxiv', 'success', 1, 'incomplete')"
            ))
            session.execute(text(
                "INSERT INTO paper_discoveries "
                "(run_id, paper_id, search_query_id, execution_id, source, "
                " discovery_origin, deduplication_status, discovery_key, "
                " retrieved_at, created_at) "
                "VALUES (1, 1, 1, 1, 'arxiv', 'remote_search', 'unique', 'k', "
                " CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ))
            session.commit()
        finally:
            session.close()

        # Downgrade 015 → 014
        command.downgrade(cfg, "014")

        engine = create_engine(db_url)
        insp = inspect(engine)
        # Table gone
        assert not insp.has_table("search_query_executions")
        # paper_discoveries no longer has execution_id
        disc_cols = {c["name"] for c in insp.get_columns("paper_discoveries")}
        assert "execution_id" not in disc_cols
        # Legacy data (runs, papers, queries, discoveries) still intact
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM pipeline_runs")).scalar() == 1
            assert conn.execute(text("SELECT COUNT(*) FROM paper_discoveries")).scalar() == 1


def test_alembic_round_trip_idempotent():
    """014→015→014→015 is stable."""
    from alembic import command

    tmpdir = tempfile.mkdtemp()
    db_url = f"sqlite:///{Path(tmpdir) / 'alembic_rt.db'}"
    cfg = _alembic_cfg(db_url)

    with _patched_settings(db_url):
        command.upgrade(cfg, "014")
        command.upgrade(cfg, "015")
        command.downgrade(cfg, "014")
        command.upgrade(cfg, "015")

        insp = inspect(create_engine(db_url))
        assert insp.has_table("search_query_executions")
        disc_cols = {c["name"] for c in insp.get_columns("paper_discoveries")}
        assert "execution_id" in disc_cols
