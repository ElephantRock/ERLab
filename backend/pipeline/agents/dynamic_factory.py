"""Dynamic agent creation — runtime agent factory with LLM-generated role prompts.

Creates and retires agents on-demand based on pipeline stage requirements.
Each specialist agent gets a dynamically generated system prompt tailored
to its stage and context, then is retired after use.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from backend.pipeline.agents.message_bus import MessageBus
    from backend.pipeline.agents.registry import AgentRegistry

logger = logging.getLogger(__name__)

_STAGE_ROLE_SCHEMA = {
    "type": "object",
    "properties": {
        "role_description": {"type": "string"},
        "system_prompt": {"type": "string"},
        "capabilities": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["role_description", "system_prompt", "capabilities"],
}


class DynamicAgentConfig(BaseModel):
    """Configuration for a dynamically created agent."""

    agent_id: str = Field(default_factory=lambda: f"dyn-{uuid.uuid4().hex[:8]}")
    role_description: str = ""
    capabilities: list[str] = Field(default_factory=list)
    system_prompt: str = ""
    temperature: float = 0.5


class DynamicAgentFactory:
    """Creates and retires agents at runtime based on pipeline needs."""

    def __init__(
        self,
        provider: Any,
        registry: AgentRegistry,
        bus: MessageBus | None = None,
        max_agents: int = 5,
    ) -> None:
        self._provider = provider
        self._registry = registry
        self._bus = bus
        self._max_agents = max_agents
        self._active_agents: list[str] = []

    async def create_agent(self, config: DynamicAgentConfig) -> str:
        """Create a dynamic agent from config. Returns agent_id."""
        if len(self._active_agents) >= self._max_agents:
            # Retire oldest agent to make room
            oldest = self._active_agents.pop(0)
            self.retire_agent(oldest)

        from backend.pipeline.negotiation.agent import NegotiationAgent

        agent = NegotiationAgent(
            agent_id=config.agent_id,
            provider=self._provider,
            capabilities=config.capabilities,
            role=config.role_description,
        )

        # Register with routing infrastructure
        handler = self._make_handler(agent)
        self._registry.register(
            agent_id=config.agent_id,
            capabilities=config.capabilities,
            handler=handler,
            metadata={
                "dynamic": True,
                "system_prompt": config.system_prompt,
                "temperature": config.temperature,
            },
        )

        self._active_agents.append(config.agent_id)
        logger.info(
            "Created dynamic agent '%s' with capabilities: %s",
            config.agent_id, config.capabilities,
        )
        return config.agent_id

    async def create_stage_specialist(
        self, stage_name: str, context: str = "",
    ) -> DynamicAgentConfig:
        """Use LLM to generate role prompts for a pipeline stage specialist."""
        try:
            result = await self._provider.structured_output(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You design specialist AI agents for a research pipeline. "
                            "Create an agent configuration for the given pipeline stage."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Pipeline stage: {stage_name}\n"
                            f"Context: {context[:500]}\n\n"
                            "Design a specialist agent for this stage. Provide a "
                            "role description, system prompt, and list of capabilities."
                        ),
                    },
                ],
                schema=_STAGE_ROLE_SCHEMA,
                temperature=0.7,
            )

            return DynamicAgentConfig(
                role_description=result.get("role_description", f"{stage_name} specialist"),
                capabilities=result.get("capabilities", [stage_name]),
                system_prompt=result.get("system_prompt", f"You are a {stage_name} specialist."),
            )
        except Exception as e:
            logger.warning("LLM agent generation failed for stage '%s': %s", stage_name, e)
            return DynamicAgentConfig(
                role_description=f"{stage_name} specialist",
                capabilities=[stage_name],
                system_prompt=f"You are a specialist agent for the {stage_name} pipeline stage.",
            )

    def retire_agent(self, agent_id: str) -> bool:
        """Retire a dynamic agent. Returns True if found."""
        success = self._registry.unregister(agent_id)
        if success:
            self._active_agents = [a for a in self._active_agents if a != agent_id]
            logger.info("Retired dynamic agent '%s'", agent_id)
        return success

    def retire_all(self) -> int:
        """Retire all active dynamic agents. Returns count retired."""
        count = 0
        for agent_id in list(self._active_agents):
            if self.retire_agent(agent_id):
                count += 1
        return count

    @property
    def active_count(self) -> int:
        return len(self._active_agents)

    @staticmethod
    def _make_handler(agent: Any) -> Any:
        """Create a message handler that delegates to the agent's propose method."""
        from backend.pipeline.agents.message_bus import MessageHandler

        class AgentHandler(MessageHandler):
            async def handle(self, message: Any) -> Any:
                if hasattr(agent, 'propose'):
                    return await agent.propose(message.payload if hasattr(message, 'payload') else str(message))
                return None

        return AgentHandler()
