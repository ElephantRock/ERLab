"""Topic clustering service using UMAP + HDBSCAN."""

import logging

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from backend.pipeline.gap_analysis.models import ClusterInfo, ClusterReport
from backend.pipeline.literature.models import Paper

logger = logging.getLogger(__name__)


class ClusterService:
    """Cluster papers by topic using embeddings and TF-IDF."""

    async def cluster_papers(
        self,
        papers: list[Paper],
        min_cluster_size: int = 3,
    ) -> ClusterReport:
        """Cluster papers and return a report with labeled clusters."""
        if len(papers) < min_cluster_size:
            logger.warning("Too few papers (%d) for clustering, min=%d", len(papers), min_cluster_size)
            return ClusterReport(total_papers=len(papers))

        # Get embeddings or fall back to TF-IDF
        embeddings = self._get_embeddings(papers)

        # Reduce to 2D with UMAP
        reduced = self._reduce_dimensions(embeddings)

        # Cluster with HDBSCAN
        labels = self._cluster(reduced, min_cluster_size)

        # Label clusters with top TF-IDF terms
        cluster_infos = self._build_cluster_info(papers, labels)

        return ClusterReport(
            clusters=cluster_infos,
            total_papers=len(papers),
        )

    def _get_embeddings(self, papers: list[Paper]) -> np.ndarray:
        """Extract embeddings or build TF-IDF from abstracts."""
        has_embeddings = any(p.embedding for p in papers)

        if has_embeddings:
            embeddings = []
            for p in papers:
                if p.embedding:
                    embeddings.append(p.embedding)
                else:
                    embeddings.append([0.0] * len(papers[0].embedding or [0.0] * 1536))
            return np.array(embeddings)

        # Fallback: TF-IDF on titles + abstracts
        texts = [f"{p.title} {p.abstract or ''}" for p in papers]
        vectorizer = TfidfVectorizer(max_features=500, stop_words="english")
        tfidf_matrix = vectorizer.fit_transform(texts)
        return tfidf_matrix.toarray()

    def _reduce_dimensions(self, embeddings: np.ndarray) -> np.ndarray:
        """Reduce to 2D with UMAP for clustering."""
        try:
            import umap

            n_neighbors = min(15, len(embeddings) - 1)
            reducer = umap.UMAP(
                n_components=2,
                n_neighbors=max(2, n_neighbors),
                min_dist=0.1,
                metric="cosine",
                random_state=42,
            )
            return reducer.fit_transform(embeddings)
        except ImportError:
            logger.warning("UMAP not available, using first 2 dimensions")
            return embeddings[:, :2] if embeddings.shape[1] >= 2 else embeddings

    def _cluster(self, reduced: np.ndarray, min_cluster_size: int) -> np.ndarray:
        """Cluster with HDBSCAN."""
        try:
            import hdbscan

            clusterer = hdbscan.HDBSCAN(
                min_cluster_size=max(2, min_cluster_size),
                metric="euclidean",
            )
            return clusterer.fit_predict(reduced)
        except ImportError:
            logger.warning("HDBSCAN not available, using KMeans fallback")
            from sklearn.cluster import KMeans

            n_clusters = max(2, len(reduced) // min_cluster_size)
            kmeans = KMeans(n_clusters=min(n_clusters, 10), random_state=42, n_init=10)
            return kmeans.fit_predict(reduced)

    def _build_cluster_info(
        self,
        papers: list[Paper],
        labels: np.ndarray,
    ) -> list[ClusterInfo]:
        """Build cluster info with TF-IDF labels."""
        clusters = {}

        for i, label in enumerate(labels):
            if label == -1:  # Noise cluster from HDBSCAN
                continue
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(papers[i])

        cluster_infos = []
        for cluster_id, cluster_papers in clusters.items():
            # Extract top terms via TF-IDF
            texts = [f"{p.title} {p.abstract or ''}" for p in cluster_papers]
            try:
                vectorizer = TfidfVectorizer(max_features=100, stop_words="english")
                vectorizer.fit(texts)
                top_terms = list(vectorizer.vocabulary_.keys())[:10]
            except ValueError:
                top_terms = []

            avg_citations = None
            citation_counts = [p.citation_count for p in cluster_papers if p.citation_count is not None]
            if citation_counts:
                avg_citations = sum(citation_counts) / len(citation_counts)

            cluster_infos.append(ClusterInfo(
                cluster_id=int(cluster_id),
                label=" / ".join(top_terms[:3]) if top_terms else f"Cluster {cluster_id}",
                paper_count=len(cluster_papers),
                top_terms=top_terms,
                avg_citations=avg_citations,
            ))

        return sorted(cluster_infos, key=lambda c: c.paper_count, reverse=True)
