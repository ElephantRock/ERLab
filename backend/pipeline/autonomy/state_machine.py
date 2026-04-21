"""Consciousness state machine for autonomous research cycles.

PUMA-inspired state machine with 5 states: IDLE, EXPLORING, FOCUSED,
CONTEMPLATING, DREAMING. Each state has defined transitions triggered
by events like idle_timeout, new_gap_found, generation_complete, etc.
"""

import logging
from datetime import datetime
from enum import Enum

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ConsciousnessState(str, Enum):
    IDLE = "idle"  # No active work, waiting for triggers
    EXPLORING = "exploring"  # Broad literature search, trend scanning
    FOCUSED = "focused"  # Deep dive on specific gaps
    CONTEMPLATING = "contemplating"  # Analyzing results, synthesizing insights
    DREAMING = "dreaming"  # Consolidating memory, updating world model


class StateTransition(BaseModel):
    from_state: ConsciousnessState
    to_state: ConsciousnessState
    trigger: str
    timestamp: datetime = datetime.now()


# Valid transitions: (from_state, trigger) -> to_state
_TRANSITIONS: dict[tuple[ConsciousnessState, str], ConsciousnessState] = {
    (ConsciousnessState.IDLE, "idle_timeout"): ConsciousnessState.EXPLORING,
    (ConsciousnessState.IDLE, "new_gap_found"): ConsciousnessState.FOCUSED,
    (ConsciousnessState.IDLE, "manual_trigger"): ConsciousnessState.FOCUSED,
    (ConsciousnessState.EXPLORING, "new_high_confidence_gap"): ConsciousnessState.FOCUSED,
    (ConsciousnessState.EXPLORING, "no_gaps_found"): ConsciousnessState.IDLE,
    (ConsciousnessState.EXPLORING, "exploration_timeout"): ConsciousnessState.IDLE,
    (ConsciousnessState.FOCUSED, "generation_complete"): ConsciousnessState.CONTEMPLATING,
    (ConsciousnessState.FOCUSED, "generation_failed"): ConsciousnessState.CONTEMPLATING,
    (ConsciousnessState.CONTEMPLATING, "analysis_complete"): ConsciousnessState.DREAMING,
    (ConsciousnessState.DREAMING, "consolidation_complete"): ConsciousnessState.IDLE,
    (ConsciousnessState.DREAMING, "consolidation_timeout"): ConsciousnessState.IDLE,
}


class ConsciousnessStateMachine:
    """PUMA-inspired state machine for autonomous research cycles."""

    def __init__(self, idle_timeout_seconds: int = 3600):
        self._state = ConsciousnessState.IDLE
        self._idle_timeout_seconds = idle_timeout_seconds
        self._last_state_change = datetime.now()
        self._history: list[StateTransition] = []

    @property
    def current_state(self) -> ConsciousnessState:
        return self._state

    @property
    def last_state_change(self) -> datetime:
        return self._last_state_change

    @property
    def seconds_in_state(self) -> float:
        return (datetime.now() - self._last_state_change).total_seconds()

    def transition(self, trigger: str) -> ConsciousnessState:
        """Attempt a state transition based on a trigger event."""
        key = (self._state, trigger)
        new_state = _TRANSITIONS.get(key)

        if new_state is None:
            logger.debug("No transition for state=%s trigger=%s", self._state.value, trigger)
            return self._state

        old_state = self._state
        self._state = new_state
        self._last_state_change = datetime.now()

        transition = StateTransition(
            from_state=old_state,
            to_state=new_state,
            trigger=trigger,
        )
        self._history.append(transition)
        logger.info(
            "State transition: %s → %s (trigger: %s)", old_state.value, new_state.value, trigger
        )

        return self._state

    def should_explore(self) -> bool:
        """Check if idle too long, should trigger curiosity-driven exploration."""
        if self._state != ConsciousnessState.IDLE:
            return False
        return self.seconds_in_state >= self._idle_timeout_seconds

    def get_next_action(self) -> dict:
        """Return suggested action for the current state."""
        actions = {
            ConsciousnessState.IDLE: {"action": "wait", "description": "Waiting for triggers"},
            ConsciousnessState.EXPLORING: {
                "action": "broad_search",
                "description": "Broad literature search across domains",
            },
            ConsciousnessState.FOCUSED: {
                "action": "run_pipeline",
                "description": "Run full pipeline on identified gaps",
            },
            ConsciousnessState.CONTEMPLATING: {
                "action": "analyze_results",
                "description": "Analyze pipeline results and extract insights",
            },
            ConsciousnessState.DREAMING: {
                "action": "consolidate",
                "description": "Consolidate memory and update world model",
            },
        }
        return actions.get(self._state, {"action": "unknown"})
