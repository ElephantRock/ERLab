"""Stage-aware provider routing via context variables.

Instead of passing stage names through 66 service files, we use
an asyncio-safe ContextVar to propagate the current stage name.
The StageAwareProvider wrapper reads this and delegates to ModelManager.

This migrates all 88 LLM call sites with zero edits to service files.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextvars import ContextVar, Token
from typing import Any

from backend.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

# Async-safe context variable for the current pipeline stage.
# Set by the orchestrator before each stage, visible to all nested awaits.
current_stage: ContextVar[str | None] = ContextVar("current_stage", default=None)

class StageAwareProvider(LLMProvider):
    """Provider wrapper that routes to the correct model based on the
    current pipeline stage (read from ``current_stage`` ContextVar).

    All 88 existing call sites call ``self._provider.complete()`` as before.
    This wrapper intercepts those calls and delegates to the model assigned
    to the current stage by ModelManager.

    Fallback chain:
        1. ModelManager assignment for ``current_stage``
        2. Default provider (the one this wraps)
    """

    def __init__(self, default: LLMProvider, model_manager: Any | None = None):
        super().__init__()
        self._default = default
        self._mm = model_manager
        self._cost_callback = default._cost_callback
        # Cache: stage_name -> LLMProvider  (avoids repeated lookups)
        self._cache: dict[str, LLMProvider] = {}
        # Token budget resolver for thinking models
        from backend.providers.token_budget import get_token_budget_resolver
        self._budget_resolver = get_token_budget_resolver()

    def _resolve(self) -> LLMProvider:
        """Return the provider for the current stage, or the default."""
        stage = current_stage.get()
        if not stage or not self._mm:
            return self._default

        cached = self._cache.get(stage)
        if cached is not None:
            return cached

        try:
            # Use alias map if the orchestrator registered one
            aliased = getattr(self._mm, "_stage_aliases", {}).get(stage, stage)
            provider = self._mm.get_provider(aliased)
            if provider is not None:
                self._cache[stage] = provider
                return provider
        except Exception as exc:
            logger.debug(
                "StageAwareProvider: stage '%s' lookup failed: %s", stage, exc
            )

        return self._default

    def _get_model_id(self, stage: str | None) -> str:
        """Get the model_id assigned to a stage, for token budget resolution."""
        if not stage or not self._mm:
            return getattr(self._default, "default_model", "")
        try:
            aliased = getattr(self._mm, "_stage_aliases", {}).get(stage, stage)
            info = self._mm.get_stage_model(aliased)
            if info:
                return info.model_id
        except Exception:
            pass
        return getattr(self._default, "default_model", "")

    # ── LLMProvider interface ─────────────────────────────────────

    async def complete(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        stage = current_stage.get()
        model_id = self._get_model_id(stage)
        adjusted = self._budget_resolver.resolve_max_tokens(model_id, max_tokens, stage)
        return await self._resolve().complete(messages, temperature, adjusted)

    async def complete_with_usage(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stage: str = "",
        run_id: str | None = None,
    ) -> LLMResponse:
        s = stage or current_stage.get()
        model_id = self._get_model_id(s)
        adjusted = self._budget_resolver.resolve_max_tokens(model_id, max_tokens, s)
        return await self._resolve().complete_with_usage(
            messages, temperature, adjusted, s, run_id
        )

    def complete_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        return self._resolve().complete_stream(messages, temperature, max_tokens)

    async def structured_output(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict:
        stage = current_stage.get()
        model_id = self._get_model_id(stage)
        adjusted = self._budget_resolver.resolve_max_tokens(model_id, max_tokens, stage)
        return await self._resolve().structured_output(messages, schema, temperature, adjusted)

    async def structured_output_with_usage(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
        stage: str = "",
        run_id: str | None = None,
    ) -> LLMResponse:
        return await self._resolve().structured_output_with_usage(
            messages, schema, temperature, stage, run_id
        )

    async def complete_with_tools(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        stage: str = "",
    ) -> LLMResponse:
        return await self._resolve().complete_with_tools(
            messages, tools, temperature, max_tokens, stage
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await self._resolve().embed(texts)

    async def health_check(self) -> bool:
        return await self._default.health_check()

    def model_info(self) -> dict[str, Any]:
        return self._resolve().model_info()

    def set_cost_callback(self, callback) -> None:
        self._cost_callback = callback
        self._default.set_cost_callback(callback)

    @property
    def provider_name(self) -> str:
        return self._resolve().provider_name

    @property
    def default_model(self) -> str:
        return self._resolve().default_model

    def set_context(self, stage: str, run_id: str = "") -> None:
        """Compatibility with GatewayProvider.set_context()."""
        resolved = self._resolve()
        if hasattr(resolved, "set_context"):
            resolved.set_context(stage, run_id)

    # ── Cache management ──────────────────────────────────────────

    def clear_cache(self) -> None:
        """Clear the per-stage provider cache (e.g. after catalog reload)."""
        self._cache.clear()


def set_stage(stage_name: str | None) -> Token | None:
    """Convenience: set the current pipeline stage. Returns a reset token."""
    return current_stage.set(stage_name)


def reset_stage(token: Token | None) -> None:
    """Convenience: reset the current stage to its previous value."""
    if token is not None:
        current_stage.reset(token)
