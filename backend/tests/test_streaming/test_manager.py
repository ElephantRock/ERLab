"""Tests for StreamManager."""

import asyncio
import time

import pytest

from backend.pipeline.streaming.events import StreamEvent, StreamEventType
from backend.pipeline.streaming.manager import StreamManager


@pytest.fixture
def manager():
    return StreamManager(dedup_window=1.0)


class TestStreamManagerCreateRemove:
    def test_create_stream(self, manager):
        q = manager.create_stream("run_1")
        assert isinstance(q, asyncio.Queue)
        assert "run_1" in manager.get_active_streams()

    def test_remove_stream(self, manager):
        manager.create_stream("run_1")
        manager.remove_stream("run_1")
        assert "run_1" not in manager.get_active_streams()

    def test_stream_count(self, manager):
        assert manager.stream_count == 0
        manager.create_stream("r1")
        manager.create_stream("r2")
        assert manager.stream_count == 2


class TestStreamManagerEmit:
    def test_emit_to_specific_run(self, manager):
        q = manager.create_stream("run_1")
        event = StreamEvent(type=StreamEventType.PROGRESS, run_id="run_1", data={"pct": 50})
        count = manager.emit(event)
        assert count == 1
        assert q.qsize() == 1
        received = q.get_nowait()
        assert received.data["pct"] == 50

    def test_emit_to_nonexistent_run(self, manager):
        event = StreamEvent(type=StreamEventType.PROGRESS, run_id="missing")
        count = manager.emit(event)
        assert count == 0

    def test_emit_broadcast_no_run_id(self, manager):
        q1 = manager.create_stream("r1")
        q2 = manager.create_stream("r2")
        event = StreamEvent(type=StreamEventType.HEARTBEAT)
        count = manager.emit(event)
        assert count == 2

    def test_emit_llm_chunk(self, manager):
        q = manager.create_stream("run_1")
        manager.emit_llm_chunk("run_1", "hello", "openai", "gpt-4o")
        assert q.qsize() == 1
        received = q.get_nowait()
        assert received.type == StreamEventType.LLM_CHUNK
        assert received.data["chunk"] == "hello"


class TestStreamManagerDedup:
    def test_dedup_suppresses_duplicate(self, manager):
        q = manager.create_stream("run_1")
        now = time.time()

        e1 = StreamEvent(type=StreamEventType.STAGE_COMPLETE, run_id="run_1", timestamp=now)
        e2 = StreamEvent(type=StreamEventType.STAGE_COMPLETE, run_id="run_1", timestamp=now + 0.5)

        manager.emit(e1)
        manager.emit(e2)  # Within 1s window — should be deduped

        assert q.qsize() == 1

    def test_dedup_allows_after_window(self, manager):
        manager._dedup_window = 0.01  # Very short window
        q = manager.create_stream("run_1")

        e1 = StreamEvent(type=StreamEventType.STAGE_COMPLETE, run_id="run_1", timestamp=time.time())
        manager.emit(e1)

        time.sleep(0.02)
        e2 = StreamEvent(type=StreamEventType.STAGE_COMPLETE, run_id="run_1", timestamp=time.time())
        manager.emit(e2)

        assert q.qsize() == 2

    def test_no_dedup_for_llm_chunks(self, manager):
        q = manager.create_stream("run_1")
        now = time.time()

        for _ in range(5):
            manager.emit(StreamEvent(type=StreamEventType.LLM_CHUNK, run_id="run_1", timestamp=now))

        assert q.qsize() == 5


class TestStreamManagerCancel:
    def test_cancel_sends_done(self, manager):
        q = manager.create_stream("run_1")
        manager.cancel_stream("run_1")
        assert q.qsize() == 1
        event = q.get_nowait()
        assert event.type == StreamEventType.DONE
        assert "run_1" not in manager.get_active_streams()

    def test_get_active_streams(self, manager):
        manager.create_stream("r1")
        manager.create_stream("r2")
        assert sorted(manager.get_active_streams()) == ["r1", "r2"]
