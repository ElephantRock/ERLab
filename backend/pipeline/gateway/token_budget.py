"""Token budgeting — prevents context overflow before it happens.

The core insight: the pipeline currently discovers context limits by crashing
into LM Studio errors (n_keep >= n_ctx). This module makes that check explicit
and proactive, refusing to send prompts that won't fit.

Usage:
    budgeter = TokenBudgeter(default_context=8192)
    budget = budgeter.check(messages, max_output_tokens=2048, context_window=8192)

    if not budget.fits:
        # Compact or split the prompt
        messages = compiler.compact(messages, budget.available_for_input)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class PromptTooLargeError(Exception):
    """Raised when a prompt exceeds the model's context window.

    Attributes:
        input_tokens: Tokens in the prompt.
        output_reserve: Tokens reserved for the response.
        context_window: Model's total context capacity.
        available: How many input tokens could actually fit.
    """

    def __init__(
        self,
        input_tokens: int,
        output_reserve: int,
        context_window: int,
        available: int,
    ):
        self.input_tokens = input_tokens
        self.output_reserve = output_reserve
        self.context_window = context_window
        self.available = available
        super().__init__(
            f"Prompt ({input_tokens} tokens) + output reserve ({output_reserve}) "
            f"exceeds context ({context_window}). Available for input: {available}"
        )


@dataclass
class TokenBudget:
    """Token budget for a single LLM call."""

    input_tokens: int          # tokens in the prompt
    output_reserve: int        # tokens reserved for the response
    context_window: int        # model's total context capacity
    safety_margin: float = 0.15  # 15% headroom

    @property
    def total_budget(self) -> int:
        """Total usable tokens (context minus safety margin)."""
        return int(self.context_window * (1.0 - self.safety_margin))

    @property
    def fits(self) -> bool:
        """Whether the prompt + output reserve fits within budget."""
        return self.input_tokens + self.output_reserve <= self.total_budget

    @property
    def available_for_input(self) -> int:
        """Max input tokens that could fit given the output reserve."""
        return max(0, self.total_budget - self.output_reserve)

    @property
    def available_for_output(self) -> int:
        """Max output tokens that could fit given the input."""
        return max(0, self.total_budget - self.input_tokens)

    @property
    def overflow_tokens(self) -> int:
        """How many input tokens need to be removed to fit."""
        if self.fits:
            return 0
        return self.input_tokens + self.output_reserve - self.total_budget

    def summary(self) -> str:
        """Human-readable budget summary."""
        status = "OK" if self.fits else "OVERFLOW"
        return (
            f"[{status}] input={self.input_tokens} + output={self.output_reserve} "
            f"vs budget={self.total_budget} (ctx={self.context_window}, "
            f"safety={self.safety_margin:.0%})"
        )


@dataclass
class TokenCount:
    """Result of counting tokens for a message list."""

    total_tokens: int
    message_counts: list[int] = field(default_factory=list)
    method: str = "estimate"  # "exact" | "estimate"


class TokenBudgeter:
    """Pre-flight token budget checker.

    Counts tokens in the prompt, reserves space for the output,
    and checks whether the total fits within the model's context window.

    The safety_margin provides headroom for tokenizer discrepancies,
    special tokens, and system overhead. Default 15% means a model
    with 8192 context gets a usable budget of ~6963 tokens.
    """

    def __init__(
        self,
        default_context: int = 4096,
        default_safety_margin: float = 0.15,
        chars_per_token: float = 3.8,  # conservative for mixed code/text
    ):
        self._default_context = default_context
        self._default_safety_margin = default_safety_margin
        self._chars_per_token = chars_per_token

    def count_tokens(self, messages: list[dict]) -> TokenCount:
        """Count tokens in a message list.

        Uses character-based estimation. For exact counting,
        use the model's tokenizer via TokenCounter (gateway/token_counter.py).

        Estimation formula: total_chars / chars_per_token
        Plus overhead per message (~4 tokens for role tags).
        """
        total_chars = 0
        message_counts: list[int] = []

        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                chars = len(content)
            elif isinstance(content, list):
                # Anthropic-style content blocks
                chars = sum(
                    len(block.get("text", "")) if isinstance(block, dict) else len(str(block))
                    for block in content
                )
            else:
                chars = len(str(content))

            # Estimate tokens for this message: content + overhead
            msg_tokens = int(chars / self._chars_per_token) + 4
            message_counts.append(msg_tokens)
            total_chars += chars

        total_tokens = int(total_chars / self._chars_per_token) + len(messages) * 4

        return TokenCount(
            total_tokens=total_tokens,
            message_counts=message_counts,
            method="estimate",
        )

    def count_text(self, text: str) -> int:
        """Count tokens in a plain string."""
        return int(len(text) / self._chars_per_token)

    def check(
        self,
        messages: list[dict],
        max_output_tokens: int = 4096,
        context_window: int | None = None,
        safety_margin: float | None = None,
    ) -> TokenBudget:
        """Check if a prompt fits within the model's context window.

        Args:
            messages: The message list to check.
            max_output_tokens: Tokens reserved for the response.
            context_window: Model's context capacity. Uses default if None.
            safety_margin: Headroom fraction. Uses default if None.

        Returns:
            TokenBudget with fit status and overflow info.
        """
        ctx = context_window or self._default_context
        margin = safety_margin or self._default_safety_margin

        count = self.count_tokens(messages)

        budget = TokenBudget(
            input_tokens=count.total_tokens,
            output_reserve=max_output_tokens,
            context_window=ctx,
            safety_margin=margin,
        )

        if not budget.fits:
            logger.warning(
                "Prompt too large: %s (%s)",
                budget.summary(),
                f"overflow={budget.overflow_tokens}",
            )

        return budget

    def check_or_raise(
        self,
        messages: list[dict],
        max_output_tokens: int = 4096,
        context_window: int | None = None,
    ) -> TokenBudget:
        """Check budget and raise PromptTooLargeError if it doesn't fit.

        Use this in the gateway to prevent sending oversized prompts.
        """
        budget = self.check(messages, max_output_tokens, context_window)
        if not budget.fits:
            raise PromptTooLargeError(
                input_tokens=budget.input_tokens,
                output_reserve=budget.output_reserve,
                context_window=budget.context_window,
                available=budget.available_for_input,
            )
        return budget

    def recommend_max_output(
        self,
        messages: list[dict],
        context_window: int | None = None,
        safety_margin: float | None = None,
        min_output: int = 256,
    ) -> int:
        """Recommend max_output_tokens given the current prompt.

        If the prompt is too large even for min_output, returns 0
        (prompt must be compacted).
        """
        ctx = context_window or self._default_context
        margin = safety_margin or self._default_safety_margin

        count = self.count_tokens(messages)
        total_budget = int(ctx * (1.0 - margin))
        available = total_budget - count.total_tokens

        if available < min_output:
            return 0
        return available
