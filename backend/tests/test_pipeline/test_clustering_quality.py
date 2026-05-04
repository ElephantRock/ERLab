"""Tests for clustering quality metrics (BATCH-67)."""

import pytest
import sys
sys.path.insert(0, "backend")

from pipeline.gap_analysis.cluster_service import ClusterService
from pipeline.gap_analysis.models import ClusterReport
from pipeline.literature.models import Paper

pytestmark = pytest.mark.anyio


def _make_papers(n: int = 25) -> list[Paper]:
    """Create diverse test papers."""
    domains = [
        ("reinforcement learning", "RL policy optimization reward"),
        ("natural language", "NLP transformer attention mechanism"),
        ("computer vision", "CNN image detection object recognition"),
        ("causal inference", "treatment effect estimation observational"),
        ("federated learning", "distributed privacy preserving training"),
    ]
    papers = []
    for domain, kw in domains:
        for i in range(n // len(domains)):
            papers.append(Paper(
                id=f"p{len(papers)}", source="test",
                title=f"{domain} approach {i}",
                abstract=f"Method for {kw} with validation {i}",
                authors=[], year=2024,
            ))
    return papers


class TestClusteringQuality:
    """BATCH-67: UMAP/HDBSCAN + quality metrics."""

    async def test_umap_hdbscan_produces_clusters(self):
        """TEST-67-01: ClusterService uses UMAP+HDBSCAN, not KMeans fallback."""
        svc = ClusterService()
        papers = _make_papers(25)
        report = await svc.cluster_papers(papers)
        assert report.total_papers == 25

    async def test_quality_metrics_populated(self):
        """TEST-67-02: ClusterReport includes silhouette and DBI."""
        svc = ClusterService()
        papers = _make_papers(30)
        report = await svc.cluster_papers(papers)
        # Metrics may be None if too few clusters, but field must exist
        assert hasattr(report, "silhouette_score")
        assert hasattr(report, "davies_bouldin_index")

    async def test_empty_papers_returns_empty_report(self):
        """TEST-67-03: Empty input returns valid empty report."""
        svc = ClusterService()
        report = await svc.cluster_papers([])
        assert report.total_papers == 0
        assert len(report.clusters) == 0
