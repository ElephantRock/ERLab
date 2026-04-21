"""CachedProvider — transparent LLM response caching wrapper."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from backend.providers.base import LLMProvider, LLMResponse
from backend.providers.cache.base import CacheEntry, make_cache_key
from backend.providers.cache.memory_cache import InMemoryCache

if TYPE_CHECKING:
    from backend.providers.cache.semantic_cache import SemanticCache

logger = logging.getLogger(__name__)


class CachedProvider(LLMProvider):
    def __init__(
        self,
        wrapped: LLMProvider,
        cache: InMemoryCache,
        cache_type: str = "memory",
        semantic_cache: SemanticCache | None = None,
    ) -> None:
        super().__init__()
        self._wrapped = wrapped
        self._cache = cache
        self._cache_type = cache_type
        self._semantic_cache = semantic_cache

    def _check_exact(self, key: str) -> LLMResponse | None:
        entry = self._cache.lookup(key)
        if entry is not None:
            logger.debug("Cache HIT (exact): key=%s", key[:12])
            return entry.response
        return None

    async def _check_semantic(self, serialized: str) -> LLMResponse | None:
        if self._semantic_cache is None:
            return None
        entry = await self._semantic_cache.lookup_similar(serialized)
        if entry is not None:
            logger.debug("Cache HIT (semantic)")
            return entry.response
        return None

    def _store_exact(self, key: str, response: LLMResponse) -> None:
        self._cache.update(key, CacheEntry(response=response, created_at=time.time()))

    async def _store_semantic(self, serialized: str, response: LLMResponse) -> None:
        if self._semantic_cache is not None:
            await self._semantic_cache.update_similar(
                serialized, CacheEntry(response=response, created_at=time.time())
            )

    def _serialize(self, messages: list[dict], **extra: object) -> str:
        return json.dumps({"messages": messages, **extra}, sort_keys=True)

    # --- LLMProvider interface ---

    async def complete(
        self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 4096
    ) -> str:
        serialized = self._serialize(messages, temperature=temperature)
        key = make_cache_key(messages, temperature=temperature)

        cached = self._check_exact(key)
        if cached is not None:
            return cached.content

        cached = await self._check_semantic(serialized)
        if cached is not None:
            return cached.content

        result = await self._wrapped.complete(messages, temperature, max_tokens)
        response = LLMResponse(content=result)
        self._store_exact(key, response)
        await self._store_semantic(serialized, response)
        return result

    async def complete_with_usage(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stage: str = "",
        run_id: str | None = None,
    ) -> LLMResponse:
        serialized = self._serialize(messages, temperature=temperature, max_tokens=max_tokens)
        key = make_cache_key(messages, temperature=temperature, max_tokens=max_tokens)

        cached = self._check_exact(key)
        if cached is not None:
            return cached

        cached = await self._check_semantic(serialized)
        if cached is not None:
            return cached

        response = await self._wrapped.complete_with_usage(
            messages, temperature, max_tokens, stage=stage, run_id=run_id
        )
        self._store_exact(key, response)
        await self._store_semantic(serialized, response)
        return response

    def complete_stream(
        self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 4096
    ) -> AsyncIterator[str]:
        return self._wrapped.complete_stream(messages, temperature, max_tokens)

    async def structured_output(
        self, messages: list[dict], schema: dict, temperature: float = 0.3
    ) -> dict:
        schema_hash = _hash_schema(schema)
        serialized = self._serialize(messages, temperature=temperature)
        key = make_cache_key(messages, temperature=temperature, schema_hash=schema_hash)

        cached = self._check_exact(key)
        if cached is not None and cached.structured is not None:
            return cached.structured

        cached = await self._check_semantic(serialized)
        if cached is not None and cached.structured is not None:
            return cached.structured

        result = await self._wrapped.structured_output(messages, schema, temperature)
        response = LLMResponse(content="", structured=result)
        self._store_exact(key, response)
        await self._store_semantic(serialized, response)
        return result

    async def structured_output_with_usage(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
        stage: str = "",
        run_id: str | None = None,
    ) -> LLMResponse:
        schema_hash = _hash_schema(schema)
        serialized = self._serialize(messages, temperature=temperature)
        key = make_cache_key(messages, temperature=temperature, schema_hash=schema_hash)

        cached = self._check_exact(key)
        if cached is not None:
            return cached

        cached = await self._check_semantic(serialized)
        if cached is not None:
            return cached

        response = await self._wrapped.structured_output_with_usage(
            messages, schema, temperature, stage=stage, run_id=run_id
        )
        self._store_exact(key, response)
        await self._store_semantic(serialized, response)
        return response

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await self._wrapped.embed(texts)

    async def complete_with_tools(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        stage: str = "",
    ) -> LLMResponse:
        return await self._wrapped.complete_with_tools(
            messages, tools, temperature, max_tokens, stage=stage
        )

    async def health_check(self) -> bool:
        return await self._wrapped.health_check()

    @property
    def provider_name(self) -> str:
        return self._wrapped.provider_name

    @property
    def default_model(self) -> str:
        return self._wrapped.default_model

    def model_info(self) -> dict[str, Any]:
        return self._wrapped.model_info()

    def set_cost_callback(self, callback: Any) -> None:
        self._wrapped.set_cost_callback(callback)

    def cache_stats(self) -> dict[str, Any]:
        result: dict[str, Any] = {"type": self._cache_type, **self._cache.stats()}
        if self._semantic_cache is not None:
            result["semantic"] = self._semantic_cache.stats()
        return result


def _hash_schema(schema: dict) -> str:
    canonical = json.dumps(schema, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
