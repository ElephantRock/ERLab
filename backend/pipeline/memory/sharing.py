"""Cross-agent memory sharing with tagged attribution.

SharedKnowledgeBase provides a shared namespace where agents can publish
discoveries and subscribe to knowledge from other agents.

Reference: coda shared vector KB with tagged agent attribution.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.pipeline.knowledge.truth import TruthValue
from backend.pipeline.memory.models import MemoryEntry, MemoryQuery, MemoryRevision, MemoryType

if TYPE_CHECKING:
    from backend.pipeline.agents.message_bus import MessageBus
    from backend.pipeline.memory.tiers import TieredMemoryService

logger = logging.getLogger(__name__)

SHARED_NAMESPACE = "__shared__"


class MemoryConflictResolver:
    """Resolves conflicts when multiple agents write contradictory knowledge."""

    def __init__(self, strategy: str = "highest_confidence"):
        self._strategy = strategy

    def resolve(
        self,
        existing: MemoryEntry,
        incoming: MemoryEntry,
    ) -> MemoryEntry:
        """Resolve a conflict between existing and incoming entries.

        Returns the winning entry. The losing entry is recorded in the
        winner's revision_history for provenance.
        """
        if self._strategy == "newest_wins":
            winner, loser = (incoming, existing) if True else (existing, incoming)
        elif self._strategy == "merge":
            return self._merge(existing, incoming)
        else:  # highest_confidence (default)
            if incoming.truth.confidence > existing.truth.confidence:
                winner, loser = incoming, existing
            else:
                winner, loser = existing, incoming

        # Record provenance
        if winner is incoming:
            revision = MemoryRevision(
                revision_number=len(existing.revision_history) + 1,
                content=existing.content,
                truth=existing.truth,
                agent_id=existing.agent_id,
                reason="conflict_resolution:replaced_by_higher_confidence",
            )
            incoming.revision_history = existing.revision_history + [revision]
        return winner

    def _merge(self, existing: MemoryEntry, incoming: MemoryEntry) -> MemoryEntry:
        """Merge: combine tags, revise truth, keep higher-confidence content."""
        merged_truth = existing.truth.revise(incoming.truth)
        merged_tags = list(set(existing.tags + incoming.tags))
        winner_content = incoming.content if incoming.truth.confidence > existing.truth.confidence else existing.content

        revision = MemoryRevision(
            revision_number=len(existing.revision_history) + 1,
            content=existing.content,
            truth=existing.truth,
            agent_id=existing.agent_id,
            reason="conflict_resolution:merge",
        )

        return MemoryEntry(
            id=existing.id,
            content=winner_content,
            memory_type=existing.memory_type,
            namespace=existing.namespace,
            agent_id=existing.agent_id,
            truth=merged_truth,
            tags=merged_tags,
            created_at=existing.created_at,
            access_count=existing.access_count,
            revision_history=existing.revision_history + [revision],
        )


class SharedKnowledgeBase:
    """Shared memory with tagged agent attribution.

    Agents publish to a shared namespace with their agent_id tag.
    Other agents subscribe and read from the shared namespace.
    Private namespaces remain isolated.
    """

    def __init__(
        self,
        memory: TieredMemoryService,
        conflict_strategy: str = "highest_confidence",
    ):
        self._memory = memory
        self._conflict_resolver = MemoryConflictResolver(conflict_strategy)

    async def publish(
        self,
        content: str,
        agent_id: str,
        memory_type: MemoryType = MemoryType.SEMANTIC,
        tags: list[str] | None = None,
        truth: TruthValue | None = None,
    ) -> str:
        """Publish knowledge to the shared namespace."""
        entry = MemoryEntry(
            id="",  # Will be set by content hash in store
            content=content,
            memory_type=memory_type,
            namespace=SHARED_NAMESPACE,
            truth=truth or TruthValue.from_observation(),
            tags=(tags or []) + [f"agent:{agent_id}"],
        )
        return await self._memory.store(entry, tier="archival")  # type: ignore[arg-type]

    async def subscribe(
        self,
        agent_id: str | None = None,
        query: str = "",
        memory_type: MemoryType | None = None,
        top_k: int = 10,
    ) -> list[MemoryEntry]:
        """Read from shared namespace, optionally filtered by source agent."""
        memory_query = MemoryQuery(
            query=query,
            memory_type=memory_type,
            namespace=SHARED_NAMESPACE,
            top_k=top_k * 2,  # Overfetch for agent filtering
        )
        results = await self._memory.recall(memory_query)

        # Filter by source agent if specified
        if agent_id:
            agent_tag = f"agent:{agent_id}"
            results = [r for r in results if agent_tag in r.tags]

        return results[:top_k]

    async def get_shared_count(self) -> int:
        """Count entries in the shared namespace."""
        all_entries = await self._memory.recall(
            MemoryQuery(
                query="",
                namespace=SHARED_NAMESPACE,
                top_k=10000,
            )
        )
        return len(all_entries)


class SharedMemoryBridge:
    """Bridges MessageBus pub-sub to SharedKnowledgeBase.

    When an agent publishes to the MessageBus on the 'shared_knowledge' topic,
    this bridge automatically publishes to the SharedKnowledgeBase.
    """

    def __init__(
        self,
        shared_kb: SharedKnowledgeBase,
        message_bus: MessageBus,
    ):
        self._kb = shared_kb
        self._bus = message_bus
        self._bus.subscribe(
            "__shared_memory_bridge__",
            "shared_knowledge",
            self._on_message,
        )

    async def _on_message(self, message: AgentMessage) -> None:
        """Handle incoming bus messages by publishing to shared KB."""
        payload = message.payload if isinstance(message.payload, dict) else {}
        content = payload.get("content", "")
        agent_id = payload.get("agent_id", message.sender_id)
        memory_type_str = payload.get("memory_type", "semantic")
        try:
            memory_type = MemoryType(memory_type_str)
        except ValueError:
            memory_type = MemoryType.SEMANTIC
        await self._kb.publish(
            content=content,
            agent_id=agent_id,
            memory_type=memory_type,
            tags=payload.get("tags"),
        )

    async def notify(
        self,
        content: str,
        agent_id: str,
        memory_type: MemoryType = MemoryType.SEMANTIC,
        tags: list[str] | None = None,
    ) -> str:
        """Publish to shared KB and notify bus subscribers."""
        from backend.pipeline.agents.message_bus import AgentMessage

        entry_id = await self._kb.publish(content, agent_id, memory_type, tags)
        await self._bus.publish(AgentMessage(
            message_type="shared_knowledge",
            payload={
                "content": content,
                "agent_id": agent_id,
                "memory_type": memory_type.value,
                "tags": tags,
                "entry_id": entry_id,
            },
            sender_id=agent_id,
        ))
        return entry_id
