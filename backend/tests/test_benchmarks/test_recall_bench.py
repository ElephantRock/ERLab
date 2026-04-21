"""Recall quality benchmarks: substring vs BM25 vs hybrid RRF."""

import tempfile

import pytest

from backend.pipeline.knowledge.bm25_index import BM25Index

pytestmark = pytest.mark.slow

QUERY_TOPICS = [
    "transformer attention",
    "retrieval augmented generation",
    "knowledge graph embedding",
    "contrastive learning",
    "few-shot learning",
    "neural machine translation",
    "sentiment analysis",
    "text summarization",
    "question answering",
    "cross-lingual transfer",
]


def _make_test_collection():
    corpus = []
    queries = []
    relevant = {}

    for qi, topic in enumerate(QUERY_TOPICS):
        queries.append(topic)
        rel_ids = set()
        for di in range(5):
            doc_id = f"rel_{qi}_{di}"
            text = (
                f"This paper presents {topic} methodology. The {topic} approach "
                f"achieves state-of-the-art results. {topic} is the core contribution."
            )
            corpus.append((doc_id, text))
            rel_ids.add(doc_id)
        for di in range(195):
            corpus.append(
                (f"dist_{qi}_{di}", f"Distractor document about unrelated topic number {di}")
            )
        relevant[qi] = rel_ids

    return corpus, queries, relevant


def _recall_at_k(retrieved_ids, relevant_ids, k=10):
    retrieved_set = set(retrieved_ids[:k])
    if not relevant_ids:
        return 0.0
    return len(retrieved_set & relevant_ids) / len(relevant_ids)


class TestRecallBenchmark:
    def test_substring_recall_at_10(self):
        corpus, queries, relevant = _make_test_collection()
        ids = [c[0] for c in corpus]
        texts = [c[1] for c in corpus]

        recalls = []
        for qi, query in enumerate(queries):
            query_lower = query.lower()
            scored = [(i, texts[i].lower().count(query_lower)) for i in range(len(texts))]
            scored.sort(key=lambda x: x[1], reverse=True)
            retrieved = [ids[i] for i, _ in scored[:10]]
            recalls.append(_recall_at_k(retrieved, relevant[qi]))

        avg = sum(recalls) / len(recalls)
        assert avg > 0

    def test_bm25_recall_at_10(self):
        corpus, queries, relevant = _make_test_collection()
        ids = [c[0] for c in corpus]
        texts = [c[1] for c in corpus]

        with tempfile.TemporaryDirectory() as tmp:
            bm25 = BM25Index(f"{tmp}/bm25_recall")
            bm25.add_documents(ids, texts)

            recalls = []
            for qi, query in enumerate(queries):
                results = bm25.query(query, n_results=10)
                retrieved = [r["id"] for r in results]
                recalls.append(_recall_at_k(retrieved, relevant[qi]))

            avg = sum(recalls) / len(recalls)
            assert avg > 0

    def test_hybrid_rrf_recall_at_10(self):
        corpus, queries, relevant = _make_test_collection()
        ids = [c[0] for c in corpus]
        texts = [c[1] for c in corpus]

        with tempfile.TemporaryDirectory() as tmp:
            bm25 = BM25Index(f"{tmp}/bm25_hybrid")
            bm25.add_documents(ids, texts)

            recalls_bm25 = []
            recalls_hybrid = []

            for qi, query in enumerate(queries):
                bm25_results = bm25.query(query, n_results=10)
                bm25_ids = [r["id"] for r in bm25_results]
                recalls_bm25.append(_recall_at_k(bm25_ids, relevant[qi]))

                # Simulate semantic results: shuffle BM25 results to mimic different ranking
                import random

                random.seed(qi)
                sem_ids = list(ids)
                random.shuffle(sem_ids)
                sem_results = [{"id": eid, "text": "", "metadata": {}} for eid in sem_ids[:20]]

                # RRF fusion
                k = 60
                scores = {}
                for rank, doc in enumerate(bm25_results):
                    scores[doc["id"]] = scores.get(doc["id"], 0.0) + 1.0 / (k + rank + 1)
                for rank, doc in enumerate(sem_results):
                    scores[doc["id"]] = scores.get(doc["id"], 0.0) + 1.0 / (k + rank + 1)
                fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                fused_ids = [fid for fid, _ in fused[:10]]
                recalls_hybrid.append(_recall_at_k(fused_ids, relevant[qi]))

            avg_bm25 = sum(recalls_bm25) / len(recalls_bm25)
            avg_hybrid = sum(recalls_hybrid) / len(recalls_hybrid)
            assert avg_hybrid >= avg_bm25 * 0.8  # Hybrid should be comparable or better
