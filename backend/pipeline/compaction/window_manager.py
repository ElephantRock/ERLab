"""ContextWindowManager — unified context tracking with fraction-based triggers and offload."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.pipeline.compaction.model_profiles import get_context_size, get_trigger_threshold
from backend.pipeline.compaction.offload import ContextOffloadStore


def _get_fallback_model() -> str:
    """Read compaction fallback model from settings."""
    try:
        from backend.config import get_settings
        return get_settings().compaction_fallback_model
    except Exception:
        return "gpt-4o"

if TYPE_CHECKING:
    from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

CHARS_PER_TOKEN = 4


class ContextWindowManager:
    """Tracks cumulative token usage per run against model context window.

    Compresses at a fraction-based threshold (e.g., 85%) with tool output
    truncation and filesystem offload for evicted context.
    """

    def __init__(
        self,
        provider: LLMProvider,
        trigger_fraction: float = 0.85,
        offload_dir: str = "./data/context_offload",
        max_tool_output_chars: int = 2000,
    ) -> None:
        self._provider = provider
        self._trigger_fraction = trigger_fraction
        self._offload = ContextOffloadStore(offload_dir)
        self._max_tool_output_chars = max_tool_output_chars
        self._compressions_done = 0
        self._offloads_done = 0

    def check_and_compress(
        self,
        messages: list[dict],
        model_name: str | None = None,
        run_id: str | None = None,
    ) -> list[dict]:
        """Main entry: check budget and compress if triggered."""
        model = model_name or getattr(self._provider, "default_model", _get_fallback_model())
        context_size = get_context_size(model)
        threshold = get_trigger_threshold(model, self._trigger_fraction)

        current_tokens = self._estimate_total_tokens(messages)

        if current_tokens <= threshold:
            return messages

        logger.info(
            "Context budget exceeded: %d tokens > %d threshold (%.0f%% of %d). Compressing.",
            current_tokens, threshold, self._trigger_fraction * 100, context_size,
        )

        # Phase 1: truncate large tool outputs
        messages = self._truncate_tool_outputs(messages)
        current_tokens = self._estimate_total_tokens(messages)

        if current_tokens <= threshold:
            self._compressions_done += 1
            return messages

        # Phase 2: offload middle messages to filesystem
        if run_id and len(messages) > 4:
            head = messages[:2]
            tail = messages[-2:]
            middle = messages[2:-2]

            if middle:
                self._offload.save(run_id, self._offloads_done, middle)
                self._offloads_done += 1
                summary_msg = {
                    "role": "system",
                    "content": f"[{len(middle)} messages offloaded to context store]",
                }
                messages = head + [summary_msg] + tail

        self._compressions_done += 1
        return messages

    def recover_offloaded(self, run_id: str) -> list[dict]:
        """Load previously offloaded context for a run."""
        return self._offload.load(run_id)

    def cleanup(self, run_id: str) -> int:
        """Delete offloaded data for a completed run."""
        return self._offload.delete(run_id)

    def get_usage_report(self, messages: list[dict], model_name: str | None = None) -> dict:
        """Return current context utilization."""
        model = model_name or getattr(self._provider, "default_model", _get_fallback_model())
        context_size = get_context_size(model)
        current = self._estimate_total_tokens(messages)
        return {
            "current_tokens": current,
            "context_size": context_size,
            "utilization_pct": round(current / max(1, context_size) * 100, 1),
            "compressions_done": self._compressions_done,
            "offloads_done": self._offloads_done,
        }

    @staticmethod
    def _estimate_total_tokens(messages: list[dict]) -> int:
        total_chars = sum(len(m.get("content", "")) for m in messages)
        return total_chars // CHARS_PER_TOKEN

    @staticmethod
    def _should_trigger(current_tokens: int, context_size: int, fraction: float) -> bool:
        return current_tokens > int(context_size * fraction)

    def _truncate_tool_outputs(self, messages: list[dict]) -> list[dict]:
        """Truncate tool/function outputs that exceed max chars."""
        truncated = []
        for m in messages:
            role = m.get("role", "")
            content = m.get("content", "")
            if role in ("tool", "function") and len(content) > self._max_tool_output_chars:
                truncated.append({
                    **m,
                    "content": content[:self._max_tool_output_chars] + "\n[...truncated]",
                })
            else:
                truncated.append(m)
        return truncated
