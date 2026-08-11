"""Tests for BATCH-32 TASK-01: DB indexes + webhook notifications."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from backend.db.database import Base

# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()


# ── TEST-32-01-01: Indexes exist on frequently queried columns ────


def test_32_01_01_indexes_exist_on_frequently_queried_columns(db_engine):
    """Verify that DB indexes exist on columns used in common queries."""
    inspector = inspect(db_engine)
    indexes_by_table = {}
    for t in inspector.get_table_names():
        idx_list = inspector.get_indexes(t)
        indexes_by_table[t] = [tuple(cols) for idx in idx_list for cols in [idx["column_names"]]]

    # Idea indexes
    idea_idx = indexes_by_table.get("ideas", [])
    assert ("pipeline_run_id",) in idea_idx, "Missing index on ideas.pipeline_run_id"
    assert ("domain",) in idea_idx, "Missing index on ideas.domain"
    assert ("overall_score",) in idea_idx, "Missing index on ideas.overall_score"

    # PipelineRun indexes
    run_idx = indexes_by_table.get("pipeline_runs", [])
    assert ("status",) in run_idx, "Missing index on pipeline_runs.status"
    assert ("session_id",) in run_idx, "Missing index on pipeline_runs.session_id"

    # ResearchGapDB indexes
    gap_idx = indexes_by_table.get("research_gaps", [])
    assert ("pipeline_run_id",) in gap_idx, "Missing index on research_gaps.pipeline_run_id"
    assert ("confidence",) in gap_idx, "Missing index on research_gaps.confidence"


# ── TEST-32-01-02: Webhook fires on pipeline completion ──────────


@pytest.mark.anyio
async def test_32_01_02_webhook_fires_on_pipeline_completion():
    """Verify that fire_webhook is called with pipeline.completed event."""
    with patch("backend.notifications.webhooks.get_settings") as mock_settings, \
         patch("backend.notifications.webhooks._get_client") as mock_client_fn:
        mock_settings.return_value = MagicMock(
            webhook_enabled=True,
            webhook_url="https://hooks.example.com/pipeline",
            webhook_secret=None,
        )
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_fn.return_value = mock_client

        from backend.notifications.webhooks import fire_webhook
        await fire_webhook("pipeline.completed", {
            "run_id": "run_test",
            "domain": "AI/NLP",
            "status": "completed",
        })

        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        body = json.loads(call_kwargs.kwargs["content"])
        assert body["event"] == "pipeline.completed"
        assert body["data"]["run_id"] == "run_test"
        assert body["data"]["status"] == "completed"


# ── TEST-32-01-03: Webhook payload includes run summary ──────────


@pytest.mark.anyio
async def test_32_01_03_webhook_payload_includes_run_summary():
    """Verify that the webhook payload contains timestamp, event, and data."""
    with patch("backend.notifications.webhooks.get_settings") as mock_settings, \
         patch("backend.notifications.webhooks._get_client") as mock_client_fn:
        mock_settings.return_value = MagicMock(
            webhook_enabled=True,
            webhook_url="https://hooks.example.com/pipeline",
            webhook_secret="test-secret",
        )
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_fn.return_value = mock_client

        from backend.notifications.webhooks import fire_webhook
        await fire_webhook("pipeline.completed", {
            "run_id": "run_20260502",
            "domain": "AI/NLP",
            "status": "completed",
            "ideas_count": 5,
            "gaps_count": 3,
        })

        call_kwargs = mock_client.post.call_args
        body = json.loads(call_kwargs.kwargs["content"])

        # Payload structure
        assert "event" in body
        assert "timestamp" in body
        assert "data" in body
        assert body["data"]["ideas_count"] == 5
        assert body["data"]["gaps_count"] == 3

        # Signature header present when secret is configured
        headers = call_kwargs.kwargs["headers"]
        assert "X-Webhook-Signature" in headers


# ── TEST-32-01-04: Webhook failure doesn't block pipeline ────────


@pytest.mark.anyio
async def test_32_01_04_webhook_failure_doesnt_block_pipeline():
    """Verify that a webhook failure is caught and doesn't raise."""
    with patch("backend.notifications.webhooks.get_settings") as mock_settings, \
         patch("backend.notifications.webhooks._get_client") as mock_client_fn:
        mock_settings.return_value = MagicMock(
            webhook_enabled=True,
            webhook_url="https://hooks.example.com/pipeline",
            webhook_secret=None,
        )
        mock_client = AsyncMock()
        # Simulate network failure
        mock_client.post = AsyncMock(side_effect=ConnectionError("Network unreachable"))
        mock_client_fn.return_value = mock_client

        from backend.notifications.webhooks import fire_webhook
        # Should not raise — webhook failure is swallowed
        await fire_webhook("pipeline.completed", {"run_id": "run_x"})

        # Confirm it attempted to post
        mock_client.post.assert_called_once()
