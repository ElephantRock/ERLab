"""Tests for consolidation scheduler."""

import asyncio
import time

import pytest

from backend.pipeline.knowledge.truth import TruthValue
from backend.pipeline.memory.consolidation import LLMConsolidator
from backend.pipeline.memory.models import MemoryEntry, MemoryType
from backend.pipeline.memory.scheduler import ConsolidationScheduler
from backend.pipeline.memory.service import MemoryService
from backend.tests.conftest import FakeLLMProvider


@pytest.fixture
def memory(tmp_path):
    return MemoryService(persist_path=str(tmp_path / "mem"))


@pytest.fixture
def consolidator():
    return LLMConsolidator(provider=FakeLLMProvider(), similarity_threshold=0.9)


@pytest.fixture
def scheduler(memory, consolidator):
    return ConsolidationScheduler(
        memory=memory,
        consolidator=consolidator,
        interval_hours=1,
    )


class TestConsolidationSchedulerLifecycle:
    @pytest.mark.anyio
    async def test_start_and_stop(self, scheduler):
        await scheduler.start()
        assert scheduler.status()["running"] is True
        await scheduler.stop()
        assert scheduler.status()["running"] is False

    @pytest.mark.anyio
    async def test_stop_when_not_started(self, scheduler):
        await scheduler.stop()
        assert scheduler.status()["running"] is False

    @pytest.mark.anyio
    async def test_cancel_cancels_task(self, scheduler):
        await scheduler.start()
        task = scheduler._task
        assert task is not None
        await scheduler.stop()
        assert task.cancelled() or task.done()


class TestConsolidationSchedulerSweep:
    @pytest.mark.anyio
    async def test_run_sweep_records_stats(self, scheduler):
        await scheduler._run_sweep()
        status = scheduler.status()
        assert status["sweeps_completed"] == 1
        assert status["last_run"] is not None

    @pytest.mark.anyio
    async def test_sweep_increments_entries_consolidated(self, memory, scheduler):
        entry = MemoryEntry(
            id="",
            content="RAG with reranking improves retrieval by 15 percent",
            memory_type=MemoryType.SEMANTIC,
            namespace="research_facts",
            truth=TruthValue.from_observation(0.8),
        )
        await memory.store(entry)
        await scheduler._run_sweep()
        assert scheduler.status()["entries_consolidated"] == 1


class TestConsolidationSchedulerStatus:
    def test_initial_status(self, scheduler):
        status = scheduler.status()
        assert status["running"] is False
        assert status["last_run"] is None
        assert status["sweeps_completed"] == 0
        assert status["entries_consolidated"] == 0
        assert status["interval_hours"] == 1

    @pytest.mark.anyio
    async def test_status_after_multiple_sweeps(self, scheduler):
        await scheduler._run_sweep()
        await scheduler._run_sweep()
        assert scheduler.status()["sweeps_completed"] == 2
