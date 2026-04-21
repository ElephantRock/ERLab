"""Working context manager for in-loop context compression.

Tracks accumulated context within the AgentOrchestrator's multi-round
loop (Ideator → Critic → Refiner) and applies compression between
rounds when token budgets are exceeded.

5-phase compression (from Hermes pattern):
  1. Tool output pruning — truncate long tool results
  2. Head protection — preserve system prompt and first exchanges
  3. Tail protection — preserve most recent exchanges
  4. LLM summarization — summarize the middle section
  5. Sanitize — remove broken JSON or truncated text
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

CHARS_PER_TOKEN = 4
MAX_ACCUMULATED_TOKENS = 20000


class WorkingContext:
    """Tracks and compresses context within the agent loop."""

    def __init__(
        self,
        provider: LLMProvider,
        max_tokens: int = MAX_ACCUMULATED_TOKENS,
    ):
        self._provider = provider
        self._max_tokens = max_tokens

    def estimate_tokens(self, text: str) -> int:
        return len(text) // CHARS_PER_TOKEN

    def check_budget(self, messages: list[dict]) -> bool:
        """Return True if budget is exceeded."""
        total_chars = sum(len(m.get("content", "")) for m in messages)
        return (total_chars // CHARS_PER_TOKEN) > self._max_tokens

    async def compress_if_needed(
        self,
        messages: list[dict],
        round_num: int,
    ) -> list[dict]:
        """Apply compression between agent loop rounds if budget exceeded."""
        if not self.check_budget(messages):
            return messages

        logger.info(
            "WorkingContext: compressing at round %d (%d messages)",
            round_num, len(messages),
        )

        # Phase 1: Prune tool outputs
        messages = self._prune_tool_outputs(messages)
        if not self.check_budget(messages):
            return messages

        # Phases 2-4: Head/tail protection + LLM summarization
        messages = await self._compress_middle(messages)

        # Phase 5: Sanitize
        messages = self._sanitize(messages)

        return messages

    def _prune_tool_outputs(self, messages: list[dict]) -> list[dict]:
        """Phase 1: Truncate tool results longer than 1000 chars."""
        pruned = []
        for m in messages:
            if m.get("role") == "tool" and len(m.get("content", "")) > 1000:
                pruned.append({**m, "content": m["content"][:800] + "\n[...truncated]"})
            else:
                pruned.append(m)
        return pruned

    async def _compress_middle(self, messages: list[dict]) -> list[dict]:
        """Phases 2-4: Keep head and tail, summarize the middle."""
        if len(messages) <= 4:
            return messages

        head = messages[:2]
        tail = messages[-2:]
        middle = messages[2:-2]

        if not middle:
            return messages

        middle_text = "\n\n".join(
            f"[{m.get('role', 'unknown')}]: {m.get('content', '')[:300]}"
            for m in middle
        )

        try:
            summary = await self._provider.complete(
                messages=[{
                    "role": "user",
                    "content": (
                        "Summarize the key information from these previous "
                        "research context exchanges in 2-3 sentences:\n\n"
                        + middle_text
                    ),
                }],
                temperature=0.2,
                max_tokens=200,
            )
        except Exception:
            logger.warning("LLM summarization failed, using simple truncation")
            summary = middle_text[:500]

        summary_msg = {
            "role": "system",
            "content": f"[Previous context summary]: {summary}",
        }

        return head + [summary_msg] + tail

    def _sanitize(self, messages: list[dict]) -> list[dict]:
        """Phase 5: Clean up truncated text and broken formatting."""
        clean = []
        for m in messages:
            content = m.get("content", "")
            if content.count("{") > content.count("}"):
                content = content[:content.rfind("{")]
            clean.append({**m, "content": content})
        return clean
