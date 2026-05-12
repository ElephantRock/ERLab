"""Tests for BATCH-RAG-02: Retrieval Metrics Module.

Tests cover:
  1. RetrievedDocument and QueryMetrics data models
  2. compute_retrieval_metrics: Hit Rate, MRR, nDCG@K, MAP, Precision@K, Recall@K
  3. evaluate_search_results convenience function
  4. Edge cases: empty results, all relevant, none relevant
"""

import math

import pytest

from backend.pipeline.evaluation.retrieval_metrics import (
    RetrievedDocument,
    RetrievalMetricsReport,
    QueryMetrics,
    compute_retrieval_metrics,
    evaluate_search_results,
)


# ── Helper ─────────────────────────────────────────────────────────────

def _make_docs(
    ids: list[str], relevant: set[str]
) -> list[RetrievedDocument]:
    """Create RetrievedDocument list from IDs and relevant set."""
    return [
        RetrievedDocument(
            doc_id=did, rank=i + 1, is_relevant=(did in relevant)
        )
        for i, did in enumerate(ids)
    ]


# ── Model Tests ────────────────────────────────────────────────────────

def test_retrieved_document():
    """RetrievedDocument stores all fields correctly."""
    doc = RetrievedDocument(doc_id="p1", rank=1, score=0.95, is_relevant=True)
    assert doc.doc_id == "p1"
    assert doc.rank == 1
    assert doc.is_relevant is True


def test_metrics_report_to_dict():
    """RetrievalMetricsReport serializes to clean dict."""
    report = RetrievalMetricsReport(
        total_queries=5,
        hit_rate=0.8,
        mrr=0.65,
        map_score=0.55,
    )
    d = report.to_dict()
    assert d["total_queries"] == 5
    assert d["hit_rate"] == 0.8
    assert "ndcg_at_k" in d


# ── Core Metric Tests ─────────────────────────────────────────────────

def test_empty_results():
    """Empty input returns zero metrics."""
    report = compute_retrieval_metrics([])
    assert report.total_queries == 0
    assert report.hit_rate == 0.0
    assert report.mrr == 0.0


def test_perfect_retrieval():
    """All queries return relevant doc at rank 1."""
    queries = [
        ("q1", _make_docs(["r1", "r2", "r3"], {"r1"})),
        ("q2", _make_docs(["r4", "r5", "r6"], {"r4"})),
    ]
    report = compute_retrieval_metrics(queries, k_values=[5, 10])
    assert report.hit_rate == 1.0
    assert report.mrr == 1.0
    assert report.map_score == 1.0
    assert report.ndcg_at_k[5] == 1.0
    assert report.ndcg_at_k[10] == 1.0


def test_no_relevant_results():
    """No queries find relevant docs."""
    queries = [
        ("q1", _make_docs(["a", "b", "c"], set())),
        ("q2", _make_docs(["d", "e", "f"], set())),
    ]
    report = compute_retrieval_metrics(queries, k_values=[5])
    assert report.hit_rate == 0.0
    assert report.mrr == 0.0
    assert report.map_score == 0.0
    assert report.ndcg_at_k[5] == 0.0


def test_partial_retrieval():
    """Some queries find relevant docs at various ranks."""
    queries = [
        ("q1", _make_docs(["x", "r1", "y", "z"], {"r1"})),  # rank 2
        ("q2", _make_docs(["a", "b", "c", "d"], set())),     # not found
        ("q3", _make_docs(["r2", "a", "b"], {"r2"})),        # rank 1
    ]
    report = compute_retrieval_metrics(queries, k_values=[5, 10])

    # Hit rate: 2/3
    assert report.hit_rate == pytest.approx(2.0 / 3.0)

    # MRR: (1/2 + 0 + 1/1) / 3 = 0.5
    expected_mrr = (0.5 + 0.0 + 1.0) / 3.0
    assert report.mrr == pytest.approx(expected_mrr)

    # Total queries
    assert report.total_queries == 3


