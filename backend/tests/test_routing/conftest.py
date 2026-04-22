"""Fixtures for routing tests."""

import pytest

from backend.providers.provider_factory import CostTracker


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def cost_tracker():
    return CostTracker()
