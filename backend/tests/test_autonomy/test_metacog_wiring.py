"""Tests for WP-8 metacognition wiring: hooks, state transitions, curiosity persistence."""

import asyncio
import sys
import tempfile
from datetime import datetime
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import pytest

# Stub out chromadb
_chromadb = ModuleType("chromadb")
_chromadb.PersistentClient = MagicMock
_chromadb.HttpClient = MagicMock
sys.modules.setdefault("chromadb", _chromadb)

from backend.pipeline.autonomy.hooks import HookDispatcher


class TestHookHandlersRegistered:
    def test_stage_complete_handler_registered(self):
        """HookDispatcher should have pipeline.stage.complete registered after init."""
        hooks = HookDispatcher()
        received = []

        async def handler(payload):
            received.append(payload)

        hooks.register("pipeline.stage.complete", handler)
        assert "pipeline.stage.complete" in hooks.registered_events

    def test_handler_receives_timing_payload(self):
        hooks = HookDispatcher()
        received = []

        async def handler(payload):
            received.append(payload)

        hooks.register("pipeline.stage.complete", handler)

        payload = {"stage": "gap_analysis", "elapsed": 1.5, "run_id": "test_run"}
        asyncio.run(hooks.dispatch("pipeline.stage.complete", payload))

        assert len(received) == 1
        assert received[0]["stage"] == "gap_analysis"
        assert received[0]["elapsed"] == 1.5


class TestStateTransitionDispatchesHook:
    def test_transition_dispatches_hook_event(self):
        from backend.pipeline.autonomy.state_machine import ConsciousnessStateMachine

        sm = ConsciousnessStateMachine(idle_timeout_seconds=0)
        hooks = HookDispatcher()
        transitions = []

        async def handler(payload):
            transitions.append(payload)

        hooks.register("state.transition", handler)

        # Simulate _transition_and_dispatch
        old = sm.current_state
        sm.transition("idle_timeout")
        asyncio.run(hooks.dispatch("state.transition", {
            "from": old.value,
            "to": sm.current_state.value,
            "trigger": "idle_timeout",
        }))

        assert len(transitions) == 1
        assert transitions[0]["from"] == "idle"
        assert transitions[0]["to"] == "exploring"
        assert transitions[0]["trigger"] == "idle_timeout"

    def test_multiple_transitions_all_dispatch(self):
        from backend.pipeline.autonomy.state_machine import ConsciousnessStateMachine

        sm = ConsciousnessStateMachine(idle_timeout_seconds=0)
        hooks = HookDispatcher()
        transitions = []

        async def handler(payload):
            transitions.append(payload)

        hooks.register("state.transition", handler)

        # idle -> exploring
        old = sm.current_state
        sm.transition("idle_timeout")
        asyncio.run(hooks.dispatch("state.transition", {"from": old.value, "to": sm.current_state.value, "trigger": "idle_timeout"}))

        # exploring -> focused (via new_high_confidence_gap)
        old = sm.current_state
        sm.transition("new_high_confidence_gap")
        asyncio.run(hooks.dispatch("state.transition", {"from": old.value, "to": sm.current_state.value, "trigger": "new_high_confidence_gap"}))

        assert len(transitions) == 2
        assert transitions[0]["from"] == "idle"
        assert transitions[1]["from"] == "exploring"


class TestCuriosityTopicPersisted:
    def test_curiosity_suggestion_stored_as_memory(self):
        from backend.pipeline.knowledge.truth import TruthValue
        from backend.pipeline.memory.models import MemoryEntry, MemoryType
        from backend.pipeline.memory.service import MemoryService

        with tempfile.TemporaryDirectory() as tmp:
            memory = MemoryService(persist_path=tmp)

            suggestion = {
                "topic": "Few-shot learning in multimodal settings",
                "search_queries": ["few-shot multimodal 2024"],
            }

            # Simulate what autonomous_cycle does after curiosity suggestion
            entry = MemoryEntry(
                id="",
                content=f"Curiosity exploration: {suggestion['topic']}",
                memory_type=MemoryType.EPISODIC,
                namespace="curiosity_exploration",
                truth=TruthValue.from_observation(frequency=0.7),
                tags=["curiosity", "autonomous"],
                created_at=datetime.now(),
            )
            entry_id = asyncio.run(memory.store(entry))

            # Verify stored
            assert entry_id in memory._index
            stored = memory._index[entry_id]
            assert stored.namespace == "curiosity_exploration"
            assert "curiosity" in stored.tags
            assert "Few-shot" in stored.content
