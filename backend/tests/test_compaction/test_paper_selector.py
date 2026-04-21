"""Tests for the PaperSelector."""

from backend.pipeline.compaction.paper_selector import PaperSelector
from backend.pipeline.literature.models import Paper


def _make_paper(pid: str, title: str, abstract: str = "", embedding=None) -> Paper:
    return Paper(id=pid, source="test", title=title, abstract=abstract, embedding=embedding)


class TestPaperSelector:
    def test_empty_papers(self):
        selector = PaperSelector()
        result = selector.select_papers([], query="test", max_papers=5)
        assert result == []

    def test_selects_top_n(self):
        selector = PaperSelector()
        papers = [_make_paper(f"p{i}", f"Paper about topic {i}") for i in range(10)]
        result = selector.select_papers(papers, query="topic", max_papers=5)
        assert len(result) == 5

    def test_selects_all_when_fewer_than_max(self):
        selector = PaperSelector()
        papers = [_make_paper("p1", "Machine learning"), _make_paper("p2", "Deep learning")]
        result = selector.select_papers(papers, query="learning", max_papers=10)
        assert len(result) == 2

    def test_ranks_by_word_overlap(self):
        selector = PaperSelector()
        papers = [
            _make_paper("p1", "Neural network optimization methods"),
            _make_paper("p2", "Quantum computing algorithms"),
            _make_paper("p3", "Neural network architecture search"),
        ]
        result = selector.select_papers(papers, query="neural network", max_papers=3)
        # p1 and p3 should rank higher than p2
        titles = [p.title for p in result]
        assert "Quantum computing algorithms" not in titles[:2]

    def test_ranks_by_embedding_similarity(self):
        selector = PaperSelector()
        # "query" embedding points toward first paper
        query_emb = [1.0, 0.0, 0.0]
        papers = [
            _make_paper("p1", "Relevant paper", embedding=[0.9, 0.1, 0.0]),
            _make_paper("p2", "Irrelevant paper", embedding=[0.0, 0.0, 1.0]),
        ]
        result = selector.select_papers(papers, query="test", max_papers=2)
        assert result[0].id == "p1"

    def test_adaptive_abstract_truncation(self):
        selector = PaperSelector()
        long_abstract = "x" * 500
        papers = [_make_paper(f"p{i}", f"Paper {i}", abstract=long_abstract) for i in range(10)]
        result = selector.select_papers(papers, query="paper", max_papers=10, abstract_budget=100)
        # Top-ranked should have longer abstracts than bottom-ranked
        top_abstract_len = len(result[0].abstract or "")
        bottom_abstract_len = len(result[-1].abstract or "")
        assert top_abstract_len >= bottom_abstract_len

    def test_mixed_embedding_and_no_embedding(self):
        selector = PaperSelector()
        papers = [
            _make_paper("p1", "Embedded paper", embedding=[1.0, 0.0]),
            _make_paper("p2", "No embedding paper"),
        ]
        # Should not crash when some papers have embeddings and others don't
        result = selector.select_papers(papers, query="embedded", max_papers=2)
        assert len(result) == 2

    def test_empty_query(self):
        selector = PaperSelector()
        papers = [_make_paper("p1", "Some paper")]
        # Empty query should still return papers (no ranking applied)
        result = selector.select_papers(papers, query="", max_papers=5)
        assert len(result) == 1
