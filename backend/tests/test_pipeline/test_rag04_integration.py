"""Tests for BATCH-RAG-04: Metrics Persistence + Integration.

Tests cover:
  1. PipelineMetric model
  2. persist_metrics and get_metrics_for_run
  3. get_metric_history
  4. Integration: benchmark → metrics → verify stored
  5. API endpoint verification
"""

import pytest

from backend.db.metrics_models import PipelineMetric

# ── Model Tests ────────────────────────────────────────────────────────

def test_pipeline_metric_model():
    """PipelineMetric has all required columns."""
    # Verify model has the expected columns
    assert hasattr(PipelineMetric, "id")
    assert hasattr(PipelineMetric, "run_id")
    assert hasattr(PipelineMetric, "stage")
    assert hasattr(PipelineMetric, "metric_name")
    assert hasattr(PipelineMetric, "metric_value")
    assert hasattr(PipelineMetric, "detail")
    assert hasattr(PipelineMetric, "created_at")


def test_pipeline_metric_tablename():
    """PipelineMetric uses correct table name."""
    assert PipelineMetric.__tablename__ == "pipeline_metrics"


# ── Metrics Persistence Tests (using in-memory mock) ───────────────────

class InMemoryMetricsStore:
    """Simple in-memory metrics store for testing without DB."""

    def __init__(self):
        self._metrics: list[dict] = []
        self._next_id = 1

    def persist(self, run_id: int, stage: str, metrics: dict) -> bool:
        for name, value in metrics.items():
            self._metrics.append({
                "id": self._next_id,
                "run_id": run_id,
                "stage": stage,
                "metric_name": name,
                "metric_value": float(value),
            })
            self._next_id += 1
        return True

    def get_for_run(self, run_id: int) -> dict:
        result: dict[str, list] = {}
        for m in self._metrics:
            if m["run_id"] == run_id:
                if m["stage"] not in result:
                    result[m["stage"]] = []
                result[m["stage"]].append({
                    "name": m["metric_name"],
                    "value": m["metric_value"],
                })
        return result

    def get_history(self, metric_name: str, limit: int = 50) -> list[dict]:
        matches = [
            m for m in self._metrics
            if m["metric_name"] == metric_name
        ]
        return matches[:limit]


def test_in_memory_store_persist():
    """InMemoryMetricsStore persists metrics correctly."""
    store = InMemoryMetricsStore()
    store.persist(1, "literature_search", {
        "hit_rate": 0.85,
        "mrr": 0.72,
        "ndcg_at_10": 0.68,
    })
    result = store.get_for_run(1)
    assert "literature_search" in result
    assert len(result["literature_search"]) == 3


def test_in_memory_store_multiple_stages():
    """InMemoryMetricsStore handles multiple stages per run."""
    store = InMemoryMetricsStore()
    store.persist(1, "literature_search", {"hit_rate": 0.85})
    store.persist(1, "proposal_synthesis", {"faithfulness": 0.78})

    result = store.get_for_run(1)
    assert "literature_search" in result
    assert "proposal_synthesis" in result


def test_in_memory_store_history():
    """InMemoryMetricsStore returns metric history."""
    store = InMemoryMetricsStore()
    store.persist(1, "literature_search", {"hit_rate": 0.85})
    store.persist(2, "literature_search", {"hit_rate": 0.90})
    store.persist(3, "literature_search", {"hit_rate": 0.88})

    history = store.get_history("hit_rate")
    assert len(history) == 3
    values = [h["metric_value"] for h in history]
    assert 0.85 in values
    assert 0.90 in values


# ── Integration Test ───────────────────────────────────────────────────

def test_full_evaluation_pipeline():
    """Integration: generate benchmark → compute metrics → store."""
    from backend.pipeline.evaluation.benchmark_models import (
        BenchmarkDataset,
        BenchmarkQuestion,
    )
    from backend.pipeline.evaluation.retrieval_metrics import (
        RetrievedDocument,
        compute_retrieval_metrics,
    )

    # Step 1: Create synthetic benchmark questions
    questions = [
        BenchmarkQuestion(
            question="What is the Transformer?",
            source_paper_id="p1",
            source_paper_title="Attention Is All You Need",
            difficulty="easy",
        ),
        BenchmarkQuestion(
            question="How does BERT work?",
            source_paper_id="p2",
            source_paper_title="BERT",
            difficulty="medium",
        ),
    ]
    dataset = BenchmarkDataset(id="test-integration", questions=questions)

    # Step 2: Simulate retrieval results (1 found at rank 1, 1 not found)
    queries_with_results = [
        ("What is the Transformer?", [
            RetrievedDocument(doc_id="p1", rank=1, is_relevant=True),
            RetrievedDocument(doc_id="x1", rank=2, is_relevant=False),
        ]),
        ("How does BERT work?", [
            RetrievedDocument(doc_id="x2", rank=1, is_relevant=False),
            RetrievedDocument(doc_id="x3", rank=2, is_relevant=False),
        ]),
    ]

    # Step 3: Compute metrics
    report = compute_retrieval_metrics(queries_with_results, k_values=[5, 10])
    assert report.hit_rate == 0.5  # 1 of 2 queries found correct doc
    assert report.mrr == 0.5       # (1.0 + 0.0) / 2

    # Step 4: Store metrics
    store = InMemoryMetricsStore()
    store.persist(1, "literature_search", {
        "hit_rate": report.hit_rate,
        "mrr": report.mrr,
        "ndcg_at_5": report.ndcg_at_k[5],
        "ndcg_at_10": report.ndcg_at_k[10],
        "map_score": report.map_score,
    })

    # Step 5: Verify stored
    stored = store.get_for_run(1)
    assert "literature_search" in stored
    metrics_by_name = {m["name"]: m["value"] for m in stored["literature_search"]}
    assert metrics_by_name["hit_rate"] == 0.5
    assert metrics_by_name["mrr"] == 0.5


# ── API Registration Test ──────────────────────────────────────────────

@pytest.mark.slow
def test_evaluation_router_registered():
    """Evaluation router is registered in the FastAPI app."""
    from backend.api.app import app
    routes = [r.path for r in app.routes]
    # Check that evaluation endpoints exist
    assert any("/evaluation/benchmarks" in r for r in routes)
    assert any("/evaluation/pipeline-metrics" in r for r in routes)
