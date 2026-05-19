"""GatewayProvider — LLMProvider adapter that routes through the gateway.

This is the key compatibility layer. All 75 existing call sites call
`provider.complete()` or `provider.structured_output()` as before.
But the provider now delegates to LLMGateway internally.

Usage in ServiceRegistry:
    gateway = LLMGateway(registry, budgeter, default_model=settings.lmstudio_model)
    provider = GatewayProvider(gateway, inner_provider=anthropic_provider)
    # All existing code uses `provider` as before, but calls go through gateway.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from backend.providers.base import LLMProvider, LLMResponse
from backend.pipeline.gateway.gateway import LLMGateway, LLMRequest, LLMResponse as GWResponse
from backend.pipeline.gateway.token_budget import PromptTooLargeError

logger = logging.getLogger(__name__)


class GatewayProvider(LLMProvider):
    """Wraps an LLMProvider to route calls through the LLMGateway.

    Implements the full LLMProvider interface so existing code doesn't need
    to change. Each method creates an LLMRequest and delegates to the gateway.

    The gateway provides:
    - Pre-flight token budgeting (catches oversized prompts)
    - Output validation with confidence scoring
    - Call logging for observability
    - Degraded result handling

    If the gateway is unavailable or the call fails, falls back to the
    inner provider directly (backward compatibility).
    """

    def __init__(
        self,
        gateway: LLMGateway,
        inner_provider: LLMProvider,
        stage: str = "",
        run_id: str = "",
    ):
        super().__init__()
        self._gateway = gateway
        self._inner = inner_provider
        self._stage = stage
        self._run_id = run_id
        self._cost_callback = inner_provider._cost_callback

    async def complete(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Complete via gateway with token budgeting."""
        try:
            gw_response = await self._gateway.call(LLMRequest(
                task=self._stage or "complete",
                messages=messages,
                max_output_tokens=max_tokens,
                temperature=temperature,
                stage=self._stage,
                run_id=self._run_id,
            ))

            if isinstance(gw_response.content, str):
                return gw_response.content
            return str(gw_response.content)

        except PromptTooLargeError:
            # Re-raise — the caller should compact/split
            raise
        except Exception as e:
            logger.warning("Gateway failed, falling back to inner provider: %s", str(e)[:100])
            return await self._inner.complete(messages, temperature, max_tokens)

    async def complete_with_usage(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stage: str = "",
        run_id: str | None = None,
    ) -> LLMResponse:
        """Complete with usage tracking via gateway."""
        try:
            gw_response = await self._gateway.call(LLMRequest(
                task=stage or self._stage or "complete",
                messages=messages,
                max_output_tokens=max_tokens,
                temperature=temperature,
                stage=stage or self._stage,
                run_id=run_id or self._run_id,
            ))

            content = gw_response.content
            if not isinstance(content, str):
                content = str(content)

            return LLMResponse(
                content=content,
                input_tokens=gw_response.input_tokens,
                output_tokens=gw_response.output_tokens,
            )

        except PromptTooLargeError:
            raise
        except Exception as e:
            logger.warning("Gateway failed, falling back to inner provider: %s", str(e)[:100])
            return await self._inner.complete_with_usage(
                messages, temperature, max_tokens, stage, run_id,
            )

    def complete_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream via inner provider (gateway doesn't buffer streams).

        Streaming can't go through the gateway's validate/log pipeline
        because it's a generator. We log it as a regular call instead.
        """
        # Log the streaming call
        logger.debug("Streaming call for stage '%s' (not gateway-validated)", self._stage)
        return self._inner.complete_stream(messages, temperature, max_tokens)

    async def structured_output(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
        max_tokens: int = 1200,
    ) -> dict:
        """Structured output via gateway with schema validation."""
        try:
            gw_response = await self._gateway.call(LLMRequest(
                task=self._stage or "structured_output",
                messages=messages,
                max_output_tokens=max_tokens,
                temperature=temperature,
                schema=schema,
                stage=self._stage,
                run_id=self._run_id,
            ))

            if isinstance(gw_response.content, dict):
                return gw_response.content
            # If gateway returned a string (fallback), try to parse as JSON
            if isinstance(gw_response.content, str):
                import json
                try:
                    return json.loads(gw_response.content)
                except json.JSONDecodeError:
                    # Try aggressive JSON extraction from LLM output
                    from backend.pipeline.utils.json_extraction import extract_json
                    extracted = extract_json(gw_response.content)
                    if extracted:
                        logger.info("Recovered structured output via extract_json")
                        return extracted
                    logger.warning("Structured output was not valid JSON")
                    return {"raw": gw_response.content}
            return {"raw": str(gw_response.content)}

        except PromptTooLargeError:
            raise
        except Exception as e:
            logger.warning("Gateway failed, falling back to inner provider: %s", str(e)[:100])
            return await self._inner.structured_output(messages, schema, temperature)

    async def structured_output_with_usage(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
        stage: str = "",
        run_id: str | None = None,
    ) -> LLMResponse:
        """Structured output with usage tracking."""
        try:
            gw_response = await self._gateway.call(LLMRequest(
                task=stage or self._stage or "structured_output",
                messages=messages,
                max_output_tokens=4096,
                temperature=temperature,
                schema=schema,
                stage=stage or self._stage,
                run_id=run_id or self._run_id,
            ))

            content = gw_response.content
            if isinstance(content, str):
                import json
                try:
                    content = json.loads(content)
                except json.JSONDecodeError:
                    content = {"raw": content}

            return LLMResponse(
                content=str(content),
                input_tokens=gw_response.input_tokens,
                output_tokens=gw_response.output_tokens,
            )

        except PromptTooLargeError:
            raise
        except Exception as e:
            logger.warning("Gateway failed, falling back to inner provider: %s", str(e)[:100])
            return await self._inner.structured_output_with_usage(
                messages, schema, temperature, stage, run_id,
            )

    async def complete_with_tools(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        stage: str = "",
    ) -> LLMResponse:
        """Tool-calling completion (falls back to inner provider)."""
        try:
            gw_response = await self._gateway.call(LLMRequest(
                task=stage or self._stage or "tool_call",
                messages=messages,
                max_output_tokens=max_tokens,
                temperature=temperature,
                tools=tools,
                stage=stage or self._stage,
                run_id=self._run_id,
            ))

            content = gw_response.content
            if not isinstance(content, str):
                content = str(content)

            return LLMResponse(
                content=content,
                input_tokens=gw_response.input_tokens,
                output_tokens=gw_response.output_tokens,
            )

        except PromptTooLargeError:
            raise
        except Exception as e:
            logger.warning("Gateway failed, falling back to inner provider: %s", str(e)[:100])
            return await self._inner.complete_with_tools(
                messages, tools, temperature, max_tokens, stage,
            )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embeddings bypass the gateway (different path)."""
        return await self._inner.embed(texts)

    async def health_check(self) -> bool:
        """Health check via inner provider."""
        return await self._inner.health_check()

    def model_info(self) -> dict[str, Any]:
        return self._inner.model_info()

    def set_cost_callback(self, callback) -> None:
        self._cost_callback = callback
        self._inner.set_cost_callback(callback)

    @property
    def provider_name(self) -> str:
        return self._inner.provider_name

    @property
    def default_model(self) -> str:
        return self._inner.default_model

    def set_context(self, stage: str, run_id: str = "") -> None:
        """Update the stage/run context for subsequent calls."""
        self._stage = stage
        self._run_id = run_id
