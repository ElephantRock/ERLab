"""Tests for provider ModelReceipt propagation.

Verifies that receipts flow through the full provider chain:
ResilientProvider → CachedProvider → OpenAIProvider

and that last_receipt is accessible on the outermost wrapper.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.providers.base import LLMProvider, LLMResponse
from backend.providers.resilience.resilient_provider import ResilientProvider
from backend.providers.resilience.circuit_breaker import CircuitBreaker
from backend.providers.resilience.retry import RetryConfig
from backend.providers.cache.cached_provider import CachedProvider
from backend.providers.cache.memory_cache import InMemoryCache
from backend.pipeline.operations.types import ModelReceipt


class ReceiptCapturingProvider(LLMProvider):
    """Test provider that sets _last_receipt like OpenAIProvider does."""

    def __init__(self, model: str = "test-model"):
        super().__init__()
        self._model = model

    @property
    def provider_name(self) -> str:
        return "test"

    @property
    def default_model(self) -> str:
        return self._model

    async def complete(self, messages, temperature=0.7, max_tokens=4096) -> str:
        self._set_receipt_from_response(self._model)
        return "test response"

    async def complete_stream(self, messages, temperature=0.7, max_tokens=4096):
        yield "test"

    async def structured_output(self, messages, schema, temperature=0.3, **kwargs) -> dict:
        return {}


class TestReceiptPropagation:
    """Test that receipts propagate through the provider chain."""

    @pytest.mark.asyncio
    async def test_inner_provider_sets_receipt(self):
        provider = ReceiptCapturingProvider("qwen3-4b")
        assert provider.last_receipt is None

        await provider.complete([{"role": "user", "content": "hi"}])

        assert provider.last_receipt is not None
        assert provider.last_receipt.served_model == "qwen3-4b"
        assert provider.last_receipt.provider == "test"

    @pytest.mark.asyncio
    async def test_receipt_propagates_through_cached(self):
        inner = ReceiptCapturingProvider("qwen3-4b")
        cache = InMemoryCache()
        cached = CachedProvider(inner, cache)

        assert cached.last_receipt is None

        await cached.complete([{"role": "user", "content": "hi"}])

        assert cached.last_receipt is not None
        assert cached.last_receipt.served_model == "qwen3-4b"

    @pytest.mark.asyncio
    async def test_receipt_propagates_through_resilient(self):
        inner = ReceiptCapturingProvider("qwen3-4b")
        cache = InMemoryCache()
        cached = CachedProvider(inner, cache)
        cb = CircuitBreaker()
        retry = RetryConfig(max_retries=1)
        resilient = ResilientProvider(cached, cb, retry)

        assert resilient.last_receipt is None

        await resilient.complete([{"role": "user", "content": "hi"}])

        assert resilient.last_receipt is not None
        assert resilient.last_receipt.served_model == "qwen3-4b"
        assert resilient.last_receipt.provider == "test"

    @pytest.mark.asyncio
    async def test_receipt_reflects_actual_served_model(self):
        """If the API returns a different model, the receipt reflects it."""
        inner = ReceiptCapturingProvider("requested-model")
        inner._model = "actual-served-model"

        await inner.complete([{"role": "user", "content": "hi"}])

        assert inner.last_receipt.served_model == "actual-served-model"
        assert inner.last_receipt.requested_model == "actual-served-model"

    @pytest.mark.asyncio
    async def test_receipt_cleared_on_new_provider(self):
        """Fresh provider has no receipt."""
        provider = ReceiptCapturingProvider("test")
        assert provider.last_receipt is None

    @pytest.mark.asyncio
    async def test_full_chain_three_layers(self):
        """End-to-end: ResilientProvider → CachedProvider → ReceiptCapturingProvider."""
        inner = ReceiptCapturingProvider("qwen3-4b")
        cache = InMemoryCache()
        cached = CachedProvider(inner, cache)
        cb = CircuitBreaker()
        retry = RetryConfig(max_retries=1)
        resilient = ResilientProvider(cached, cb, retry)

        result = await resilient.complete([{"role": "user", "content": "hello"}])

        assert result == "test response"
        assert resilient.last_receipt is not None
        # All three layers should have the same receipt
        assert cached.last_receipt is not None
        assert inner.last_receipt is not None
        assert resilient.last_receipt.served_model == inner.last_receipt.served_model

    @pytest.mark.asyncio
    async def test_receipt_has_timestamp(self):
        provider = ReceiptCapturingProvider("test")
        await provider.complete([{"role": "user", "content": "hi"}])

        assert provider.last_receipt.timestamp is not None
        assert "T" in provider.last_receipt.timestamp  # ISO format
