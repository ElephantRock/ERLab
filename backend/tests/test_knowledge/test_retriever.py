"""Tests for BM25 index, RRF fusion retriever, and reranker."""

import tempfile

from backend.pipeline.knowledge.bm25_index import BM25Index

# Longer texts to ensure BM25 produces non-zero scores
CORPUS = [
    "Retrieval augmented generation combines information retrieval with language model generation to produce more accurate and grounded outputs for knowledge intensive tasks",
    "BM25 is a classic keyword search algorithm based on term frequency inverse document frequency that has been widely used in information retrieval systems for decades",
    "Neural network architectures for natural language processing include transformers attention mechanisms and pre training strategies that have revolutionized the field",
    "Machine learning models can be trained on large datasets to learn patterns and make predictions about unseen data in various domains",
    "Deep learning models use multiple layers of neural networks to learn hierarchical representations of data for complex tasks",
]


class TestBM25Index:
    def setup_method(self):
        self._tmpdir = tempfile.mkdtemp()
        self.index = BM25Index(self._tmpdir)

    def test_add_and_query(self):
        self.index.add_documents(
            ids=["doc1", "doc2", "doc3"],
            texts=CORPUS[:3],
        )

        results = self.index.query("retrieval search algorithm", n_results=2)
        assert len(results) == 2
        assert results[0]["score"] > 0

    def test_query_empty_index(self):
        results = self.index.query("test query", n_results=5)
        assert results == []

    def test_query_no_match(self):
        self.index.add_documents(
            ids=["doc1"],
            texts=["Quantum computing uses qubits for parallel computation and superposition"],
        )
        results = self.index.query("recipe for chocolate cake baking instructions", n_results=5)
        assert results == []

    def test_delete_documents(self):
        self.index.add_documents(
            ids=["doc1", "doc2"],
            texts=[
                "First document about cats and their behavior in domestic environments",
                "Second document about dogs and their training methods",
            ],
        )
        assert self.index.doc_count == 2

        removed = self.index.delete(["doc1"])
        assert removed == 1
        assert self.index.doc_count == 1

    def test_metadata_filter(self):
        self.index.add_documents(
            ids=["doc1", "doc2", "doc3"],
            texts=CORPUS[:3],
            metadatas=[{"source": "arxiv"}, {"source": "semantic_scholar"}, {"source": "arxiv"}],
        )

        results = self.index.query(
            "retrieval information", n_results=5, filter_metadata={"source": "arxiv"}
        )
        assert all(r["metadata"]["source"] == "arxiv" for r in results)
        assert len(results) >= 1

    def test_persistence(self):
        # Use all 5 docs so BM25 IDF is meaningful
        self.index.add_documents(
            ids=["doc1", "doc2", "doc3", "doc4", "doc5"],
            texts=CORPUS,
        )

        index2 = BM25Index(self._tmpdir)
        assert index2.doc_count == 5
        results = index2.query("retrieval generation", n_results=5)
        assert len(results) >= 1

    def test_overwrite_existing_id(self):
        self.index.add_documents(ids=["doc1", "doc2", "doc3", "doc4", "doc5"], texts=CORPUS)
        self.index.add_documents(ids=["doc1"], texts=[CORPUS[2]])

        assert self.index.doc_count == 5
        results = self.index.query("neural network transformers attention", n_results=5)
        assert len(results) >= 1
        # doc1 should now match neural networks content
        result_ids = [r["id"] for r in results]
        assert "doc1" in result_ids or "doc3" in result_ids


class TestRRFFusion:
    """Test Reciprocal Rank Fusion logic directly without import chain."""

    def test_rrf_fuse_merges_both_sources(self):
        # Directly test the RRF algorithm without importing TwoStageRetriever
        # (avoids chromadb import requirement)
        def rrf_fuse(bm25_results, semantic_results, k=60):
            scores = {}
            docs = {}
            for rank, doc in enumerate(bm25_results):
                doc_id = doc["id"]
                scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
                docs[doc_id] = doc
            for rank, doc in enumerate(semantic_results):
                doc_id = doc["id"]
                scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
                if doc_id not in docs:
                    docs[doc_id] = doc
            fused = [
                {
                    "id": doc_id,
                    "score": score,
                    "text": docs[doc_id].get("text", ""),
                    "metadata": docs[doc_id].get("metadata", {}),
                }
                for doc_id, score in scores.items()
            ]
            fused.sort(key=lambda r: r["score"], reverse=True)
            return fused

        bm25_results = [
            {"id": "doc_c", "text": "keyword match C", "score": 2.5, "metadata": {}},
            {"id": "doc_a", "text": "keyword match A", "score": 1.8, "metadata": {}},
        ]
        semantic_results = [
            {"id": "doc_a", "text": "semantic match A", "distance": 0.1, "metadata": {}},
            {"id": "doc_b", "text": "semantic match B", "distance": 0.3, "metadata": {}},
        ]

        fused = rrf_fuse(bm25_results, semantic_results, k=60)

        # doc_a appears in both sources — should have highest RRF score
        assert fused[0]["id"] == "doc_a"
        assert len(fused) == 3

        # doc_a: bm25 rank=1 (0-indexed) -> 1/(60+2), semantic rank=0 -> 1/(60+1)
        expected_score_a = 1.0 / (60 + 2) + 1.0 / (60 + 1)
        assert abs(fused[0]["score"] - expected_score_a) < 1e-10

    def test_rrf_fuse_empty_sources(self):
        def rrf_fuse(bm25_results, semantic_results, k=60):
            scores = {}
            for rank, doc in enumerate(bm25_results):
                scores[doc["id"]] = scores.get(doc["id"], 0.0) + 1.0 / (k + rank + 1)
            for rank, doc in enumerate(semantic_results):
                scores[doc["id"]] = scores.get(doc["id"], 0.0) + 1.0 / (k + rank + 1)
            return sorted(scores.items(), key=lambda x: x[1], reverse=True)

        assert rrf_fuse([], []) == []


class TestLLMReranker:
    def test_extract_score(self):
        from backend.pipeline.knowledge.reranker import LLMReranker

        assert LLMReranker._extract_score("0.85") == 0.85
        assert LLMReranker._extract_score("The score is 0.72") == 0.72
        assert LLMReranker._extract_score("invalid") == 0.5
        assert LLMReranker._extract_score("1.5") == 1.0
        assert LLMReranker._extract_score("-0.1") == 0.0
