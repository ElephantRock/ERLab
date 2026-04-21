"""RRF fusion performance benchmarks."""

import pytest

pytestmark = pytest.mark.slow


def _rrf_fuse(bm25_results, semantic_results, k=60):
    scores, docs = {}, {}
    for rank, doc in enumerate(bm25_results):
        scores[doc["id"]] = scores.get(doc["id"], 0.0) + 1.0 / (k + rank + 1)
        docs[doc["id"]] = doc
    for rank, doc in enumerate(semantic_results):
        scores[doc["id"]] = scores.get(doc["id"], 0.0) + 1.0 / (k + rank + 1)
        if doc["id"] not in docs:
            docs[doc["id"]] = doc
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


class TestRRFFusionBenchmark:
    def test_rrf_fuse_200_docs(self, benchmark):
        bm25 = [{"id": f"bm25_{i}", "text": f"doc {i}", "metadata": {}} for i in range(100)]
        sem = [{"id": f"sem_{i}", "text": f"doc {i}", "metadata": {}} for i in range(100)]
        benchmark(_rrf_fuse, bm25, sem)

    def test_rrf_fuse_1000_docs(self, benchmark):
        bm25 = [{"id": f"bm25_{i}", "text": f"doc {i}", "metadata": {}} for i in range(500)]
        sem = [{"id": f"sem_{i}", "text": f"doc {i}", "metadata": {}} for i in range(500)]
        benchmark(_rrf_fuse, bm25, sem)
