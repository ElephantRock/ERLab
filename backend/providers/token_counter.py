"""Token usage tracking across LLM calls within a pipeline stage."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TokenSnapshot:
    """Point-in-time view of accumulated token usage."""

    input_tokens: int = 0
    output_tokens: int = 0
    call_count: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class TokenCounter:
    """Accumulates token usage from provider calls within a scope.

    Typically scoped to a single pipeline stage. Providers call ``record()``
    after each LLM call. The orchestrator calls ``snapshot()`` at stage end
    to feed the budget system, then ``reset()`` for the next stage.
    """

    def __init__(self) -> None:
        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._call_count: int = 0

    def record(self, input_tokens: int, output_tokens: int) -> None:
        """Record token usage from a single LLM call."""
        self._input_tokens += input_tokens
        self._output_tokens += output_tokens
        self._call_count += 1

    def snapshot(self) -> TokenSnapshot:
        """Return accumulated usage without clearing."""
        return TokenSnapshot(
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            call_count=self._call_count,
        )

    def reset(self) -> None:
        """Clear accumulated usage for the next scope."""
        self._input_tokens = 0
        self._output_tokens = 0
        self._call_count = 0
