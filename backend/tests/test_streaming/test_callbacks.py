"""Tests for streaming callbacks."""

import asyncio

import pytest

from backend.pipeline.streaming.callbacks import create_llm_stream_callback, create_stage_callback
from backend.pipeline.streaming.events import StreamEventType
from backend.pipeline.streaming.manager import StreamManager


@pytest.fixture
def manager():
    return StreamManager(dedup_window=0.0)  # No dedup for tests


class TestCreateStageCallback:
    def test_emits_stage_complete(self, manager):
        q = manager.create_stream("run_1")
        callback = create_stage_callback(manager, "run_1")

        callback("idea_generation", 2, 5, 1.5)

        assert q.qsize() == 1
        event = q.get_nowait()
        assert event.type == StreamEventType.STAGE_COMPLETE
        assert event.data["stage"] == "idea_generation"
        assert event.data["index"] == 2
        assert event.data["total"] == 5
        assert event.data["elapsed"] == 1.5


class TestCreateLLMStreamCallback:
    def test_relays_chunks(self, manager):
        q = manager.create_stream("run_1")
        callback = create_llm_stream_callback(manager, "run_1")

        callback("Hello", "openai", "gpt-4o")
        callback(" world", "openai", "gpt-4o")

        assert q.qsize() == 2
        e1 = q.get_nowait()
        assert e1.type == StreamEventType.LLM_CHUNK
        assert e1.data["chunk"] == "Hello"

        e2 = q.get_nowait()
        assert e2.data["chunk"] == " world"