def test_ndcg_with_multiple_relevant():
    """nDCG when multiple relevant docs exist at different ranks."""
    docs = [
        RetrievedDocument(doc_id="r1", rank=1, is_relevant=True),
        RetrievedDocument(doc_id="n1", rank=2, is_relevant=False),
        RetrievedDocument(doc_id="r2", rank=3, is_relevant=True),
        RetrievedDocument(doc_id="n2", rank=4, is_relevant=False),
        RetrievedDocument(doc_id="r3", rank=5, is_relevant=True),
    ]
    queries = [("q1", docs)]
    report = compute_retrieval_metrics(queries, k_values=[5])

    # DCG = 1/log2(2) + 1/log2(4) + 1/log2(6) = 1 + 0.5 + 0.387
    dcg = 1.0 / math.log2(2) + 1.0 / math.log2(4) + 1.0 / math.log2(6)
    # IDCG = 1/log2(2) + 1/log2(3) + 1/log2(4) = 1 + 0.631 + 0.5
    idcg = 1.0 / math.log2(2) + 1.0 / math.log2(3) + 1.0 / math.log2(4)
    expected = dcg / idcg

    assert report.ndcg_at_k[5] == pytest.approx(expected, rel=0.01)


def test_precision_and_recall_at_k():
    """Precision@K and Recall@K computed correctly."""
    docs = [
        RetrievedDocument(doc_id="r1", rank=1, is_relevant=True),
        RetrievedDocument(doc_id="n1", rank=2, is_relevant=False),
        RetrievedDocument(doc_id="r2", rank=3, is_relevant=True),
        RetrievedDocument(doc_id="n2", rank=4, is_relevant=False),
        RetrievedDocument(doc_id="n3", rank=5, is_relevant=False),
        RetrievedDocument(doc_id="r3", rank=6, is_relevant=True),  # Beyond K=5
    ]
    queries = [("q1", docs)]
    report = compute_retrieval_metrics(queries, k_values=[5])

    # P@5: 2 relevant out of 5 = 0.4
    assert report.precision_at_k[5] == pytest.approx(0.4)

    # Recall@5: 2 out of 3 total relevant = 0.667
    assert report.recall_at_k[5] == pytest.approx(2.0 / 3.0)


def test_map_computation():
    """Mean Average Precision computed correctly."""
    # Query 1: r1 at rank 1, r2 at rank 3
    docs1 = _make_docs(["r1", "x", "r2"], {"r1", "r2"})
    # AP = (1/1 + 2/3) / 2 = (1 + 0.667) / 2 = 0.833
    ap1 = (1.0 / 1 + 2.0 / 3) / 2.0

    # Query 2: r3 at rank 2
    docs2 = _make_docs(["y", "r3"], {"r3"})
    # AP = (1/2) / 1 = 0.5
    ap2 = 0.5

    queries = [("q1", docs1), ("q2", docs2)]
    report = compute_retrieval_metrics(queries)
    expected_map = (ap1 + ap2) / 2.0
    assert report.map_score == pytest.approx(expected_map, rel=0.01)


# ── Convenience Function Test ──────────────────────────────────────────

def test_evaluate_search_results():
    """evaluate_search_results converts raw dicts to metrics correctly."""
    results = [
        {"id": "p1", "score": 0.95},
        {"id": "p2", "score": 0.85},
        {"id": "p3", "score": 0.75},
        {"id": "p4", "score": 0.65},
    ]
    relevant = {"p1", "p3"}

    report = evaluate_search_results(
        search_results=results,
        relevant_ids=relevant,
        query="test query",
    )

    assert report.total_queries == 1
    assert report.hit_rate == 1.0  # p1 at rank 1
    assert report.mrr == 1.0      # first relevant at rank 1


def test_evaluate_search_results_no_matches():
    """evaluate_search_results when no docs are relevant."""
    results = [
        {"id": "x1", "score": 0.9},
        {"id": "x2", "score": 0.8},
    ]
    report = evaluate_search_results(
        search_results=results,
        relevant_ids={"p1"},
        query="nothing matches",
    )
    assert report.hit_rate == 0.0
    assert report.mrr == 0.0
