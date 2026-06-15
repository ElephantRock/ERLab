"""Memory Warm-Start — load lessons from prior runs before a new pipeline run.

Recalls relevant EPISODIC and PROCEDURAL memories from the memory service
and injects them as warm_start_hints into the pipeline context.

Inspired by DeepScientist's memory.search() pattern:
"Search memory before repeating literature search, retries, or user
 questions that local memory may already answer."
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.pipeline.memory.service import MemoryService

logger = logging.getLogger(__name__)


@dataclass
class WarmStartHints:
    """Lessons and hints loaded from prior run memories."""

    lessons: list[str] = field(default_factory=list)
    effective_params: list[str] = field(default_factory=list)
    avoided_directions: list[str] = field(default_factory=list)

    @property
    def total_memories_loaded(self) -> int:
        return len(self.lessons) + len(self.effective_params) + len(self.avoided_directions)

    @property
    def has_hints(self) -> bool:
        return bool(self.lessons or self.effective_params or self.avoided_directions)

    def to_dict(self) -> dict:
        return {
            "lessons": self.lessons,
            "effective_params": self.effective_params,
            "avoided_directions": self.avoided_directions,
            "total_memories_loaded": self.total_memories_loaded,
        }


class WarmStartLoader:
    """Load relevant memories before a pipeline run to warm-start stages."""

    def __init__(self, memory_service: "MemoryService") -> None:
        self._memory = memory_service

    async def load_hints(self, domain: str) -> WarmStartHints:
        """Load warm-start hints for a new run.

        Args:
            domain: Research domain for memory recall.

        Returns:
            WarmStartHints with lessons, effective params, and avoided directions.
        """
        hints = WarmStartHints()

        try:
            from backend.pipeline.memory.models import MemoryQuery, MemoryType

            # Recall pipeline experience lessons (EPISODIC)
            try:
                results = await self._memory.recall(MemoryQuery(
                    query=domain,
                    memory_type=MemoryType.EPISODIC,
                    namespace="pipeline_experience",
                    top_k=5,
                    min_confidence=0.3,
                ))
                hints.lessons = [
                    r.content for r in results if hasattr(r, "content")
                ]
            except Exception as e:
                logger.debug("EPISODIC memory recall failed: %s", e)

            # Recall procedural memories (effective strategies)
            try:
                results = await self._memory.recall(MemoryQuery(
                    query=domain,
                    memory_type=MemoryType.PROCEDURAL,
                    namespace="pipeline_experience",
                    top_k=3,
                    min_confidence=0.3,
                ))
                hints.effective_params = [
                    r.content for r in results if hasattr(r, "content")
                ]
            except Exception as e:
                logger.debug("PROCEDURAL memory recall failed: %s", e)

            # Recall abandoned directions (SEMANTIC)
            try:
                results = await self._memory.recall(MemoryQuery(
                    query=f"{domain} abandoned failed",
                    memory_type=MemoryType.SEMANTIC,
                    namespace="pipeline_experience",
                    top_k=5,
                    min_confidence=0.3,
                ))
                hints.avoided_directions = [
                    r.content for r in results if hasattr(r, "content")
                ]
            except Exception as e:
                logger.debug("SEMANTIC memory recall for abandoned directions failed: %s", e)

        except ImportError:
            logger.debug("Memory models not available — skipping warm-start")
        except Exception as e:
            logger.warning("Warm-start failed (non-fatal): %s", e)

        if hints.has_hints:
            logger.info(
                "Warm-start: loaded %d memories (%d lessons, %d params, %d avoided)",
                hints.total_memories_loaded,
                len(hints.lessons),
                len(hints.effective_params),
                len(hints.avoided_directions),
            )

        return hints
