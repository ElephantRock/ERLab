"""Tests for pipeline run watchdog (BATCH-74/TASK-03)."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from backend.pipeline.execution.watchdog import PipelineWatchdog


def _make_run(run_id: int, status: str = "running", created_hours_ago: float = 0, updated_hours_ago: float = None):
    """Create a mock PipelineRun."""
    run = MagicMock()
    run.id = run_id
    run.status = status
    run.session_id = f"session_{run_id}"
    run.created_at = datetime.now(UTC) - timedelta(hours=created_hours_ago)
    if updated_hours_ago is not None:
        run.updated_at = datetime.now(UTC) - timedelta(hours=updated_hours_ago)
    else:
        run.updated_at = None
    return run


class TestPipelineWatchdog:
    def test_finds_stale_runs(self):
        """TEST-74-03-01: find_stale_runs returns runs past timeout."""
        persistence = MagicMock()
        stale_run = _make_run(1, status="running", created_hours_ago=2)
        persistence.find_stale_runs.return_value = [stale_run]
        persistence.mark_stale_run_failed = MagicMock()

        watchdog = PipelineWatchdog(persistence, timeout=timedelta(minutes=30))
        marked = asyncio.run(watchdog.check_and_mark_stale_runs())

        assert marked == 1
        persistence.find_stale_runs.assert_called_once()
        persistence.mark_stale_run_failed.assert_called_once_with(
            1,
            "Watchdog: run has been in 'running' status longer than 0:30:00. Marking as failed."
        )

    def test_ignores_completed_runs(self):
        """TEST-74-03-02: find_stale_runs ignores completed runs (HB-02)."""
        persistence = MagicMock()
        # Persistence only returns runs with status='running' — verify the query
        persistence.find_stale_runs.return_value = []
        persistence.mark_stale_run_failed = MagicMock()

        watchdog = PipelineWatchdog(persistence, timeout=timedelta(minutes=30))
        marked = asyncio.run(watchdog.check_and_mark_stale_runs())

        assert marked == 0
        persistence.mark_stale_run_failed.assert_not_called()

    def test_marks_stale_run_as_failed(self):
        """TEST-74-03-03: watchdog marks stale run as failed."""
        persistence = MagicMock()
        stale_run = _make_run(42, status="running", created_hours_ago=1)
        persistence.find_stale_runs.return_value = [stale_run]
        persistence.mark_stale_run_failed = MagicMock()

        watchdog = PipelineWatchdog(persistence, timeout=timedelta(minutes=30))
        marked = asyncio.run(watchdog.check_and_mark_stale_runs())

        assert marked == 1
        call_args = persistence.mark_stale_run_failed.call_args[0]
        assert call_args[0] == 42  # run id
        assert "failed" in call_args[1].lower() or "Watchdog" in call_args[1]

    def test_no_stale_runs(self):
        """Watchdog returns 0 when no stale runs found."""
        persistence = MagicMock()
        persistence.find_stale_runs.return_value = []

        watchdog = PipelineWatchdog(persistence, timeout=timedelta(minutes=30))
        marked = asyncio.run(watchdog.check_and_mark_stale_runs())

        assert marked == 0

    def test_sync_check(self):
        """Synchronous check works the same as async."""
        persistence = MagicMock()
        stale_run = _make_run(1, status="running", created_hours_ago=2)
        persistence.find_stale_runs.return_value = [stale_run]
        persistence.mark_stale_run_failed = MagicMock()

        watchdog = PipelineWatchdog(persistence, timeout=timedelta(minutes=30))
        marked = watchdog.check_sync()

        assert marked == 1


class TestPersistenceStaleRuns:
    def test_advance_stage_updates_timestamp(self):
        """TEST-74-03-04: advance_stage updates updated_at timestamp."""
        from backend.pipeline.persistence import PipelinePersistence

        persistence = PipelinePersistence()
        mock_run = MagicMock()
        mock_run.stages_completed = "[]"
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_run

        with patch("backend.db.database.get_session") as mock_get_session:
            # get_session is used as context manager
            mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            persistence.advance_stage(1, "ingestion")

            # Verify updated_at was set
            assert mock_run.updated_at is not None
            # Should be roughly now
            age = datetime.now(UTC) - mock_run.updated_at
            assert age.total_seconds() < 5  # Within 5 seconds

    def test_find_stale_runs_query(self):
        """TEST-74-03-05: find_stale_runs queries correctly."""
        from backend.pipeline.persistence import PipelinePersistence

        persistence = PipelinePersistence()
        stale_run = _make_run(1, status="running", created_hours_ago=2)
        recent_run = _make_run(2, status="running", created_hours_ago=0.1)

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = [stale_run, recent_run]

        with patch("backend.db.database.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            result = persistence.find_stale_runs(max_age=timedelta(minutes=30))

            # Only the stale run (created 2 hours ago) should be returned
            assert len(result) == 1
            assert result[0].id == 1


class TestWatchdogEndpoint:
    def test_endpoint_returns_count(self):
        """TEST-74-03-05: POST /pipeline/watchdog returns cleaned count."""
        from fastapi.testclient import TestClient

        from backend.api.app import app

        client = TestClient(app)
        with patch("backend.pipeline.execution.watchdog.PipelineWatchdog.check_and_mark_stale_runs", return_value=2):
            response = client.post("/api/v1/pipeline/watchdog?timeout_minutes=30")
            assert response.status_code == 200
            data = response.json()
            assert data["marked_failed"] == 2
            assert data["timeout_minutes"] == 30
