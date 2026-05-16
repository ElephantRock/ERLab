"""Token counting utilities for the LLM gateway.

Provides both exact counting (when tokenizer available) and estimation.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Conservative defaults for character-to-token estimation
_CHARS_PER_TOKEN: dict[str, float] = {
    "default": 3.8,
    "code": 3.2,       # code is denser
    "prose": 4.0,      # prose is sparser
    "markdown": 3.6,   # markdown has formatting overhead
}


def count_tokens_text(text: str, chars_per_token: float = 3.8) -> int:
    """Estimate token count for a plain string.

    Uses character-based estimation. For exact counting, use the
    model's native tokenizer.
    """
    return max(1, int(len(text) / chars_per_token))


def count_tokens_messages(
    messages: list[dict],
    chars_per_token: float = 3.8,
) -> int:
    """Estimate token count for a message list.

    Includes per-message overhead (~4 tokens for role tags, separators).
    Handles both OpenAI and Anthropic message formats.
    """
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += int(len(content) / chars_per_token)
        elif isinstance(content, list):
            # Anthropic content blocks
            for block in content:
                if isinstance(block, dict):
                    total += int(len(block.get("text", "")) / chars_per_token)
                    # Tool use / results have extra overhead
                    if block.get("type") in ("tool_use", "tool_result"):
                        total += 20
                else:
                    total += int(len(str(block)) / chars_per_token)
        else:
            total += int(len(str(content)) / chars_per_token)

        # Per-message overhead: role, separators, etc.
        total += 4

    return total


def count_tokens_anthropic_messages(
    messages: list[dict],
    system_prompt: str | None = None,
    chars_per_token: float = 3.8,
) -> int:
    """Estimate tokens for Anthropic-format messages including system prompt.

    Anthropic's API counts system prompt separately from messages.
    """
    total = count_tokens_messages(messages, chars_per_token)

    if system_prompt:
        total += int(len(system_prompt) / chars_per_token) + 4

    # Anthropic message envelope overhead
    total += 10

    return total
