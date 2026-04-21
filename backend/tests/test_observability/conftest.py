"""Fixtures for observability tests."""

import pytest

from backend.pipeline.tracing.processor import (
    CompositeProcessor,
    InMemoryProcessor,
    set_tracer,
)


@pytest.fixture(autouse=True)
def _reset_tracer():
    yield
    set_tracer(CompositeProcessor())


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def memory_processor():
    return InMemoryProcessor(max_spans=100)


@pytest.fixture
def composite(memory_processor):
    c = CompositeProcessor([memory_processor])
    set_tracer(c)
    return c
