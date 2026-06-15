"""Abstract base class for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass
class LLMResponse:
    """Wraps LLM output with token usage metadata."""

    content: str
    structured: dict | None = None
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class CostEvent:
    """A single cost event from an LLM call."""

    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float = 0.0
    stage: str = ""
    run_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


# Type alias for the cost callback
CostCallback = Callable[[CostEvent], None]


class LLMProvider(ABC):
    """Interface that all LLM providers must implement."""

    def __init__(self) -> None:
        self._cost_callback: CostCallback | None = None

    def set_cost_callback(self, callback: CostCallback) -> None:
        """Register a callback to record cost events after each LLM call."""
        self._cost_callback = callback

    def _report_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        stage: str = "",
        run_id: str | None = None,
    ) -> None:
        """Fire cost callback if registered."""
        if self._cost_callback is None:
            return
        event = CostEvent(
            provider=self.provider_name,
            model=self.default_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            stage=stage,
            run_id=run_id,
        )
        self._cost_callback(event)

    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Single-shot completion. Returns the assistant message text."""
        ...

    async def complete_with_usage(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stage: str = "",
        run_id: str | None = None,
    ) -> LLMResponse:
        """Same as complete() but returns token usage and reports cost."""
        text = await self.complete(messages, temperature, max_tokens)
        return LLMResponse(content=text)

    @abstractmethod
    def complete_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Streaming completion. Yields chunks of assistant message text."""
        ...

    @abstractmethod
    async def structured_output(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict:
        """Return a JSON object conforming to the given JSON schema."""
        ...

    async def structured_output_with_usage(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
        stage: str = "",
        run_id: str | None = None,
    ) -> LLMResponse:
        """Same as structured_output() but returns token usage and reports cost."""
        result = await self.structured_output(messages, schema, temperature)
        return LLMResponse(content="", structured=result)

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        ...

    def model_info(self) -> dict[str, Any]:
        """Return model metadata. Providers can override for richer info."""
        return {
            "provider": self.provider_name,
            "model": self.default_model,
        }

    async def complete_with_tools(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        stage: str = "",
    ) -> LLMResponse:
        """Completion with tool-calling support.

        Returns LLMResponse where structured={"tool_calls": [...]} if the
        model chose to call tools, None otherwise.
        """
        raise NotImplementedError(
            f"{self.provider_name} does not implement complete_with_tools()"
        )

    async def health_check(self) -> bool:
        """Verify the provider is reachable and API key is valid."""
        try:
            await self.complete(
                [{"role": "user", "content": "ping"}], max_tokens=1
            )
            return True
        except Exception:
            return False
