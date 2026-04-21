"""Fixtures for caching tests."""

import pytest

from backend.providers.cache.memory_cache import InMemoryCache


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def memory_cache():
    return InMemoryCache(max_size=10, ttl_seconds=3600)
