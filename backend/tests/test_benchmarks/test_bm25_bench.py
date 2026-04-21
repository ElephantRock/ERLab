"""BM25 index performance benchmarks."""

import pytest

pytestmark = pytest.mark.slow


class TestBM25Benchmark:
    def test_bm25_query_10_results(self, benchmark, benchmark_bm25):
        benchmark(benchmark_bm25.query, "transformer attention retrieval", n_results=10)

    def test_bm25_query_100_results(self, benchmark, benchmark_bm25):
        benchmark(benchmark_bm25.query, "knowledge graph embedding", n_results=100)

    def test_bm25_query_single_term(self, benchmark, benchmark_bm25):
        benchmark(benchmark_bm25.query, "reinforcement", n_results=10)
