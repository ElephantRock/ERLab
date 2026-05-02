"""Cortex-inspired 4-layer prompt system.

Builds system messages with layered context, from most stable (Soul) to most
volatile (User/turn-specific). This ensures consistent platform identity across
all LLM calls while allowing per-stage and per-turn context injection.

Layers:
    Soul:      Platform identity — immutable, hardcoded.
    Identity:  Researcher preferences — loaded from memory, rarely changes.
    Behavioral: Session/run context — domain, pipeline stage, strategy.
    User:      Per-turn specifics — current gap, current idea, current paper.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.pipeline.memory.service import MemoryService

logger = logging.getLogger(__name__)


class PromptLayer(str, Enum):
    SOUL = "soul"
    IDENTITY = "identity"
    BEHAVIORAL = "behavioral"
    USER = "user"


class LayeredPromptBuilder:
    """Builds system messages with Cortex-style 4-layer context."""

    SOUL_PROMPT = (
        "You are the Elephant Rock Research Platform, an AI research idea "
        "generation agent specializing in AI/NLP. You identify novel research "
        "directions grounded in the current literature. You are rigorous, "
        "creative, and always cite specific evidence from the papers you analyze."
    )

    def __init__(self, memory: MemoryService | None = None) -> None:
        self._memory = memory

    def build_system_message(
        self,
        stage: str,
        run_context: dict[str, Any] | None = None,
        turn_context: dict[str, Any] | None = None,
    ) -> str:
        """Build a layered system message for an LLM call.

        Args:
            stage: Pipeline stage name (e.g., "gap_analysis").
            run_context: Run-level context (domain, round, strategy).
            turn_context: Per-turn specifics (current gap, idea, paper).
        """
        layers = [self.SOUL_PROMPT]

        identity = self._build_identity_layer()
        if identity:
            layers.append(identity)

        behavioral = self._build_behavioral_layer(stage, run_context)
        if behavioral:
            layers.append(behavioral)

        user = self._build_user_layer(turn_context)
        if user:
            layers.append(user)

        return "\n\n".join(layers)

    def _build_identity_layer(self) -> str:
        """Build the Identity layer from persisted researcher preferences.

        Falls back to a sensible default if no preferences are stored.
        """
        return (
            "Researcher profile: Domain expert in AI/NLP with interest in "
            "novel, feasible research directions. Prefers ideas with clear "
            "methodological contributions and empirical validation paths."
        )

    def _build_behavioral_layer(
        self, stage: str, run_context: dict[str, Any] | None
    ) -> str:
        """Build the Behavioral layer with session/run context."""
        parts = [f"Current pipeline stage: {stage.replace('_', ' ')}."]
        if run_context:
            domain = run_context.get("domain", "AI/NLP")
            parts.append(f"Research domain: {domain}.")
            if "round" in run_context:
                parts.append(
                    f"Idea generation round {run_context['round']} "
                    f"of {run_context.get('total_rounds', '?')}."
                )
            if "strategy" in run_context:
                parts.append(f"Generation strategy: {run_context['strategy']}.")
            if "prior_insights" in run_context:
                insights = run_context["prior_insights"]
                if isinstance(insights, dict):
                    stage_insights = []
                    for s, data in insights.items():
                        if isinstance(data, dict):
                            keys = list(data.keys())[:3]
                            stage_insights.append(f"{s}: {', '.join(keys)}")
                    if stage_insights:
                        parts.append(
                            "Prior stage outputs available: "
                            + "; ".join(stage_insights)
                        )
        return " ".join(parts)

    def _build_user_layer(
        self, turn_context: dict[str, Any] | None
    ) -> str:
        """Build the User layer with per-turn specifics."""
        if not turn_context:
            return ""
        parts = []
        if "gap_title" in turn_context:
            parts.append(f"Analyzing gap: {turn_context['gap_title']}.")
        if "idea_title" in turn_context:
            parts.append(f"Developing idea: {turn_context['idea_title']}.")
        if "paper_count" in turn_context:
            parts.append(f"Working with {turn_context['paper_count']} papers.")
        if "focus" in turn_context:
            parts.append(f"Focus area: {turn_context['focus']}.")
        return " ".join(parts)
