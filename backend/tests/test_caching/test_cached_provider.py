"""Tests for CachedProvider — cache hit/miss across all LLM methods."""

import time

import pytest

from backend.providers.base import LLMResponse
from backend.providers.cache.cached_provider import CachedProvider
from backend.providers.cache.memory_cache import InMemoryCache
from backend.providers.cache.base import CacheEntry
from backend.tests.conftest import FakeLLMProvider


def _cached_provider(**cache_kwargs):
    cache = InMemoryCache(**cache_kwargs)
    fake = FakeLLMProvider(responses={
        "complete": "LLM response",
        "structured_output": {"key": "value"},
    })
    return CachedProvider(wrapped=fake, cache=cache), fake


@pytest.mark.anyio
class TestCachedProvider:
    async def test_complete_hits_cache(self):
        cp, fake = _cached_provider(max_size=10, ttl_seconds=3600)
        msgs = [{"role": "user", "content": "hello"}]
        r1 = await cp.complete(msgs)
        r2 = await cp.complete(msgs)
        assert r1 == "LLM response"
        assert r2 == "LLM response"
        assert len(fake._call_log) == 1  # second was cached

    async def test_complete_with_usage_caches(self):
        cp, fake = _cached_provider(max_size=10, ttl_seconds=3600)
        msgs = [{"role": "user", "content": "hello"}]
        r1 = await cp.complete_with_usage(msgs)
        r2 = await cp.complete_with_usage(msgs)
        assert r1.content == "LLM response"
        assert r2.content == "LLM response"
        assert len(fake._call_log) == 1

    async def test_structured_output_caches(self):
        cp, fake = _cached_provider(max_size=10, ttl_seconds=3600)
        msgs = [{"role": "user", "content": "analyze"}]
        schema = {"type": "object", "properties": {"key": {"type": "string"}}}
        r1 = await cp.structured_output(msgs, schema)
        r2 = await cp.structured_output(msgs, schema)
        assert r1 == {"key": "value"}
        assert r2 == {"key": "value"}
        assert len(fake._call_log) == 1

    async def test_structured_output_with_usage_caches(self):
        cp, fake = _cached_provider(max_size=10, ttl_seconds=3600)
        msgs = [{"role": "user", "content": "analyze"}]
        schema = {"type": "object"}
        r1 = await cp.structured_output_with_usage(msgs, schema)
        r2 = await cp.structured_output_with_usage(msgs, schema)
        assert r1.structured == {"key": "value"}
        assert r2.structured == {"key": "value"}
        assert len(fake._call_log) == 1

    async def test_stream_not_cached(self):
        cp, fake = _cached_provider(max_size=10, ttl_seconds=3600)
        msgs = [{"role": "user", "content": "stream"}]
        chunks1 = [c async for c in cp.complete_stream(msgs)]
        chunks2 = [c async for c in cp.complete_stream(msgs)]
        assert len(fake._call_log) == 2

    async def test_complete_with_tools_not_cached(self):
        cp, _ = _cached_provider(max_size=10, ttl_seconds=3600)
        msgs = [{"role": "user", "content": "tools"}]
        # Both calls should raise NotImplementedError (pass-through, not cached)
        with pytest.raises(NotImplementedError):
            await cp.complete_with_tools(msgs, tools=[])
        with pytest.raises(NotImplementedError):
            await cp.complete_with_tools(msgs, tools=[])

    async def test_different_temperature_different_cache(self):
        cp, fake = _cached_provider(max_size=10, ttl_seconds=3600)
        msgs = [{"role": "user", "content": "hello"}]
        await cp.complete(msgs, temperature=0.7)
        await cp.complete(msgs, temperature=0.3)
        assert len(fake._call_log) == 2

    async def test_ttl_expiry_causes_fresh_call(self):
        cp, fake = _cached_provider(max_size=10, ttl_seconds=0)
        msgs = [{"role": "user", "content": "hello"}]
        await cp.complete_with_usage(msgs)
        time.sleep(0.01)
        await cp.complete_with_usage(msgs)
        assert len(fake._call_log) == 2

    async def test_cache_stats(self):
        cp, _ = _cached_provider(max_size=10, ttl_seconds=3600)
        msgs = [{"role": "user", "content": "hello"}]
        await cp.complete_with_usage(msgs)
        await cp.complete_with_usage(msgs)
        stats = cp.cache_stats()
        assert stats["type"] == "memory"
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    async def test_cost_callback_forwarded(self):
        cp, fake = _cached_provider(max_size=10, ttl_seconds=3600)
        events = []
        cp.set_cost_callback(lambda e: events.append(e))
        assert fake._cost_callback is not None

    async def test_properties_delegated(self):
        cp, fake = _cached_provider(max_size=10, ttl_seconds=3600)
        assert cp.provider_name == "fake"
        assert cp.default_model == "fake-model"
