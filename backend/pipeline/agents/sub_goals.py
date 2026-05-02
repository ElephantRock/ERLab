"""Sub-goal decomposition — breaks pipeline stages into smaller executable goals.

Uses LLM to decompose complex stages into prioritized sub-tasks, then
dispatches each to a dynamically created specialist agent. Results are
collected and merged back into the pipeline context.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from backend.pipeline.agents.dynamic_factory import DynamicAgentFactory

logger = logging.getLogger(__name__)

_DECOMPOSE_SCHEMA = {
    "type": "object",
    "properties": {
        "sub_goals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "priority": {"type": "integer"},
                    "required_capabilities": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["description", "priority", "required_capabilities"],
            },
        },
    },
    "required": ["sub_goals"],
}


class SubGoal(BaseModel):
    """A decomposed sub-task within a pipeline stage."""

    goal_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    description: str = ""
    parent_stage: str = ""
    priority: int = 1
    required_capabilities: list[str] = Field(default_factory=list)


class SubGoalGenerator:
    """Decomposes pipeline stages into executable sub-goals."""

    def __init__(self, provider: Any, factory: DynamicAgentFactory) -> None:
        self._provider = provider
        self._factory = factory

    async def decompose_stage(
        self, stage_name: str, context: str = "",
    ) -> list[SubGoal]:
        """Use LLM to decompose a stage into prioritized sub-goals."""
        try:
            result = await self._provider.structured_output(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a task decomposition specialist. Break down "
                            "pipeline stages into concrete, prioritized sub-tasks. "
                            "Each sub-task should have clear required capabilities."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Stage: {stage_name}\n"
                            f"Context: {context[:500]}\n\n"
                            "Decompose this stage into 2-5 sub-goals."
                        ),
                    },
                ],
                schema=_DECOMPOSE_SCHEMA,
                temperature=0.5,
            )

            goals = []
            for sg in result.get("sub_goals", []):
                goals.append(SubGoal(
                    parent_stage=stage_name,
                    description=sg.get("description", ""),
                    priority=sg.get("priority", 1),
                    required_capabilities=sg.get("required_capabilities", [stage_name]),
                ))

            goals.sort(key=lambda g: g.priority, reverse=True)
            logger.info(
                "Decomposed stage '%s' into %d sub-goals",
                stage_name, len(goals),
            )
            return goals
        except Exception as e:
            logger.warning("Sub-goal decomposition failed for '%s': %s", stage_name, e)
            return []

    async def execute_sub_goals(
        self, goals: list[SubGoal], ctx: Any = None,
    ) -> dict[str, Any]:
        """Create specialist agents for each sub-goal and execute them."""
        results: dict[str, Any] = {}
        created_agents: list[str] = []

        for goal in goals:
            # Create a specialist for this sub-goal
            config = await self._factory.create_stage_specialist(
                stage_name=f"{goal.parent_stage}:{goal.goal_id}",
                context=goal.description,
            )
            agent_id = await self._factory.create_agent(config)
            created_agents.append(agent_id)

            # Record that the agent was assigned
            results[goal.goal_id] = {
                "agent_id": agent_id,
                "description": goal.description,
                "status": "assigned",
            }

        # Clean up all created agents
        for agent_id in created_agents:
            self._factory.retire_agent(agent_id)

        logger.info(
            "Executed %d sub-goals, created and retired %d agents",
            len(goals), len(created_agents),
        )
        return results
