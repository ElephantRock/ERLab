"""Tiered memory performance benchmarks."""

import asyncio
import time

import pytest

from backend.pipeline.knowledge.truth import TruthValue
from backend.pipeline.memory.models import MemoryEntry, MemoryQuery, MemoryType

pytestmark = pytest.mark.slow


class TestMemoryBenchmark:
    def test_working_tier_recall(self, benchmark, benchmark_memory):
        query = MemoryQuery(query="observation", namespace="benchmark", top_k=10)

        def recall():
            return asyncio.run(benchmark_memory.recall(query))

        results = benchmark(recall)
        assert len(results) > 0

    def test_working_tier_store(self, benchmark, benchmark_memory):
        counter = [0]

        def store():
            counter[0] += 1
            entry = MemoryEntry(
                id=f"bench_{counter[0]}_{time.time_ns()}",
                content="benchmark store entry",
                memory_type=MemoryType.SEMANTIC,
                namespace="bench_store",
                truth=TruthValue.from_observation(),
            )
            return asyncio.run(benchmark_memory.store(entry))

        benchmark(store)

    def test_working_tier_recall_under_50ms(self, benchmark_memory):
        query = MemoryQuery(query="observation", namespace="benchmark", top_k=10)
        start = time.perf_counter()
        asyncio.run(benchmark_memory.recall(query))
        elapsed = time.perf_counter() - start
        assert elapsed < 0.05, f"Working-tier recall took {elapsed*1000:.1f}ms (limit: 50ms)"
