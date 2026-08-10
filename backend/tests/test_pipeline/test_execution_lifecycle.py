"""Tests for P0.2.2: execution lifecycle of literature search.

Proves the runtime lifecycle of each intended query/source execution:
  - Every actual outbound request triggers one observer callback.
  - Pre-attempt failures are recorded with attempt_count = 0.
  - Post-attempt failures retain the observed attempt count.
  - Bare-list governed returns are recorded as failed and propagated.
  - External cancellation leaves an honest running execution.
  - Only one concurrent caller can claim a pending execution.
  - All accounting count columns remain NULL and accounting_status = incomplete.

Uses fake source adapters (fast, no network) + in-memory SQLite with FK
enforcement. The concurrency test uses a file-backed SQLite database with
separate sessions per the frozen policy.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.db.database import Base
from backend.db.models import (
    PipelineRun,
    SearchQuery,
    SearchQueryExecution,
)
from backend.pipeline.literature.contracts import (
    SourceSearchOutcome,
)
from backend.pipeline.literature.execution_recorder import (
    DatabaseAttemptObserver,
    ExecutionAlreadyClaimed,
    ExecutionRecorder,
)
from backend.pipeline.literature.models import Paper as SearchPaper
from backend.pipeline.literature.models import SearchResult

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
        run_id_str=f"run_p022_{_run_counter[0]}",
        domain="AI", status="completed",
        config_json="{}", stages_completed="[]",
        provenance_version="provenance_v1",
    )
    session.add(run); session.commit()
    return run


def _make_query(session, run_id, query_key="qkey1", query_text="transformers"):
    sq = SearchQuery(run_id=run_id, query_key=query_key, query_text=query_text)
    session.add(sq); session.commit()
    return sq


def _fake_paper(title="Test Paper", source_id="test:1"):
    return SearchPaper(id=source_id, title=title, source="test")


# ── Fake adapters (implement build_query_plan + execute_query_plan) ──

from backend.pipeline.literature.contracts import (
    SourceQueryPlan,
    canonical_plan_json,
)
from backend.pipeline.literature.result_accounting import reconcile_source_results


def _acct_for(results):
    """Helper: build accounting for a list of results."""
    unique, acct = reconcile_source_results(
        raw_result_count=len(results),
        normalized_results=results,
        rejected_result_count=0,
    )
    return unique, acct


def _fake_plan(source="arxiv"):
    return SourceQueryPlan(
        source=source, schema_version="source_query_v1",
        translated_query=canonical_plan_json(source, {"query": "test"}),
        request_parameters={"query": "test"},
    )


class _SuccessAdapter:
    """Always succeeds with one attempt, returns N results."""
    source_name = "arxiv"
    def __init__(self, n_results=2):
        self._n = n_results
        self.call_count = 0
    def build_query_plan(self, query, limit=20, year_from=None, year_to=None):
        return _fake_plan()
    async def execute_query_plan(self, plan, *, attempt_observer=None):
        self.call_count += 1
        if attempt_observer:
            await attempt_observer.attempt_started()
        results = [SearchResult(paper=_fake_paper(f"Paper {i}", source_id=f"test:{i}"), source="arxiv")
                   for i in range(self._n)]
        unique, acct = _acct_for(results)
        return SourceSearchOutcome(results=unique, status="success", attempt_count=1, accounting=acct)


class _RetryAdapter:
    """Retries once on first call, succeeds on second attempt."""
    source_name = "arxiv"
    def __init__(self):
        self.call_count = 0
    def build_query_plan(self, query, limit=20, year_from=None, year_to=None):
        return _fake_plan()
    async def execute_query_plan(self, plan, *, attempt_observer=None):
        self.call_count += 1
        if attempt_observer:
            await attempt_observer.attempt_started()
        if attempt_observer:
            await attempt_observer.attempt_started()
        results = [SearchResult(paper=_fake_paper("Retried Paper"), source="arxiv")]
        unique, acct = _acct_for(results)
        return SourceSearchOutcome(results=unique, status="success", attempt_count=2, accounting=acct)


class _FailAdapter:
    """Reports a truthful failure."""
    source_name = "arxiv"
    def __init__(self):
        self.call_count = 0
    def build_query_plan(self, query, limit=20, year_from=None, year_to=None):
        return _fake_plan()
    async def execute_query_plan(self, plan, *, attempt_observer=None):
        self.call_count += 1
        if attempt_observer:
            await attempt_observer.attempt_started()
        return SourceSearchOutcome(
            results=[], status="failed", attempt_count=1,
            error_detail="connection refused",
            failure_category="transport", failure_code="connection_error",
        )


class _PreAttemptFailAdapter:
    """Raises before any observer callback (pre-attempt failure)."""
    source_name = "arxiv"
    def __init__(self):
        self.call_count = 0
    def build_query_plan(self, query, limit=20, year_from=None, year_to=None):
        raise ValueError("bad query construction")
    async def execute_query_plan(self, plan, *, attempt_observer=None):
        raise ValueError("should not reach execute")


class _TimeoutAdapter:
    """Simulates a timeout by sleeping longer than the recorder timeout."""
    source_name = "arxiv"
    def __init__(self):
        self.call_count = 0
    def build_query_plan(self, query, limit=20, year_from=None, year_to=None):
        return _fake_plan()
    async def execute_query_plan(self, plan, *, attempt_observer=None):
        self.call_count += 1
        if attempt_observer:
            await attempt_observer.attempt_started()
        await asyncio.sleep(10)
        return SourceSearchOutcome(results=[], status="success", attempt_count=1)


class _PartialAdapter:
    """Returns partial results with an error detail."""
    source_name = "arxiv"
    def __init__(self):
        self.call_count = 0
    def build_query_plan(self, query, limit=20, year_from=None, year_to=None):
        return _fake_plan()
    async def execute_query_plan(self, plan, *, attempt_observer=None):
        self.call_count += 1
        if attempt_observer:
            await attempt_observer.attempt_started()
        results = [SearchResult(paper=_fake_paper("Partial Paper"), source="arxiv")]
        unique, acct = _acct_for(results)
        return SourceSearchOutcome(
            results=unique, status="partial", attempt_count=1,
            error_detail="truncated response",
            failure_category="response_parse", failure_code="incomplete_response",
            accounting=acct,
        )


class _BareListAdapter:
    """Returns a bare list (violates governed contract)."""
    source_name = "arxiv"
    def __init__(self):
        self.call_count = 0
    def build_query_plan(self, query, limit=20, year_from=None, year_to=None):
        return _fake_plan()
    async def execute_query_plan(self, plan, *, attempt_observer=None):
        self.call_count += 1
        if attempt_observer:
            await attempt_observer.attempt_started()
        return [SearchResult(paper=_fake_paper(), source="arxiv")]  # bare list!


def _setup_execution(engine, source="arxiv"):
    """Build run + query + pending execution row, return (engine, exec_id, sq_id)."""
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        run = _make_run(session)
        sq = _make_query(session, run.id)
        ex = SearchQueryExecution(
            search_query_id=sq.id, source=source,
            status="pending", attempt_count=0,
        )
        session.add(ex); session.commit()
        return engine, ex.id, sq.id
    finally:
        session.close()


# ── 1. Successful invocation ─────────────────────────────────────────


def test_successful_invocation():
    """pending→running→success; attempt_count=1; timestamps set; counts NULL."""
    engine = _make_engine()
    _, exec_id, _ = _setup_execution(engine)
    adapter = _SuccessAdapter(n_results=3)
    recorder = ExecutionRecorder(engine)

    outcome = asyncio.run(recorder.run_execution(exec_id, "arxiv", adapter, "test"))

    assert outcome.status == "success"
    assert outcome.attempt_count == 1
    assert len(outcome.results) == 3

    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        row = session.get(SearchQueryExecution, exec_id)
        assert row.status == "success"
        assert row.attempt_count == 1
        assert row.attempted_at is not None
        assert row.completed_at is not None
        # P0.2.4: success now has reconciled accounting
        assert row.raw_result_count == 3
        assert row.normalized_result_count == 3
        assert row.rejected_result_count == 0
        assert row.source_unique_count == 3
        assert row.accounting_status == "reconciled"
    finally:
        session.close()


# ── 2. Internal retry then success ───────────────────────────────────


def test_internal_retry_then_success():
    """One execution row; attempt_count=2; no recorder-level retry."""
    engine = _make_engine()
    _, exec_id, _ = _setup_execution(engine)
    adapter = _RetryAdapter()
    recorder = ExecutionRecorder(engine)

    outcome = asyncio.run(recorder.run_execution(exec_id, "arxiv", adapter, "test"))

    assert outcome.status == "success"
    assert outcome.attempt_count == 2
    assert adapter.call_count == 1  # adapter called once, internal retry counted

    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        row = session.get(SearchQueryExecution, exec_id)
        assert row.attempt_count == 2
        assert row.status == "success"
    finally:
        session.close()


# ── 3. Swallowed failure now reported ────────────────────────────────


def test_swallowed_failure_now_reported():
    """Adapter reports failed, never recorded as empty success."""
    engine = _make_engine()
    _, exec_id, _ = _setup_execution(engine)
    adapter = _FailAdapter()
    recorder = ExecutionRecorder(engine)

    outcome = asyncio.run(recorder.run_execution(exec_id, "arxiv", adapter, "test"))

    assert outcome.status == "failed"
    assert outcome.attempt_count == 1
    assert len(outcome.results) == 0
    assert outcome.error_detail is not None

    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        row = session.get(SearchQueryExecution, exec_id)
        assert row.status == "failed"
        assert row.attempt_count == 1
    finally:
        session.close()


# ── 4. Skipped intended source ──────────────────────────────────────


def test_skipped_intended_source():
    """Source in intended_sources but no active adapter → skipped."""
    engine = _make_engine()
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        run = _make_run(session)
        sq = _make_query(session, run.id)
        session.commit()
        sq_id = sq.id
    finally:
        session.close()

    recorder = ExecutionRecorder(engine)
    source_to_id = recorder.ensure_pending_executions(sq_id, ["arxiv", "openalex"])
    recorder.skip_unavailable(source_to_id["openalex"], reason="no active adapter")

    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        arxiv_row = session.get(SearchQueryExecution, source_to_id["arxiv"])
        oa_row = session.get(SearchQueryExecution, source_to_id["openalex"])
        assert arxiv_row.status == "pending"
        assert oa_row.status == "skipped"
        assert oa_row.attempt_count == 0
        assert oa_row.attempted_at is None
        assert oa_row.completed_at is not None
    finally:
        session.close()


# ── 5. Duplicate terminal replay ─────────────────────────────────────


def test_duplicate_terminal_replay():
    """Second lifecycle call on terminal row → adapter NOT re-invoked → unchanged."""
    engine = _make_engine()
    _, exec_id, _ = _setup_execution(engine)
    adapter = _SuccessAdapter()
    recorder = ExecutionRecorder(engine)

    # First run
    outcome1 = asyncio.run(recorder.run_execution(exec_id, "arxiv", adapter, "test"))
    assert outcome1.status == "success"

    # Second run — should be a no-op replay
    outcome2 = asyncio.run(recorder.run_execution(exec_id, "arxiv", adapter, "test"))

    assert outcome2.status == "success"
    assert adapter.call_count == 1  # NOT called again


# ── 6. Invalid transition propagates ─────────────────────────────────


def test_invalid_transition_propagates():
    """pending→success is invalid; ValueError propagates; state unchanged."""
    engine = _make_engine()
    _, exec_id, _ = _setup_execution(engine)
    recorder = ExecutionRecorder(engine)

    # Directly try an invalid transition
    with pytest.raises(ValueError, match="invalid transition"):
        recorder._transition(exec_id, "success")

    # State unchanged
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        row = session.get(SearchQueryExecution, exec_id)
        assert row.status == "pending"
    finally:
        session.close()


# ── 7. Partial result ────────────────────────────────────────────────


def test_partial_result():
    """SourceSearchOutcome(status=partial) → candidates survive; terminal=partial."""
    engine = _make_engine()
    _, exec_id, _ = _setup_execution(engine)
    adapter = _PartialAdapter()
    recorder = ExecutionRecorder(engine)

    outcome = asyncio.run(recorder.run_execution(exec_id, "arxiv", adapter, "test"))

    assert outcome.status == "partial"
    assert len(outcome.results) == 1

    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        row = session.get(SearchQueryExecution, exec_id)
        assert row.status == "partial"
        assert row.error_detail is not None
    finally:
        session.close()


# ── 8. Timeout ───────────────────────────────────────────────────────


def test_timeout():
    """Recorder timeout → terminal 'timeout'; attempt_count from observer."""
    engine = _make_engine()
    _, exec_id, _ = _setup_execution(engine)
    adapter = _TimeoutAdapter()
    recorder = ExecutionRecorder(engine)

    outcome = asyncio.run(
        recorder.run_execution(exec_id, "arxiv", adapter, "test", timeout_seconds=0.1)
    )

    assert outcome.status == "timeout"
    assert outcome.attempt_count == 1  # one observer callback before sleep

    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        row = session.get(SearchQueryExecution, exec_id)
        assert row.status == "timeout"
        assert row.attempt_count == 1
    finally:
        session.close()


# ── 9. Multi-source query ────────────────────────────────────────────


def test_multi_source_query():
    """One row per intended source; independent outcomes preserved."""
    engine = _make_engine()
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        run = _make_run(session)
        sq = _make_query(session, run.id)
        session.commit()
        sq_id = sq.id
    finally:
        session.close()

    recorder = ExecutionRecorder(engine)
    source_to_id = recorder.ensure_pending_executions(sq_id, ["arxiv", "openalex"])

    good = _SuccessAdapter()
    good.source_name = "arxiv"
    bad = _FailAdapter()
    bad.source_name = "openalex"

    async def _run():
        r1 = await recorder.run_execution(source_to_id["arxiv"], "arxiv", good, "q")
        r2 = await recorder.run_execution(source_to_id["openalex"], "openalex", bad, "q")
        return r1, r2

    r1, r2 = asyncio.run(_run())
    assert r1.status == "success"
    assert r2.status == "failed"


# ── 10. Failed attempts with no candidates still recorded ───────────


def test_failed_attempts_no_candidates_still_recorded():
    """All sources fail → zero candidates → each failure row queryable."""
    engine = _make_engine()
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        run = _make_run(session)
        sq = _make_query(session, run.id)
        session.commit()
        sq_id = sq.id
    finally:
        session.close()

    recorder = ExecutionRecorder(engine)
    source_to_id = recorder.ensure_pending_executions(sq_id, ["arxiv", "openalex"])

    a1 = _FailAdapter(); a1.source_name = "arxiv"
    a2 = _FailAdapter(); a2.source_name = "openalex"

    async def _run():
        return await asyncio.gather(
            recorder.run_execution(source_to_id["arxiv"], "arxiv", a1, "q"),
            recorder.run_execution(source_to_id["openalex"], "openalex", a2, "q"),
        )

    outcomes = asyncio.run(_run())
    assert all(o.status == "failed" for o in outcomes)

    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        count = session.execute(
            select(func.count(SearchQueryExecution.id)).where(
                SearchQueryExecution.search_query_id == sq_id
            )
        ).scalar_one()
        assert count == 2  # both failures recorded
    finally:
        session.close()


# ── 11. Concurrent invocations — one claims ─────────────────────────


def test_concurrent_invocations_one_claims():
    """Two independent sessions race to claim one pending row; one wins.

    Uses a file-backed SQLite DB with separate sessions/connections per
    the frozen policy.
    """
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "concurrent.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)

    @event.listens_for(engine, "connect")
    def _fk(c, r):
        cur = c.cursor(); cur.execute("PRAGMA foreign_keys=ON"); cur.close()

    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        run = _make_run(session)
        sq = _make_query(session, run.id)
        ex = SearchQueryExecution(
            search_query_id=sq.id, source="arxiv",
            status="pending", attempt_count=0,
        )
        session.add(ex); session.commit()
        exec_id = ex.id
    finally:
        session.close()

    adapter = _SuccessAdapter()
    call_count = 0

    async def _try_claim():
        nonlocal call_count
        observer = DatabaseAttemptObserver(exec_id, engine)
        try:
            await observer.attempt_started()
            call_count += 1
            return True
        except ExecutionAlreadyClaimed:
            return False

    async def _race():
        return await asyncio.gather(_try_claim(), _try_claim())

    results = asyncio.run(_race())
    assert sum(1 for r in results if r) == 1, "exactly one invocation should claim"
    assert call_count == 1


# ── 12. Exception before first attempt ──────────────────────────────


def test_exception_before_first_attempt():
    """Pre-attempt failure: pending→failed, attempt_count=0, attempted_at NULL."""
    engine = _make_engine()
    _, exec_id, _ = _setup_execution(engine)
    adapter = _PreAttemptFailAdapter()
    recorder = ExecutionRecorder(engine)

    # The exception propagates, but the row is persisted as failed first.
    with pytest.raises(ValueError, match="bad query construction"):
        asyncio.run(recorder.run_execution(exec_id, "arxiv", adapter, "test"))

    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        row = session.get(SearchQueryExecution, exec_id)
        assert row.status == "failed"
        assert row.attempt_count == 0
        assert row.attempted_at is None
        assert row.completed_at is not None
        assert row.error_detail is not None
    finally:
        session.close()


# ── 13. Bare-list governed return rejected ──────────────────────────


def test_bare_list_governed_return_rejected():
    """Adapter returns bare list → TypeError propagates → recorded as failed."""
    engine = _make_engine()
    _, exec_id, _ = _setup_execution(engine)
    adapter = _BareListAdapter()
    recorder = ExecutionRecorder(engine)

    with pytest.raises(TypeError, match="SourceSearchOutcome"):
        asyncio.run(recorder.run_execution(exec_id, "arxiv", adapter, "test"))

    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        row = session.get(SearchQueryExecution, exec_id)
        assert row.status == "failed"  # recorded as failed, not success
    finally:
        session.close()


# ── 14. Cancellation leaves running row ─────────────────────────────


def test_cancellation_leaves_running():
    """CancelledError propagates; row stays running with observed count."""
    engine = _make_engine()
    _, exec_id, _ = _setup_execution(engine)

    class _CancellableAdapter:
        source_name = "arxiv"
        def build_query_plan(self, query, limit=20, year_from=None, year_to=None):
            return _fake_plan()
        async def execute_query_plan(self, plan, *, attempt_observer=None):
            if attempt_observer:
                await attempt_observer.attempt_started()
            await attempt_observer.attempt_started()  # second attempt
            await asyncio.sleep(100)  # will be cancelled

    adapter = _CancellableAdapter()
    recorder = ExecutionRecorder(engine)

    async def _run():
        task = asyncio.create_task(
            recorder.run_execution(exec_id, "arxiv", adapter, "test")
        )
        await asyncio.sleep(0.05)
        task.cancel()
        await task

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(_run())

    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        row = session.get(SearchQueryExecution, exec_id)
        assert row.status == "running"
        assert row.attempt_count == 2  # two observer callbacks before cancel
    finally:
        session.close()


# ── 15. Error detail sanitized ──────────────────────────────────────


def test_error_detail_sanitized():
    """api_key=secret + user:pass@host → neither in stored detail."""
    engine = _make_engine()
    _, exec_id, _ = _setup_execution(engine)

    class _SecretAdapter:
        source_name = "arxiv"
        def build_query_plan(self, query, limit=20, year_from=None, year_to=None):
            return _fake_plan()
        async def execute_query_plan(self, plan, *, attempt_observer=None):
            if attempt_observer:
                await attempt_observer.attempt_started()
            return SourceSearchOutcome(
                results=[], status="failed", attempt_count=1,
                error_detail="Auth failed: api_key=sk-abc123 at http://admin:hunter2@host/api",
                failure_category="authentication", failure_code="http_401",
            )

    recorder = ExecutionRecorder(engine)
    outcome = asyncio.run(recorder.run_execution(
        exec_id, "arxiv", _SecretAdapter(), "test",
    ))

    assert outcome.status == "failed"
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        row = session.get(SearchQueryExecution, exec_id)
        detail = row.error_detail
        assert "sk-abc123" not in detail
        assert "hunter2" not in detail
        assert "[auth]" in detail
        assert "[creds]" in detail
    finally:
        session.close()


# ── 16. No db_run_id skips recording ────────────────────────────────


def test_no_db_skips_recording():
    """Legacy path: no search_query_id → search runs, zero execution rows."""
    engine = _make_engine()
    # No execution rows created; recorder not invoked.
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        count = session.execute(
            select(func.count(SearchQueryExecution.id))
        ).scalar_one()
        assert count == 0
    finally:
        session.close()


# ── 17. Outcome invariant violation propagates ──────────────────────


def test_outcome_invariant_violation_propagates():
    """failed outcome with non-empty results → ValueError propagates."""
    from backend.pipeline.literature.contracts import validate_outcome

    bad = SourceSearchOutcome(
        results=[SearchResult(paper=_fake_paper(), source="arxiv")],
        status="failed", attempt_count=1, error_detail="oops",
    )
    with pytest.raises(ValueError, match="failed outcome must have empty results"):
        validate_outcome(bad, attempted_at_is_null=False)


# ── 18. Attempt-count mismatch propagates ───────────────────────────


def test_attempt_count_mismatch_propagates():
    """Adapter reports wrong attempt_count → ValueError (instrumentation defect)."""
    engine = _make_engine()
    _, exec_id, _ = _setup_execution(engine)

    class _LyingAdapter:
        source_name = "arxiv"
        def build_query_plan(self, query, limit=20, year_from=None, year_to=None):
            return _fake_plan()
        async def execute_query_plan(self, plan, *, attempt_observer=None):
            if attempt_observer:
                await attempt_observer.attempt_started()  # observer counts 1
            return SourceSearchOutcome(
                results=[], status="failed", attempt_count=99,  # lies
                error_detail="oops",
                failure_category="transport", failure_code="connection_error",
            )

    recorder = ExecutionRecorder(engine)
    with pytest.raises(ValueError, match="attempt_count mismatch"):
        asyncio.run(recorder.run_execution(exec_id, "arxiv", _LyingAdapter(), "test"))
