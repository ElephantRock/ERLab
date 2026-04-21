"""Adapter handlers that wrap Ideator/Critic/Refiner agents into the registry.

Each handler is an async function matching the MessageHandler signature
(`Callable[[AgentMessage], Coroutine[Any, Any, None]]`). The handler
extracts the payload, calls the real agent with isolated context, and
stores the result in `msg.metadata["response"]`.
"""

from __future__ import annotations

import logging
from typing import Any

from jinja2 import Template

from backend.pipeline.agents.message_bus import AgentMessage
from backend.pipeline.agents.registry import AgentRegistry
from backend.pipeline.generation.buffered_taxonomy import BufferedErrorTaxonomy
from backend.pipeline.generation.context_isolator import ContextIsolator
from backend.pipeline.generation.critic_agent import CriticAgent
from backend.pipeline.generation.ideator_agent import IdeatorAgent
from backend.pipeline.generation.refiner_agent import RefinerAgent
from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

# Loaded once, cached
_router_template: Template | None = None


def _load_router_template() -> Template:
    global _router_template
    if _router_template is None:
        from pathlib import Path

        path = Path(__file__).parent / "prompts" / "router_system.md"
        _router_template = Template(path.read_text())
    return _router_template


def make_ideator_handler(
    ideator: IdeatorAgent, isolator: ContextIsolator
) -> Any:
    """Create a handler that calls IdeatorAgent with isolated context."""

    async def handle(msg: AgentMessage) -> None:
        payload = msg.payload
        gap = payload.get("gap")
        n_ideas = payload.get("n_ideas", 3)

        if gap:
            gaps_copy, papers_copy = isolator.isolated_context_for_gap(gap)
        else:
            gaps_copy, papers_copy = isolator.isolated_context()

        ideas = await ideator.generate_ideas(
            gaps=gaps_copy,
            context_papers=papers_copy,
            prior_critique=payload.get("prior_critique"),
            n_ideas=n_ideas,
        )
        msg.metadata["response"] = ideas

    return handle


def make_critic_handler(
    critic: CriticAgent, isolator: ContextIsolator
) -> tuple[Any, BufferedErrorTaxonomy]:
    """Create a handler that calls CriticAgent with buffered taxonomy.

    Returns (handler, buffered_taxonomy) so the caller can flush later.
    """
    buffered = BufferedErrorTaxonomy(critic._error_taxonomy)
    original_taxonomy = critic._error_taxonomy
    critic._error_taxonomy = buffered

    async def handle(msg: AgentMessage) -> None:
        payload = msg.payload
        _, papers_copy = isolator.isolated_context()

        ideas = payload.get("ideas", [])
        critiques = await critic.critique_ideas(
            ideas=ideas,
            context_papers=papers_copy,
            strategy=payload.get("strategy"),
        )
        msg.metadata["response"] = critiques

    def restore() -> None:
        critic._error_taxonomy = original_taxonomy
        buffered.flush()

    return handle, buffered, restore


def make_refiner_handler(
    refiner: RefinerAgent, isolator: ContextIsolator
) -> Any:
    """Create a handler that calls RefinerAgent with isolated context."""

    async def handle(msg: AgentMessage) -> None:
        payload = msg.payload
        _, papers_copy = isolator.isolated_context()

        ideas = payload.get("ideas", [])
        critiques = payload.get("critiques", [])
        round_num = payload.get("round_num", 1)

        refined = await refiner.refine_ideas(
            ideas=ideas,
            critiques=critiques,
            context_papers=papers_copy,
            round_num=round_num,
        )
        msg.metadata["response"] = refined

    return handle


def make_router_handler(provider: LLMProvider) -> Any:
    """Create a handler that classifies gap complexity via LLM."""

    async def handle(msg: AgentMessage) -> None:
        payload = msg.payload
        gap = payload.get("gap", payload)

        title = getattr(gap, "title", str(gap))
        description = getattr(gap, "description", "")
        gap_type = getattr(gap, "gap_type", "")
        impact = getattr(gap, "potential_impact", "")

        tmpl = _load_router_template()
        prompt = tmpl.render(
            title=title,
            description=description,
            gap_type=gap_type,
            potential_impact=impact,
        )

        result = await provider.structured_output(
            messages=[{"role": "user", "content": prompt}],
            schema={
                "type": "object",
                "properties": {
                    "complexity": {"type": "string", "enum": ["simple", "complex"]},
                    "reason": {"type": "string"},
                },
                "required": ["complexity"],
            },
            temperature=0.1,
        )

        # Annotate the original payload with route info
        if isinstance(payload, dict):
            payload["_route"] = result.get("complexity", "complex")
        else:
            payload.__dict__["_route"] = result.get("complexity", "complex")

        msg.metadata["response"] = payload

    return handle


def register_all_agents(
    registry: AgentRegistry,
    agents: dict[str, Any],
    isolator: ContextIsolator,
    provider: LLMProvider,
) -> list[tuple[Any, BufferedErrorTaxonomy, Any]]:
    """Register all DAG agents with their adapter handlers.

    Returns list of (handler, buffered_taxonomy, restore_fn) for cleanup.
    """
    cleanup: list[tuple[Any, BufferedErrorTaxonomy, Any]] = []

    ideator = agents.get("ideator")
    if ideator:
        registry.register(
            agent_id="dag_ideator",
            capabilities=["ideator"],
            handler=make_ideator_handler(ideator, isolator),
        )

    critic = agents.get("critic")
    if critic:
        handler, buffered, restore = make_critic_handler(critic, isolator)
        registry.register(
            agent_id="dag_critic",
            capabilities=["critic"],
            handler=handler,
        )
        cleanup.append((handler, buffered, restore))

    refiner = agents.get("refiner")
    if refiner:
        registry.register(
            agent_id="dag_refiner",
            capabilities=["refiner"],
            handler=make_refiner_handler(refiner, isolator),
        )

    registry.register(
        agent_id="dag_router",
        capabilities=["router"],
        handler=make_router_handler(provider),
    )

    return cleanup
