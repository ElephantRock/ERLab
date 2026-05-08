"""BATCH-128 Tests — Daily Auto-Ingestion Scheduler."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.pipeline.ingestion.scheduler import IngestionScheduler, IngestionResult


class TestIngestionScheduler:
    def test_result_creates(self):
        """TEST-128-01: IngestionResult creates with defaults."""
        result = IngestionResult(run_time="2026-05-09")
        assert result.papers_fetched == 0
        assert result.errors == []

    def test_run_once_no_services(self):
        """TEST-128-02: run_once works with no services configured."""
        scheduler = IngestionScheduler()
        result = asyncio.run(scheduler.run_once())
        assert isinstance(result, IngestionResult)
        assert result.papers_fetched == 0

    def test_run_once_with_mock_search(self):
        """TEST-128-03: run_once fetches papers from search service."""
        search = MagicMock()
        search.search = AsyncMock(return_value=[
            {"id": "p1", "abstract": "Paper about transformers"},
            {"id": "p2", "abstract": "Paper about BERT"},
        ])
        scheduler = IngestionScheduler(search_service=search)
        result = asyncio.run(scheduler.run_once())
        assert result.papers_fetched == 2

    def test_run_once_handles_fetch_error(self):
        """TEST-128-04: Handles search service errors gracefully."""
        search = MagicMock()
        search.search = AsyncMock(side_effect=RuntimeError("API down"))
        scheduler = IngestionScheduler(search_service=search)
        result = asyncio.run(scheduler.run_once())
        assert len(result.errors) > 0

    def test_last_run_updated(self):
        """TEST-128-05: last_run is updated after run_once."""
        scheduler = IngestionScheduler()
        assert scheduler.last_run is None
        asyncio.run(scheduler.run_once())
        assert scheduler.last_run is not None
