"""LLM-driven memory consolidation — dual-pass ADD/UPDATE/DELETE decision loop."""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel

from backend.pipeline.memory.models import MemoryEntry

if TYPE_CHECKING:
    from backend.pipeline.memory.service import MemoryService
    from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

CONSOLIDATION_PROMPT = """Compare this new fact against existing memories and decide what to do.

## New Fact:
{new_content}

## Existing Similar Memories:
{existing_text}

Decide one action:
- ADD: The new fact is novel and not covered by existing memories
- UPDATE: An existing memory should be updated with this new information (provide updated content)
- DELETE: An existing memory is superseded and should be removed
- SKIP: The new fact is a duplicate or lower quality than existing

Respond with JSON: {{"action": "ADD|UPDATE|DELETE|SKIP", "existing_id": "id_or_null", "new_content": "updated_content_or_null", "reason": "brief explanation", "confidence": 0.0-1.0}}"""


class ConsolidationAction(str, Enum):
    ADD = "ADD"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    SKIP = "SKIP"


class ConsolidationDecision(BaseModel):
    action: ConsolidationAction = ConsolidationAction.SKIP
    existing_id: str | None = None
    new_content: str | None = None
    reason: str = ""
    confidence: float = 0.0


class LLMConsolidator:
    """Dual-pass LLM consolidation: embedding similarity + LLM decision."""

    def __init__(
        self,
        provider: LLMProvider,
        similarity_threshold: float = 0.9,
    ) -> None:
        self._provider = provider
        self._similarity_threshold = similarity_threshold

    async def consolidate_entry(
        self,
        new_entry: MemoryEntry,
        existing_entries: list[MemoryEntry],
    ) -> ConsolidationDecision:
        """Compare a new entry against existing ones and decide action."""
        if not existing_entries:
            return ConsolidationDecision(
                action=ConsolidationAction.ADD,
                reason="No existing entries to compare",
                confidence=1.0,
            )

        # Pass 1: Find similar candidates via text overlap
        candidates = self._pass_1_find_similar(new_entry.content, existing_entries)

        if not candidates:
            return ConsolidationDecision(
                action=ConsolidationAction.ADD,
                reason="No similar existing entries found",
                confidence=0.8,
            )

        # Pass 2: LLM decides among candidates
        return await self._pass_2_decide(new_entry, candidates)

    def _pass_1_find_similar(
        self,
        new_content: str,
        existing: list[MemoryEntry],
    ) -> list[MemoryEntry]:
        """Find similar entries using word overlap (Jaccard similarity)."""
        new_words = set(new_content.lower().split())
        if not new_words:
            return []

        candidates = []
        for entry in existing:
            existing_words = set(entry.content.lower().split())
            if not existing_words:
                continue
            similarity = len(new_words & existing_words) / len(new_words | existing_words)
            if similarity >= self._similarity_threshold:
                candidates.append(entry)

        return candidates[:5]  # Top 5 candidates

    async def _pass_2_decide(
        self,
        new_entry: MemoryEntry,
        candidates: list[MemoryEntry],
    ) -> ConsolidationDecision:
        """LLM call to decide ADD/UPDATE/DELETE among candidates."""
        existing_text = "\n".join(
            f"- [{c.id}] {c.content[:200]} (confidence={c.truth.confidence:.2f})"
            for c in candidates
        )

        prompt = CONSOLIDATION_PROMPT.format(
            new_content=new_entry.content[:300],
            existing_text=existing_text,
        )

        try:
            result = await self._provider.structured_output(
                messages=[
                    {"role": "system", "content": "You are a memory consolidation agent."},
                    {"role": "user", "content": prompt},
                ],
                schema={
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "existing_id": {"type": ["string", "null"]},
                        "new_content": {"type": ["string", "null"]},
                        "reason": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["action"],
                },
                temperature=0.1,
            )

            action_str = result.get("action", "SKIP").upper()
            try:
                action = ConsolidationAction(action_str)
            except ValueError:
                action = ConsolidationAction.SKIP

            return ConsolidationDecision(
                action=action,
                existing_id=result.get("existing_id"),
                new_content=result.get("new_content"),
                reason=result.get("reason", ""),
                confidence=min(1.0, max(0.0, result.get("confidence", 0.5))),
            )
        except Exception as e:
            logger.warning("Consolidation LLM call failed: %s — defaulting to ADD", e)
            return ConsolidationDecision(
                action=ConsolidationAction.ADD,
                reason=f"LLM call failed: {e}",
                confidence=0.3,
            )

    async def run_consolidation_sweep(
        self,
        memory: MemoryService,
        batch_size: int = 20,
    ) -> dict:
        """Periodic sweep of unconsolidated entries. Returns summary stats."""
        entries = list(memory._index.values())
        if not entries:
            return {"scanned": 0, "adds": 0, "updates": 0, "deletes": 0, "skips": 0}

        stats = {"scanned": 0, "adds": 0, "updates": 0, "deletes": 0, "skips": 0}

        for i in range(0, min(len(entries), batch_size)):
            entry = entries[i]
            others = [e for e in entries if e.id != entry.id]
            decision = await self.consolidate_entry(entry, others)
            stats["scanned"] += 1
            stats[decision.action.value.lower() + "s"] = stats.get(decision.action.value.lower() + "s", 0) + 1

            if decision.action == ConsolidationAction.DELETE and decision.existing_id:
                await memory.delete(decision.existing_id)

        return stats
