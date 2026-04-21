"""ResilientProvider — wraps an LLMProvider with circuit breaker, retry, and key rotation.

Same wrapper pattern as StageAwareProvider: transparent to callers,
delegates all property access to the wrapped provider.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from backend.providers.base import LLMProvider, LLMResponse
from backend.providers.resilience.circuit_breaker import CircuitBreaker
from backend.providers.resilience.retry import RetryConfig, retry_with_backoff

if TYPE_CHECKING:
    from backend.providers.secrets import KeyVault

logger = logging.getLogger(__name__)


class ResilientProvider(LLMProvider):
    """Wraps an LLMProvider with circuit breaker, retry, and optional key rotation."""

    def __init__(
        self,
        wrapped: LLMProvider,
        circuit_breaker: CircuitBreaker,
        retry_config: RetryConfig,
        key_vault: KeyVault | None = None,
    ) -> None:
        super().__init__()
        self._wrapped = wrapped
        self._circuit_breaker = circuit_breaker
        self._retry_config = retry_config
        self._key_vault = key_vault
        self._cost_callback = getattr(wrapped, "_cost_callback", None)

    async def _with_retry(self, fn, *args, **kwargs):
        """Execute an async callable with retry and circuit breaker."""

        async def _call():
            return await fn(*args, **kwargs)

        async def _on_auth_failure():
            if self._key_vault:
                try:
                    await self._key_vault.rotate_key(self._wrapped.provider_name)
                    logger.info(
                        "Rotated key for provider '%s'", self._wrapped.provider_name
                    )
                except Exception:
                    logger.warning(
                        "Key rotation failed for '%s'", self._wrapped.provider_name
                    )

        return await retry_with_backoff(
            _call,
            self._retry_config,
            self._circuit_breaker,
            on_auth_failure=_on_auth_failure if self._key_vault else None,
        )

    # --- LLMProvider interface ---

    async def complete(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        return await self._with_retry(
            self._wrapped.complete, messages, temperature, max_tokens
        )

    async def complete_with_usage(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stage: str = "",
        run_id: str | None = None,
    ) -> LLMResponse:
        return await self._with_retry(
            self._wrapped.complete_with_usage,
            messages,
            temperature,
            max_tokens,
            stage=stage,
            run_id=run_id,
        )

    def complete_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        # Streaming gets circuit-breaker check only — can't replay partial generators
        self._circuit_breaker.check()
        return self._wrapped.complete_stream(messages, temperature, max_tokens)

    async def structured_output(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
    ) -> dict:
        return await self._with_retry(
            self._wrapped.structured_output, messages, schema, temperature
        )

    async def structured_output_with_usage(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
        stage: str = "",
        run_id: str | None = None,
    ) -> LLMResponse:
        return await self._with_retry(
            self._wrapped.structured_output_with_usage,
            messages,
            schema,
            temperature,
            stage=stage,
            run_id=run_id,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await self._with_retry(self._wrapped.embed, texts)

    async def complete_with_tools(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        stage: str = "",
    ) -> LLMResponse:
        return await self._with_retry(
            self._wrapped.complete_with_tools,
            messages,
            tools,
            temperature,
            max_tokens,
            stage=stage,
        )

    async def health_check(self) -> bool:
        try:
            return await self._with_retry(self._wrapped.health_check)
        except Exception:
            return False

    # --- Delegated properties ---

    @property
    def provider_name(self) -> str:
        return self._wrapped.provider_name

    @property
    def default_model(self) -> str:
        return self._wrapped.default_model

    def model_info(self) -> dict[str, Any]:
        return self._wrapped.model_info()

    def set_cost_callback(self, callback) -> None:
        self._cost_callback = callback
        self._wrapped.set_cost_callback(callback)
