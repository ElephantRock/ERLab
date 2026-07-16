"""Tests for P0.2.4: execution-local result accounting.

Proves:
  - SourceResultAccounting validation (bool rejection, equation, dedup)
  - reconcile_source_results helper (exact dedup, first-seen order, fuzzy not merged)
  - Recorder persists accounting atomically with terminal state
  - Missing/invalid accounting → adapter_contract failure
  - DB reconciliation constraints enforced
  - Migration 017 legacy preservation + round-trip
  - Count columns and accounting_status flow correctly
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError as SAIntegrityError
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

import backend.db.models  # ensure models loaded
from backend.db.database import Base
from backend.db.models import PipelineRun, SearchQuery, SearchQueryExecution
from backend.pipeline.literature.contracts import (
    SourceQueryPlan,
    SourceResultAccounting,
    SourceSearchOutcome,
    canonical_plan_json,
    validate_accounting,
)
from backend.pipeline.literature.execution_recorder import ExecutionRecorder
from backend.pipeline.literature.models import Paper as SPaper, SearchResult
from backend.pipeline.literature.result_accounting import (
    normalize_doi,
    reconcile_source_results,
    title_hash,
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


def _setup(engine, source="arxiv"):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        _run_counter[0] += 1
        run = PipelineRun(
            run_id_str=f"r_p024_{_run_counter[0]}", domain="AI",
            status="completed", config_json="{}", stages_completed="[]",
            provenance_version="provenance_v1",
        )
        session.add(run); session.commit()
        sq = SearchQuery(run_id=run.id, query_key="qk", query_text="test")
        session.add(sq); session.commit()
        ex = SearchQueryExecution(
            search_query_id=sq.id, source=source,
            status="pending", attempt_count=0,
        )
        session.add(ex); session.commit()
        return ex.id
    finally:
        session.close()


def _fake_plan():
    return SourceQueryPlan(
        source="arxiv", schema_version="source_query_v1",
        translated_query=canonical_plan_json("arxiv", {"query": "test"}),
        request_parameters={"query": "test"},
    )


def _sr(title, source_id=None, doi=None):
    """Build a SearchResult for testing."""
    p = SPaper(id=source_id or title, title=title, source="arxiv", doi=doi)
    return SearchResult(paper=p, source="arxiv")


class _AcctAdapter:
    """Adapter that returns given results with proper accounting."""
    source_name = "arxiv"
    def __init__(self, results):
        self._results = results
        self.call_count = 0
    def build_query_plan(self, query, limit=20, year_from=None, year_to=None):
        return _fake_plan()
    async def execute_query_plan(self, plan, *, attempt_observer=None):
        self.call_count += 1
        if attempt_observer:
            await attempt_observer.attempt_started()
        unique, acct = reconcile_source_results(
            raw_result_count=len(self._results),
            normalized_results=self._results,
            rejected_result_count=0,
        )
        return SourceSearchOutcome(
            results=unique, status="success", attempt_count=1, accounting=acct,
        )


# ── 1. SourceResultAccounting validation ─────────────────────────────


def test_valid_nonzero_accounting_accepted():
    acct = SourceResultAccounting(
        schema_version="accounting_v1",
        raw_result_count=10, normalized_result_count=8,
        rejected_result_count=2, source_unique_count=5,
    )
    results = [_sr(f"Paper {i}") for i in range(5)]
    validate_accounting(acct, results)  # no error


def test_valid_zero_accounting_accepted():
    acct = SourceResultAccounting(
        schema_version="accounting_v1",
        raw_result_count=0, normalized_result_count=0,
        rejected_result_count=0, source_unique_count=0,
    )
    validate_accounting(acct, [])  # no error


def test_bool_count_rejected():
    acct = SourceResultAccounting(
        schema_version="accounting_v1",
        raw_result_count=True, normalized_result_count=0,
        rejected_result_count=0, source_unique_count=0,
    )
    with pytest.raises(ValueError, match="must be int, not bool"):
        validate_accounting(acct, [])


def test_negative_count_rejected():
    acct = SourceResultAccounting(
        schema_version="accounting_v1",
        raw_result_count=-1, normalized_result_count=0,
        rejected_result_count=0, source_unique_count=0,
    )
    with pytest.raises(ValueError, match="must be >= 0"):
        validate_accounting(acct, [])


def test_raw_equation_violation_rejected():
    acct = SourceResultAccounting(
        schema_version="accounting_v1",
        raw_result_count=10, normalized_result_count=5,
        rejected_result_count=3, source_unique_count=5,
    )
    results = [_sr(f"P{i}") for i in range(5)]
    with pytest.raises(ValueError, match="equation violated"):
        validate_accounting(acct, results)


def test_source_unique_greater_than_normalized_rejected():
    acct = SourceResultAccounting(
        schema_version="accounting_v1",
        raw_result_count=5, normalized_result_count=3,
        rejected_result_count=2, source_unique_count=4,  # > normalized!
    )
    with pytest.raises(ValueError, match="source_unique.* > normalized"):
        validate_accounting(acct, [])


def test_len_results_mismatch_rejected():
    acct = SourceResultAccounting(
        schema_version="accounting_v1",
        raw_result_count=3, normalized_result_count=3,
        rejected_result_count=0, source_unique_count=3,
    )
    results = [_sr("P1"), _sr("P2")]  # only 2, not 3
    with pytest.raises(ValueError, match="len.*!= source_unique"):
        validate_accounting(acct, results)


def test_schema_version_mismatch_rejected():
    acct = SourceResultAccounting(
        schema_version="bogus_v2",
        raw_result_count=0, normalized_result_count=0,
        rejected_result_count=0, source_unique_count=0,
    )
    with pytest.raises(ValueError, match="schema_version"):
        validate_accounting(acct, [])


# ── 2. reconcile_source_results ──────────────────────────────────────


def test_exact_duplicates_removed():
    """Two identical papers (same DOI) → 1 source-unique."""
    results = [
        _sr("Paper A", doi="10.1234/a"),
        _sr("Paper A Different Source", doi="10.1234/a"),  # same DOI, dup
    ]
    unique, acct = reconcile_source_results(
        raw_result_count=2, normalized_results=results, rejected_result_count=0,
    )
    assert len(unique) == 1
    assert acct.source_unique_count == 1
    assert acct.within_execution_duplicates_removed == 1


def test_first_seen_order_preserved():
    """First occurrence wins; order preserved."""
    results = [
        _sr("First", doi="10.1/x"),
        _sr("Second", doi="10.2/y"),
        _sr("First Dup", doi="10.1/x"),  # dup of First
        _sr("Third", doi="10.3/z"),
    ]
    unique, _ = reconcile_source_results(
        raw_result_count=4, normalized_results=results, rejected_result_count=0,
    )
    assert [r.paper.doi for r in unique] == ["10.1/x", "10.2/y", "10.3/z"]


def test_fuzzy_similar_titles_not_merged():
    """Near-duplicate titles (not exact) are NOT merged."""
    results = [
        _sr("Attention Is All You Need"),
        _sr("Attention is All You Need"),  # different capitalization — but NO DOI
    ]
    # These have different title hashes because... actually casefold would match.
    # Let's use genuinely different strings that are similar but not identical.
    results = [
        _sr("Deep Learning for NLP", source_id="id1"),
        _sr("Deep Learning for Natural Language Processing", source_id="id2"),
    ]
    unique, acct = reconcile_source_results(
        raw_result_count=2, normalized_results=results, rejected_result_count=0,
    )
    assert len(unique) == 2  # NOT merged — different IDs


def test_doi_normalization_deduplicates():
    """Equivalent DOI forms are deduplicated."""
    results = [
        _sr("Paper", doi="https://doi.org/10.1234/abc"),
        _sr("Paper Dup", doi="doi:10.1234/ABC"),  # same DOI, different case/prefix
    ]
    unique, acct = reconcile_source_results(
        raw_result_count=2, normalized_results=results, rejected_result_count=0,
    )
    assert len(unique) == 1


def test_reconcile_with_rejections():
    """3 raw, 2 normalized, 1 rejected → 2/2/1/2 (assuming unique)."""
    results = [_sr("A"), _sr("B")]
    unique, acct = reconcile_source_results(
        raw_result_count=3, normalized_results=results, rejected_result_count=1,
    )
    assert acct.raw_result_count == 3
    assert acct.normalized_result_count == 2
    assert acct.rejected_result_count == 1
    assert acct.source_unique_count == 2


# ── 3. Recorder accounting behavior ──────────────────────────────────


def test_success_persists_all_counts_atomically():
    engine = _make_engine()
    exec_id = _setup(engine)
    adapter = _AcctAdapter([_sr("P1"), _sr("P2"), _sr("P3")])
    recorder = ExecutionRecorder(engine)

    asyncio.run(recorder.run_execution(exec_id, "arxiv", adapter, "test"))

    s = sessionmaker(bind=engine)()
    try:
        row = s.get(SearchQueryExecution, exec_id)
        assert row.status == "success"
        assert row.raw_result_count == 3
        assert row.normalized_result_count == 3
        assert row.rejected_result_count == 0
        assert row.source_unique_count == 3
        assert row.accounting_status == "reconciled"
        assert row.accounting_schema_version == "accounting_v1"
    finally:
        s.close()


def test_zero_result_success_reconciled():
    """Genuine zero-result search: 0/0/0/0 reconciled."""
    engine = _make_engine()
    exec_id = _setup(engine)
    adapter = _AcctAdapter([])
    recorder = ExecutionRecorder(engine)

    asyncio.run(recorder.run_execution(exec_id, "arxiv", adapter, "test"))

    s = sessionmaker(bind=engine)()
    try:
        row = s.get(SearchQueryExecution, exec_id)
        assert row.status == "success"
        assert row.raw_result_count == 0
        assert row.accounting_status == "reconciled"
    finally:
        s.close()


def test_success_without_accounting_becomes_contract_failure():
    engine = _make_engine()
    exec_id = _setup(engine)

    class _NoAcctAdapter:
        source_name = "arxiv"
        def build_query_plan(self, query, limit=20, year_from=None, year_to=None):
            return _fake_plan()
        async def execute_query_plan(self, plan, *, attempt_observer=None):
            if attempt_observer:
                await attempt_observer.attempt_started()
            return SourceSearchOutcome(results=[], status="success", attempt_count=1)

    recorder = ExecutionRecorder(engine)
    with pytest.raises(ValueError, match="missing accounting"):
        asyncio.run(recorder.run_execution(exec_id, "arxiv", _NoAcctAdapter(), "test"))

    s = sessionmaker(bind=engine)()
    try:
        row = s.get(SearchQueryExecution, exec_id)
        assert row.status == "failed"
        assert row.failure_code == "accounting_missing"
        assert row.accounting_status == "incomplete"
        assert row.raw_result_count is None
    finally:
        s.close()


def test_terminal_replay_leaves_accounting_unchanged():
    engine = _make_engine()
    exec_id = _setup(engine)
    adapter = _AcctAdapter([_sr("P1")])
    recorder = ExecutionRecorder(engine)

    asyncio.run(recorder.run_execution(exec_id, "arxiv", adapter, "test"))
    # Replay
    asyncio.run(recorder.run_execution(exec_id, "arxiv", adapter, "test"))

    s = sessionmaker(bind=engine)()
    try:
        row = s.get(SearchQueryExecution, exec_id)
        assert row.raw_result_count == 1
        assert row.accounting_status == "reconciled"
    finally:
        s.close()


def test_timeout_remains_incomplete():
    engine = _make_engine()
    exec_id = _setup(engine)

    class _TimeoutAdapter:
        source_name = "arxiv"
        def build_query_plan(self, query, limit=20, year_from=None, year_to=None):
            return _fake_plan()
        async def execute_query_plan(self, plan, *, attempt_observer=None):
            if attempt_observer:
                await attempt_observer.attempt_started()
            await asyncio.sleep(10)

    recorder = ExecutionRecorder(engine)
    outcome = asyncio.run(
        recorder.run_execution(exec_id, "arxiv", _TimeoutAdapter(), "test", timeout_seconds=0.1)
    )

    s = sessionmaker(bind=engine)()
    try:
        row = s.get(SearchQueryExecution, exec_id)
        assert row.status == "timeout"
        assert row.accounting_status == "incomplete"
        assert row.raw_result_count is None
        assert row.accounting_schema_version is None
    finally:
        s.close()


# ── 4. Database constraint tests ─────────────────────────────────────


def test_reconciled_row_requires_all_counts():
    """A reconciled row with missing counts is rejected."""
    engine = _make_engine()
    s = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        _run_counter[0] += 1
        run = PipelineRun(run_id_str=f"r_{_run_counter[0]}", domain="AI",
                          status="completed", config_json="{}", stages_completed="[]",
                          provenance_version="provenance_v1")
        s.add(run); s.commit()
        sq = SearchQuery(run_id=run.id, query_key="qk", query_text="q")
        s.add(sq); s.commit()

        with pytest.raises(SAIntegrityError):
            s.execute(text(
                "INSERT INTO search_query_executions "
                "(search_query_id, source, status, attempt_count, accounting_status, "
                " accounting_schema_version, raw_result_count, completed_at) "
                "VALUES (:sqid, 'arxiv', 'success', 1, 'reconciled', 'accounting_v1', 5, "
                " CURRENT_TIMESTAMP)"
            ), {"sqid": sq.id})
            s.commit()
    finally:
        s.close()


def test_reconciled_row_requires_equation():
    """raw != normalized + rejected is rejected."""
    engine = _make_engine()
    s = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        _run_counter[0] += 1
        run = PipelineRun(run_id_str=f"r_{_run_counter[0]}", domain="AI",
                          status="completed", config_json="{}", stages_completed="[]",
                          provenance_version="provenance_v1")
        s.add(run); s.commit()
        sq = SearchQuery(run_id=run.id, query_key="qk", query_text="q")
        s.add(sq); s.commit()

        with pytest.raises(SAIntegrityError):
            s.execute(text(
                "INSERT INTO search_query_executions "
                "(search_query_id, source, status, attempt_count, accounting_status, "
                " accounting_schema_version, raw_result_count, normalized_result_count, "
                " rejected_result_count, source_unique_count, completed_at) "
                "VALUES (:sqid, 'arxiv', 'success', 1, 'reconciled', 'accounting_v1', "
                " 10, 5, 2, 5, CURRENT_TIMESTAMP)"  # 10 != 5 + 2
            ), {"sqid": sq.id})
            s.commit()
    finally:
        s.close()


def test_incomplete_row_requires_all_counts_null():
    """An incomplete row with a non-NULL count is rejected."""
    engine = _make_engine()
    s = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        _run_counter[0] += 1
        run = PipelineRun(run_id_str=f"r_{_run_counter[0]}", domain="AI",
                          status="completed", config_json="{}", stages_completed="[]",
                          provenance_version="provenance_v1")
        s.add(run); s.commit()
        sq = SearchQuery(run_id=run.id, query_key="qk", query_text="q")
        s.add(sq); s.commit()

        with pytest.raises(SAIntegrityError):
            s.execute(text(
                "INSERT INTO search_query_executions "
                "(search_query_id, source, status, attempt_count, accounting_status, "
                " raw_result_count) "
                "VALUES (:sqid, 'arxiv', 'pending', 0, 'incomplete', 5)"
            ), {"sqid": sq.id})
            s.commit()
    finally:
        s.close()


# ── 5. Migration tests ───────────────────────────────────────────────


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


def test_migration_017_preserves_legacy():
    """Build at 016, insert execution, upgrade to 017. Legacy preserved."""
    from alembic import command

    tmpdir = tempfile.mkdtemp()
    db_url = f"sqlite:///{Path(tmpdir) / 'p024.db'}"
    cfg = _alembic_cfg(db_url)

    with _patched_settings(db_url):
        command.upgrade(cfg, "016")
        engine = create_engine(db_url)
        with engine.connect() as c:
            c.execute(text(
                "INSERT INTO pipeline_runs "
                "(run_id_str,domain,status,config_json,stages_completed,created_at,provenance_version) "
                "VALUES ('r1','AI','completed','{}','[]',CURRENT_TIMESTAMP,'provenance_v1')"
            ))
            c.execute(text(
                "INSERT INTO search_queries "
                "(run_id,query_key,query_text,query_type,generation_origin,sequence_number,status) "
                "VALUES (1,'k','q','template','base',0,'persisted')"
            ))
            c.execute(text(
                "INSERT INTO search_query_executions "
                "(search_query_id,source,status,attempt_count,accounting_status) "
                "VALUES (1,'arxiv','failed',1,'incomplete')"
            ))
            c.commit()

        command.upgrade(cfg, "017")
        engine = create_engine(db_url)
        with engine.connect() as c:
            row = c.execute(text(
                "SELECT accounting_schema_version, accounting_status, raw_result_count "
                "FROM search_query_executions WHERE id=1"
            )).one()
            assert row[0] is None, "legacy accounting_schema_version should be NULL"
            assert row[1] == "incomplete"
            assert row[2] is None


def test_migration_017_round_trip():
    from alembic import command

    tmpdir = tempfile.mkdtemp()
    db_url = f"sqlite:///{Path(tmpdir) / 'rt.db'}"
    cfg = _alembic_cfg(db_url)

    with _patched_settings(db_url):
        command.upgrade(cfg, "016")
        command.upgrade(cfg, "017")
        command.downgrade(cfg, "016")
        command.upgrade(cfg, "017")
        with create_engine(db_url).connect() as c:
            cols = [r[1] for r in c.execute(text("PRAGMA table_info(search_query_executions)"))]
            assert "accounting_schema_version" in cols
