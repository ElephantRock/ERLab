"""Tests for consciousness state machine."""

import time

from backend.pipeline.autonomy.state_machine import (
    ConsciousnessState,
    ConsciousnessStateMachine,
)


class TestConsciousnessStateMachine:
    def test_initial_state_is_idle(self):
        sm = ConsciousnessStateMachine()
        assert sm.current_state == ConsciousnessState.IDLE

    def test_transition_idle_to_exploring(self):
        sm = ConsciousnessStateMachine()
        new_state = sm.transition("idle_timeout")
        assert new_state == ConsciousnessState.EXPLORING

    def test_transition_idle_to_focused(self):
        sm = ConsciousnessStateMachine()
        new_state = sm.transition("manual_trigger")
        assert new_state == ConsciousnessState.FOCUSED

    def test_full_cycle(self):
        sm = ConsciousnessStateMachine()
        assert sm.transition("idle_timeout") == ConsciousnessState.EXPLORING
        assert sm.transition("new_high_confidence_gap") == ConsciousnessState.FOCUSED
        assert sm.transition("generation_complete") == ConsciousnessState.CONTEMPLATING
        assert sm.transition("analysis_complete") == ConsciousnessState.DREAMING
        assert sm.transition("consolidation_complete") == ConsciousnessState.IDLE

    def test_invalid_transition_ignored(self):
        sm = ConsciousnessStateMachine()
        # No valid transition from IDLE + "generation_complete"
        new_state = sm.transition("generation_complete")
        assert new_state == ConsciousnessState.IDLE

    def test_history_tracks_transitions(self):
        sm = ConsciousnessStateMachine()
        sm.transition("idle_timeout")
        sm.transition("no_gaps_found")
        assert len(sm._history) == 2
        assert sm._history[0].from_state == ConsciousnessState.IDLE
        assert sm._history[0].to_state == ConsciousnessState.EXPLORING

    def test_should_explore_idle_short(self):
        sm = ConsciousnessStateMachine(idle_timeout_seconds=9999)
        assert sm.should_explore() is False

    def test_should_explore_idle_long(self):
        sm = ConsciousnessStateMachine(idle_timeout_seconds=0)
        assert sm.should_explore() is True

    def test_should_not_explore_when_not_idle(self):
        sm = ConsciousnessStateMachine(idle_timeout_seconds=0)
        sm.transition("idle_timeout")  # Now EXPLORING
        assert sm.should_explore() is False

    def test_get_next_action(self):
        sm = ConsciousnessStateMachine()
        action = sm.get_next_action()
        assert action["action"] == "wait"

        sm.transition("idle_timeout")
        action = sm.get_next_action()
        assert action["action"] == "broad_search"
