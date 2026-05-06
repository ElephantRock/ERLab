"""Tests for BATCH-95 — Run Stats Endpoint.

AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


def test_95_01_stats_endpoint_returns_dict():
    """Stats endpoint returns aggregate statistics."""
    from backend.api.routes.pipeline import run_stats
    import asyncio

    mock_run = MagicMock()
    mock_run.status = "completed"
    mock_run.duration_seconds = 120.0
    mock_run.idea_count = 3
    mock_run.gap_count = 5

    mock_persistence = MagicMock()
    mock_persistence.list_runs.return_value = [mock_run]

    with patch("backend.pipeline.persistence.PipelinePersistence", return_value=mock_persistence):
        result = asyncio.run(run_stats())

    assert result["total_runs"] == 1
    assert result["total_ideas"] == 3
    assert result["total_gaps"] == 5


def test_95_01_stats_handles_empty_runs():
    """Stats endpoint handles no runs gracefully."""
    from backend.api.routes.pipeline import run_stats
    import asyncio

    mock_persistence = MagicMock()
    mock_persistence.list_runs.return_value = []

    with patch("backend.pipeline.persistence.PipelinePersistence", return_value=mock_persistence):
        result = asyncio.run(run_stats())

    assert result["total_runs"] == 0
    assert result["avg_duration_s"] == 0


def test_95_01_stats_groups_by_status():
    """Stats endpoint groups runs by status."""
    from backend.api.routes.pipeline import run_stats
    import asyncio

    runs = []
    for status in ["completed", "completed", "failed", "running"]:
        r = MagicMock()
        r.status = status
        r.duration_seconds = 60
        r.idea_count = 0
        r.gap_count = 0
        runs.append(r)

    mock_persistence = MagicMock()
    mock_persistence.list_runs.return_value = runs

    with patch("backend.pipeline.persistence.PipelinePersistence", return_value=mock_persistence):
        result = asyncio.run(run_stats())

    assert result["by_status"]["completed"] == 2
    assert result["by_status"]["failed"] == 1


def test_95_01_stats_handles_exception():
    """Stats endpoint handles exceptions gracefully."""
    from backend.api.routes.pipeline import run_stats
    import asyncio

    mock_persistence = MagicMock()
    mock_persistence.list_runs.side_effect = Exception("DB error")

    with patch("backend.pipeline.persistence.PipelinePersistence", return_value=mock_persistence):
        result = asyncio.run(run_stats())

    assert result["total_runs"] == 0
    assert "error" in result
