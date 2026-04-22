"""Tests for stream events."""

import json
import time

from backend.pipeline.streaming.events import StreamEvent, StreamEventType


class TestStreamEventType:
    def test_all_types(self):
        expected = {
            "stage_start", "stage_complete", "idea_generated", "idea_scored",
            "tool_call", "llm_chunk", "error", "progress", "heartbeat", "done",
        }
        actual = {t.value for t in StreamEventType}
        assert actual == expected


class TestStreamEvent:
    def test_creation(self):
        event = StreamEvent(type=StreamEventType.PROGRESS, run_id="run_1")
        assert event.type == StreamEventType.PROGRESS
        assert event.run_id == "run_1"
        assert event.timestamp > 0
        assert len(event.event_id) == 12

    def test_event_id_unique(self):
        e1 = StreamEvent(type=StreamEventType.HEARTBEAT)
        e2 = StreamEvent(type=StreamEventType.HEARTBEAT)
        assert e1.event_id != e2.event_id

    def test_data_dict(self):
        event = StreamEvent(
            type=StreamEventType.STAGE_COMPLETE,
            data={"stage": "gen", "elapsed": 1.5},
        )
        assert event.data["stage"] == "gen"
        assert event.data["elapsed"] == 1.5

    def test_to_sse(self):
        event = StreamEvent(
            type=StreamEventType.HEARTBEAT,
            run_id="r1",
        )
        sse = event.to_sse()
        assert sse.startswith("data: ")
        assert sse.endswith("\n\n")
        data = json.loads(sse[6:].strip())
        assert data["type"] == "heartbeat"
        assert data["run_id"] == "r1"

    def test_serialization_roundtrip(self):
        event = StreamEvent(
            type=StreamEventType.ERROR,
            run_id="r2",
            data={"message": "test error"},
        )
        dumped = event.model_dump(mode="json")
        restored = StreamEvent(**dumped)
        assert restored.type == StreamEventType.ERROR
        assert restored.data["message"] == "test error"
