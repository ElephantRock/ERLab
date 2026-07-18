"""Abstract base class for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from backend.pipeline.operations.types import ModelReceipt


@dataclass
class LLMResponse:
    """Wraps LLM output with token usage metadata.

    ``served_model`` is a compatibility field that allows the conformance
    layer to extract receipt information from provider responses during
    migration. The real conformance unit is ``ModelReceipt``, not this field.
    """

    content: str
    structured: dict | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    served_model: str | None = None

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
        self._last_receipt: ModelReceipt | None = None

    @property
    def last_receipt(self) -> ModelReceipt | None:
        """Receipt from the most recent model-backed call, or None."""
        return self._last_receipt

    def _set_receipt_from_response(
        self,
        served_model: str,
        endpoint: str = "",
        context_length: int | None = None,
    ) -> None:
        """Build and store a ModelReceipt after a successful API call.

        Called by concrete providers after each complete()/structured_output()
        call that returns a response containing the served model identity.
        """
        from datetime import datetime, timezone

        self._last_receipt = ModelReceipt(
            requested_model=self.default_model,
            served_model=served_model,
            provider=self.provider_name,
            endpoint=endpoint,
            timestamp=datetime.now(timezone.utc).isoformat(),
            context_length=context_length,
        )

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
        """Same as structured_output() but returns token usage and reports cost.

        Override in concrete providers to capture real usage from the API
        response. The base implementation delegates to structured_output()
        and reports zero usage — subclasses MUST override for real receipts.
        """
        result = await self.structured_output(messages, schema, temperature)
        if hasattr(self, '_cost_callback'):
            self._report_cost(0, 0, stage=stage, run_id=run_id)
        return LLMResponse(
            content="",
            structured=result,
            served_model=self.default_model,
        )

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
