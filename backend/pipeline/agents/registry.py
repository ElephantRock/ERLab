"""Agent registry with capability advertisement.

Agents register their capabilities (e.g., "ideation", "critique", "retrieval")
and the registry enables dynamic discovery and assignment.

Reference: agentscope agent registry with MCP toolkit, agent-orchestrator 8-slot plugins.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from backend.pipeline.agents.message_bus import MessageBus, MessageHandler

logger = logging.getLogger(__name__)


@dataclass
class AgentDescriptor:
    """Describes an agent's identity and capabilities."""

    agent_id: str
    capabilities: list[str]
    handler: MessageHandler | None = None
    metadata: dict = field(default_factory=dict)


class AgentRegistry:
    """Registry for agent discovery and capability-based routing."""

    def __init__(self, message_bus: MessageBus | None = None):
        self._agents: dict[str, AgentDescriptor] = {}
        self._capability_index: dict[str, list[str]] = {}  # capability -> [agent_ids]
        self._bus = message_bus

    def register(
        self,
        agent_id: str,
        capabilities: list[str],
        handler: MessageHandler | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Register an agent with its capabilities."""
        desc = AgentDescriptor(
            agent_id=agent_id,
            capabilities=capabilities,
            handler=handler,
            metadata=metadata or {},
        )
        self._agents[agent_id] = desc

        for cap in capabilities:
            if cap not in self._capability_index:
                self._capability_index[cap] = []
            self._capability_index[cap].append(agent_id)

        # Auto-subscribe to message bus if handler provided
        if handler and self._bus:
            for cap in capabilities:
                self._bus.subscribe(agent_id, cap, handler)
            self._bus.subscribe(agent_id, f"direct:{agent_id}", handler)

        logger.info(
            "Registered agent '%s' with capabilities: %s",
            agent_id,
            capabilities,
        )

    def unregister(self, agent_id: str) -> bool:
        """Remove an agent from the registry."""
        desc = self._agents.pop(agent_id, None)
        if not desc:
            return False

        for cap in desc.capabilities:
            if cap in self._capability_index:
                self._capability_index[cap] = [
                    aid for aid in self._capability_index[cap] if aid != agent_id
                ]
                if not self._capability_index[cap]:
                    del self._capability_index[cap]

        if desc.handler and self._bus:
            for cap in desc.capabilities:
                self._bus.unsubscribe(agent_id, cap)

        return True

    def discover(self, capability: str) -> list[AgentDescriptor]:
        """Find all agents with a given capability."""
        agent_ids = self._capability_index.get(capability, [])
        return [self._agents[aid] for aid in agent_ids if aid in self._agents]

    def get(self, agent_id: str) -> AgentDescriptor | None:
        """Get an agent descriptor by ID."""
        return self._agents.get(agent_id)

    def get_handler(self, agent_id: str) -> MessageHandler | None:
        """Get an agent's message handler."""
        desc = self._agents.get(agent_id)
        return desc.handler if desc else None

    def all_capabilities(self) -> list[str]:
        """Return all registered capabilities."""
        return list(self._capability_index.keys())

    @property
    def agent_count(self) -> int:
        return len(self._agents)
