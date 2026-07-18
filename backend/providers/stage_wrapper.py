"""StageAwareProvider — wraps an LLMProvider to auto-inject stage and run_id.

Used by the orchestrator to attribute cost events to specific pipeline stages
without modifying every subsystem's call sites.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from backend.providers.base import LLMProvider, LLMResponse


class StageAwareProvider(LLMProvider):
    """Wraps an LLMProvider to inject stage and run_id into cost reports."""

    def __init__(
        self,
        wrapped: LLMProvider,
        stage: str,
        run_id: str | None = None,
    ):
        super().__init__()
        self._wrapped = wrapped
        self._stage = stage
        self._run_id = run_id
        self._cost_callback = wrapped._cost_callback

    async def complete(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        return await self._wrapped.complete(messages, temperature, max_tokens)

    async def complete_with_usage(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stage: str = "",
        run_id: str | None = None,
    ) -> LLMResponse:
        return await self._wrapped.complete_with_usage(
            messages,
            temperature,
            max_tokens,
            stage=stage or self._stage,
            run_id=run_id or self._run_id,
        )

    def complete_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        return self._wrapped.complete_stream(messages, temperature, max_tokens)

    async def structured_output(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
    ) -> dict:
        return await self._wrapped.structured_output(messages, schema, temperature)

    async def structured_output_with_usage(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
        stage: str = "",
        run_id: str | None = None,
    ) -> LLMResponse:
        return await self._wrapped.structured_output_with_usage(
            messages,
            schema,
            temperature,
            stage=stage or self._stage,
            run_id=run_id or self._run_id,
        )

    async def complete_with_tools(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        stage: str = "",
    ) -> LLMResponse:
        return await self._wrapped.complete_with_tools(
            messages,
            tools,
            temperature,
            max_tokens,
            stage=stage or self._stage,
        )

    async def health_check(self) -> bool:
        return await self._wrapped.health_check()

    def model_info(self) -> dict[str, Any]:
        return self._wrapped.model_info()

    def set_cost_callback(self, callback) -> None:
        self._cost_callback = callback
        self._wrapped.set_cost_callback(callback)

    @property
    def provider_name(self) -> str:
        return self._wrapped.provider_name

    @property
    def default_model(self) -> str:
        return self._wrapped.default_model
