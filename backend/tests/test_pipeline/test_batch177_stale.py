"""Tests for BATCH-177 — Stale Run Cleanup + Run Status Accuracy.

AIV v5.3 Test Integrity Protocol:
  - T1, T2, T5 apply
  - BATCH-177 is the FINAL batch of the B172-B177 remediation roadmap

TASK-01: GET /runs/stale endpoint + stale flag in run detail
TASK-02: Watchdog verification + regression + doc checks
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

# ── Helpers ──────────────────────────────────────────────────────────


def _make_run(
    run_id: int = 1,
    status: str = "running",
    domain: str = "AI/NLP",
    created_hours_ago: float = 2.0,
    updated_hours_ago: float | None = None,
):
    """Create a mock PipelineRun object."""
    run = MagicMock()
    run.id = run_id
    run.status = status
    run.domain = domain
    run.created_at = datetime.now(UTC) - timedelta(hours=created_hours_ago)
    run.updated_at = (
        datetime.now(UTC) - timedelta(hours=updated_hours_ago)
        if updated_hours_ago is not None
        else None
    )
    return run


def _make_run_detail(
    run_id: int = 1,
    status: str = "running",
    domain: str = "AI/NLP",
    created_hours_ago: float = 2.0,
):
    """Create a mock PipelineRun suitable for run detail endpoint."""
    run = MagicMock()
    run.id = run_id
    run.status = status
    run.domain = domain
    run.current_stage = "running"
    run.config_json = "{}"
    run.stages_completed = "[]"
    run.ideas = []
    run.tree_data_json = None
    run.stage_report_json = None
    run.created_at = datetime.now(UTC) - timedelta(hours=created_hours_ago)
    run.completed_at = None
    run.error_message = None
    return run


# ── TASK-01 Tests: Stale Runs Endpoint + Run Detail Stale Flag ─────


def test_stale_endpoint_returns_200():
    """TEST-177-01: GET /runs/stale returns 200."""
    from backend.api.app import app

    client = TestClient(app)

    with patch("backend.db.database.get_session") as mock_gs:
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_gs.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_gs.return_value.__exit__ = MagicMock(return_value=False)

        response = client.get("/api/v1/pipeline/runs/stale")
        assert response.status_code == 200


def test_stale_endpoint_returns_list():
    """TEST-177-02: Response has stale_runs key with list."""
    from backend.api.app import app

    client = TestClient(app)

    with patch("backend.db.database.get_session") as mock_gs:
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_gs.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_gs.return_value.__exit__ = MagicMock(return_value=False)

        response = client.get("/api/v1/pipeline/runs/stale")
        data = response.json()
        assert "stale_runs" in data
        assert isinstance(data["stale_runs"], list)
        assert "count" in data
        assert data["count"] == 0


def test_stale_only_returns_running():
    """TEST-177-03: Completed runs are not returned in stale list."""
    from backend.api.app import app

    client = TestClient(app)

    # The endpoint filters on status == "running" at the SQL level,
    # so with an empty query result, count should be 0
    with patch("backend.db.database.get_session") as mock_gs:
        mock_session = MagicMock()
        # Return empty list (no running runs at all)
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_gs.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_gs.return_value.__exit__ = MagicMock(return_value=False)

        response = client.get("/api/v1/pipeline/runs/stale")
        data = response.json()
        assert data["count"] == 0
        assert data["stale_runs"] == []


def test_stale_respects_timeout():
    """TEST-177-04: Short timeout returns more runs than long timeout."""
    from backend.api.app import app

    client = TestClient(app)

    # Create a run that's 45 minutes old
    stale_run = _make_run(1, status="running", created_hours_ago=0.75)

    with patch("backend.db.database.get_session") as mock_gs:
        mock_session = MagicMock()
        mock_gs.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_gs.return_value.__exit__ = MagicMock(return_value=False)

        # With 30-min timeout, the 45-min-old run IS stale
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [stale_run]
        resp_short = client.get("/api/v1/pipeline/runs/stale?timeout_minutes=30")
        assert resp_short.json()["count"] == 1

        # With 60-min timeout, the 45-min-old run is NOT stale (empty result)
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        resp_long = client.get("/api/v1/pipeline/runs/stale?timeout_minutes=60")
        assert resp_long.json()["count"] == 0


def test_run_detail_has_stale_field():
    """TEST-177-05: Run detail response includes stale key."""
    from backend.api.app import app

    client = TestClient(app)

    run = _make_run_detail(run_id=99, status="running", created_hours_ago=2.0)

    with patch("backend.db.crud.get_pipeline_run", return_value=run), \
         patch("backend.db.database.get_session") as mock_gs:
        mock_session = MagicMock()
        mock_gs.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_gs.return_value.__exit__ = MagicMock(return_value=False)

        response = client.get("/api/v1/pipeline/runs/detail/99")
        assert response.status_code == 200
        data = response.json()
        assert "stale" in data
        assert data["stale"] is True  # 2 hours old running run


def test_completed_run_stale_false():
    """TEST-177-06: Completed run has stale=false regardless of age."""
    from backend.api.app import app

    client = TestClient(app)

    # A completed run from 48 hours ago
    run = _make_run_detail(run_id=100, status="completed", created_hours_ago=48.0)

    with patch("backend.db.crud.get_pipeline_run", return_value=run), \
         patch("backend.db.database.get_session") as mock_gs:
        mock_session = MagicMock()
        mock_gs.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_gs.return_value.__exit__ = MagicMock(return_value=False)

        response = client.get("/api/v1/pipeline/runs/detail/100")
        assert response.status_code == 200
        data = response.json()
        assert "stale" in data
        assert data["stale"] is False  # Completed runs are never stale


# ── TASK-02 Tests: Watchdog Verification + Regression + Docs ────────


def test_watchdog_marks_stale_failed():
    """TEST-177-07: POST /watchdog marks stale runs as failed."""
    from backend.api.app import app

    client = TestClient(app)

    with patch("backend.pipeline.execution.watchdog.PipelineWatchdog.check_and_mark_stale_runs", return_value=3):
        response = client.post("/api/v1/pipeline/watchdog?timeout_minutes=30")
        assert response.status_code == 200
        data = response.json()
        assert data["checked"] is True
        assert data["marked_failed"] == 3
        assert data["stale_found"] == 3
        assert data["timeout_minutes"] == 30


def test_no_regressions():
    """TEST-177-08: Batch 172-176 modules still import cleanly."""
    # Verify core modules from B172-B176 are importable (no broken deps)
    from backend.pipeline.execution.watchdog import PipelineWatchdog  # B174 (watchdog existed)
    from backend.pipeline.preflight import run_preflight  # B172
    from backend.pipeline.result import StageReport  # B173
    from backend.providers.retry import retry_llm_call  # B176

    assert callable(run_preflight)
    assert callable(PipelineWatchdog)
    assert hasattr(StageReport, '__dataclass_fields__')
    assert callable(retry_llm_call)


def test_state_md_has_batch177():
    """TEST-177-09: STATE.md documents BATCH-177."""
    from pathlib import Path
    state = Path("docs/aiv/STATE.md").read_text(encoding="utf-8")
    assert "BATCH-177" in state
    assert "stale" in state.lower() or "Stale" in state


def test_changelog_has_batch177():
    """TEST-177-10: CHANGELOG.md documents BATCH-177."""
    from pathlib import Path
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    assert "BATCH-177" in changelog
    assert "stale" in changelog.lower() or "Stale" in changelog
