"""BATCH-55 TASK-01: Pipeline background task error handling tests.

Tests that when the orchestrator's run() method throws an exception,
the DB run record is updated to status='failed' with error_message
and completed_at set.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.pipeline import router

app = FastAPI()
app.include_router(router, prefix="/api/v1/pipeline")


def _mock_session():
    """Create a mock session context manager."""
    ms = MagicMock()
    mc = MagicMock()
    mc.__enter__ = MagicMock(return_value=ms)
    mc.__exit__ = MagicMock(return_value=False)
    return ms, mc


def _make_run_record(run_id=1, status="running", error_message=None, completed_at=None):
    """Create a mock PipelineRun record."""
    rec = MagicMock()
    rec.id = run_id
    rec.status = status
    rec.error_message = error_message
    rec.completed_at = completed_at
    return rec


def test_55_01_01_pipeline_failure_updates_db_status_to_failed():
    """When a pipeline run fails, the DB run record status is set to 'failed'."""
    run_record = _make_run_record(run_id=1, status="running")
    ms, mc = _mock_session()
    ms.execute.return_value.scalar_one_or_none.return_value = run_record

    with (
        patch("backend.pipeline.orchestrator.PipelineOrchestrator") as MockOrch,
        patch("backend.db.database.get_session", return_value=mc),
        patch("backend.notifications.fire_webhook", new_callable=AsyncMock),
        patch("backend.notifications.create_notification", new_callable=AsyncMock),
    ):
        orch_instance = MagicMock()
        orch_instance.run = AsyncMock(side_effect=RuntimeError("LLM provider timeout"))
        orch_instance._should_stop = MagicMock(return_value=False)
        MockOrch.return_value = orch_instance

        client = TestClient(app)
        resp = client.post("/api/v1/pipeline/run", json={"domain": "AI/NLP"})

    assert resp.status_code == 200
    # Verify the DB record was updated to "failed"
    assert run_record.status == "failed"


def test_55_01_02_pipeline_failure_sets_error_message():
    """When a pipeline run fails, the error_message is set on the DB record."""
    run_record = _make_run_record(run_id=2, status="running")
    ms, mc = _mock_session()
    ms.execute.return_value.scalar_one_or_none.return_value = run_record

    with (
        patch("backend.pipeline.orchestrator.PipelineOrchestrator") as MockOrch,
        patch("backend.db.database.get_session", return_value=mc),
        patch("backend.notifications.fire_webhook", new_callable=AsyncMock),
        patch("backend.notifications.create_notification", new_callable=AsyncMock),
    ):
        orch_instance = MagicMock()
        orch_instance.run = AsyncMock(side_effect=RuntimeError("LLM provider timeout"))
        orch_instance._should_stop = MagicMock(return_value=False)
        MockOrch.return_value = orch_instance

        client = TestClient(app)
        resp = client.post("/api/v1/pipeline/run", json={"domain": "AI/NLP"})

    assert resp.status_code == 200
    assert run_record.error_message is not None
    assert "LLM provider timeout" in run_record.error_message


def test_55_01_03_pipeline_failure_sets_completed_at():
    """When a pipeline run fails, completed_at is set to a UTC datetime."""
    run_record = _make_run_record(run_id=3, status="running")
    ms, mc = _mock_session()
    ms.execute.return_value.scalar_one_or_none.return_value = run_record

    with (
        patch("backend.pipeline.orchestrator.PipelineOrchestrator") as MockOrch,
        patch("backend.db.database.get_session", return_value=mc),
        patch("backend.notifications.fire_webhook", new_callable=AsyncMock),
        patch("backend.notifications.create_notification", new_callable=AsyncMock),
    ):
        orch_instance = MagicMock()
        orch_instance.run = AsyncMock(side_effect=RuntimeError("Unexpected error"))
        orch_instance._should_stop = MagicMock(return_value=False)
        MockOrch.return_value = orch_instance

        client = TestClient(app)
        resp = client.post("/api/v1/pipeline/run", json={"domain": "AI/NLP"})

    assert resp.status_code == 200
    assert run_record.completed_at is not None
    assert isinstance(run_record.completed_at, datetime)
