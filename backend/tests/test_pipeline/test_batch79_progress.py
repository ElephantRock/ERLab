"""Tests for BATCH-79 — Live Pipeline Progress with Real Messages.

TASK-01: ProgressReporter + Event Model (7 tests)
TASK-02: Stage Integration (5 tests)

AIV v5.3 — T1, T2, T5
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from backend.pipeline.streaming.progress_reporter import ProgressReporter, ProgressEvent


# ══════════════════════════════════════════════════════════
# TASK-01: ProgressReporter + Event Model
# ══════════════════════════════════════════════════════════

# TEST-79-01-01: emit calls callback
def test_79_01_01_emit_calls_callback():
    """ProgressReporter.emit() calls callback with correct ProgressEvent."""
    callback = MagicMock()
    reporter = ProgressReporter(callback=callback)
    reporter.emit("ingestion", "test_step", "Test message", 0.5)
    assert callback.called
    event = callback.call_args[0][0]
    assert isinstance(event, ProgressEvent)
    assert event.message == "Test message"
    assert event.stage == "ingestion"


# TEST-79-01-02: ProgressEvent has correct fields
def test_79_01_02_progress_event_fields():
    """ProgressEvent has all required fields."""
    event = ProgressEvent(
        event_type="progress",
        stage="ingestion",
        step="arxiv_search",
        message="Searching arXiv...",
        progress_pct=0.3,
    )
    assert event.event_type == "progress"
    assert event.stage == "ingestion"
    assert event.step == "arxiv_search"
    assert event.message == "Searching arXiv..."
    assert event.progress_pct == 0.3
    assert event.timestamp > 0


# TEST-79-01-03: progress_pct clamped to [0, 1]
def test_79_01_03_progress_pct_clamped():
    """progress_pct > 1.0 is clamped to 1.0."""
    event = ProgressEvent(progress_pct=1.5)
    assert event.progress_pct == 1.0

    event_neg = ProgressEvent(progress_pct=-0.5)
    assert event_neg.progress_pct == 0.0


# TEST-79-01-04: stage_start emits correct event
def test_79_01_04_stage_start():
    """stage_start emits progress event with start step."""
    callback = MagicMock()
    reporter = ProgressReporter(callback=callback)
    reporter.stage_start("ingestion", total_steps=5)
    event = callback.call_args[0][0]
    assert event.step == "start"
    assert event.progress_pct == 0.0


# TEST-79-01-05: Callback error doesn't crash
def test_79_01_05_callback_error_non_fatal():
    """If callback raises, reporter doesn't crash (HB-03)."""
    callback = MagicMock(side_effect=RuntimeError("SSE error"))
    reporter = ProgressReporter(callback=callback)
    # Should NOT raise
    reporter.emit("test", "step", "message")
    # Reporter is still usable
    callback2 = MagicMock()
    reporter.set_callback(callback2)
    reporter.emit("test", "step2", "message2")
    assert callback2.called


# TEST-79-01-06: stage_step increments progress
def test_79_01_06_stage_step_increments():
    """stage_step calculates progress from total_steps."""
    events = []
    reporter = ProgressReporter(callback=lambda e: events.append(e))
    reporter.stage_start("ingestion", total_steps=4)
    reporter.stage_step("step1", "Step 1")
    reporter.stage_step("step2", "Step 2")
    reporter.stage_step("step3", "Step 3")
    reporter.stage_step("step4", "Step 4")
    # step1=0.25, step2=0.5, step3=0.75, step4=1.0
    assert events[1].progress_pct == 0.25
    assert events[2].progress_pct == 0.5
    assert events[3].progress_pct == 0.75
    assert events[4].progress_pct == 1.0


# TEST-79-01-07: stage_complete emits 1.0 progress
def test_79_01_07_stage_complete():
    """stage_complete emits progress_pct=1.0."""
    callback = MagicMock()
    reporter = ProgressReporter(callback=callback)
    reporter.stage_start("ingestion")
    reporter.stage_complete("ingestion")
    event = callback.call_args[0][0]
    assert event.progress_pct == 1.0
    assert event.step == "complete"


# ══════════════════════════════════════════════════════════
# TASK-02: No sensitive data check + integration
# ══════════════════════════════════════════════════════════

# TEST-79-02-01: Messages don't contain API keys
def test_79_02_01_no_api_keys_in_messages():
    """Progress messages MUST NOT contain API keys (HB-02)."""
    events = []
    reporter = ProgressReporter(callback=lambda e: events.append(e))
    reporter.stage_start("literature_search")
    reporter.stage_step("arxiv_search", "Searching arXiv for 'sparse attention'")
    reporter.stage_step("openalex_search", "Searching OpenAlex...")
    reporter.stage_complete("literature_search")

    for event in events:
        assert "sk-" not in event.message
        assert "api_key" not in event.message.lower()


# TEST-79-02-02: No internal prompts in messages
def test_79_02_02_no_internal_prompts_in_messages():
    """Progress messages don't contain LLM system prompts."""
    events = []
    reporter = ProgressReporter(callback=lambda e: events.append(e))
    reporter.stage_step("test", "Clustering papers by topic")
    for event in events:
        assert "system_prompt" not in event.message
        assert "You are" not in event.message


# TEST-79-02-03: ProgressEvent is serializable
def test_79_02_03_progress_event_serializable():
    """ProgressEvent can be converted to dict/JSON."""
    import json
    event = ProgressEvent(
        stage="ingestion",
        step="arxiv_search",
        message="Found 23 papers",
        progress_pct=0.5,
    )
    data = {
        "event_type": event.event_type,
        "stage": event.stage,
        "step": event.step,
        "message": event.message,
        "progress_pct": event.progress_pct,
        "timestamp": event.timestamp,
    }
    json_str = json.dumps(data)
    assert isinstance(json_str, str)
    assert "Found 23 papers" in json_str


# TEST-79-02-04: Existing StreamEventType.PROGRESS exists
def test_79_02_04_stream_event_progress_type_exists():
    """StreamEventType.PROGRESS already exists (HB-01 backward compat)."""
    from backend.pipeline.streaming.events import StreamEventType
    assert hasattr(StreamEventType, "PROGRESS")
    assert StreamEventType.PROGRESS.value == "progress"


# TEST-79-02-05: Reporter works without callback
def test_79_02_05_reporter_works_without_callback():
    """Reporter doesn't crash when callback is None."""
    reporter = ProgressReporter(callback=None)
    # These should all succeed silently
    reporter.stage_start("test")
    reporter.stage_step("step1", "Doing something")
    reporter.stage_complete("test")
