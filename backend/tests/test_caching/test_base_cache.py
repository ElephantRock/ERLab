"""Tests for cache key generation and serialization utilities."""

from backend.providers.cache.base import (
    CacheEntry,
    deserialize_response,
    make_cache_key,
    serialize_response,
)
from backend.providers.base import LLMResponse


class TestMakeCacheKey:
    def test_deterministic(self):
        msgs = [{"role": "user", "content": "hello"}]
        assert make_cache_key(msgs) == make_cache_key(msgs)

    def test_different_messages(self):
        a = make_cache_key([{"role": "user", "content": "hello"}])
        b = make_cache_key([{"role": "user", "content": "world"}])
        assert a != b

    def test_kwargs_included(self):
        base = [{"role": "user", "content": "test"}]
        assert make_cache_key(base, temperature=0.7) != make_cache_key(base, temperature=0.3)

    def test_extra_kwargs(self):
        base = [{"role": "user", "content": "test"}]
        key = make_cache_key(base, temperature=0.5, max_tokens=100)
        assert len(key) == 64


class TestSerialization:
    def test_round_trip(self):
        resp = LLMResponse(content="hi", structured={"k": 1}, input_tokens=10, output_tokens=20)
        data = serialize_response(resp)
        restored = deserialize_response(data)
        assert restored.content == "hi"
        assert restored.structured == {"k": 1}
        assert restored.input_tokens == 10
        assert restored.output_tokens == 20

    def test_null_structured(self):
        resp = LLMResponse(content="text", structured=None)
        data = serialize_response(resp)
        restored = deserialize_response(data)
        assert restored.structured is None
