"""Tests for BATCH-191: Consolidated Context Window (CCW).

AIV §13: Tests verify behavioral outcomes — compression reduces
token count, summaries are extracted correctly, format works for LLM prompts.
"""


from backend.pipeline.monitoring.ccw import (
    ConsolidatedContextWindow,
    _extract_first_sentence,
)


class TestExtractFirstSentence:
    """_extract_first_sentence produces useful summaries."""

    def test_01_normal_sentence(self):
        text = "This paper introduces a novel method for sparse attention. It achieves state-of-the-art results."
        result = _extract_first_sentence(text, max_chars=200)
        assert result == "This paper introduces a novel method for sparse attention."

    def test_02_long_text_truncated(self):
        text = "A" * 500
        result = _extract_first_sentence(text, max_chars=200)
        assert len(result) <= 203  # 200 + "..."
        assert result.endswith("...")

    def test_03_empty_input(self):
        assert _extract_first_sentence("") == ""

    def test_04_unicode_content(self):
        text = "Überprüfung der Qualität ist wichtig. Zweiter Satz."
        result = _extract_first_sentence(text, max_chars=200)
        assert "Überprüfung" in result

    def test_05_short_text_passes_through(self):
        text = "Short text"
        assert _extract_first_sentence(text, max_chars=200) == "Short text"

    def test_06_sentence_at_exact_boundary(self):
        text = "A" * 197 + ". Next"
        result = _extract_first_sentence(text, max_chars=200)
        assert len(result) == 198  # 197 chars + period


class TestConsolidatedContextWindow:
    """CCW compresses papers, gaps, ideas into summaries."""

    def _make_paper(self, pid="1", title="Test Paper", abstract="A" * 1000):
        """Create a mock paper object."""
        class MockPaper:
            pass
        p = MockPaper()
        p.id = pid
        p.title = title
        p.abstract = abstract
        p.year = 2025
        p.citation_count = 42
        return p

    def _make_gap(self, gid="g1", title="Test Gap", description="B" * 500):
        class MockGap:
            pass
        g = MockGap()
        g.id = gid
        g.title = title
        g.description = description
        g.confidence = 0.85
        g.gap_type = "methodological"
        return g

    def _make_idea(self, iid="i1", title="Test Idea", method="C" * 2000):
        class MockIdea:
            pass
        i = MockIdea()
        i.id = iid
        i.title = title
        i.proposed_method = method
        i.score = 0.92
        i.source_gap_ids = ["g1"]
        return i

    def test_07_papers_compressed(self):
        """Papers are compressed to title + summary."""
        ccw = ConsolidatedContextWindow()
        papers = [self._make_paper(str(i), f"Paper {i}", f"Abstract {i}. More text.") for i in range(30)]
        ccw.add_papers(papers)
        assert len(ccw.papers) == 30
        assert all(len(p.summary) <= 203 for p in ccw.papers)
        assert all(p.title == f"Paper {i}" for i, p in enumerate(ccw.papers))

    def test_08_gaps_compressed(self):
        """Gaps are compressed to title + summary."""
        ccw = ConsolidatedContextWindow()
        gaps = [self._make_gap(f"g{i}", f"Gap {i}", f"Description {i}. More.") for i in range(10)]
        ccw.add_gaps(gaps)
        assert len(ccw.gaps) == 10
        assert ccw.gaps[0].confidence == 0.85

    def test_09_ideas_compressed(self):
        """Ideas are compressed to title + summary."""
        ccw = ConsolidatedContextWindow()
        ideas = [self._make_idea(f"i{i}", f"Idea {i}", f"Method {i}. Details.") for i in range(5)]
        ccw.add_ideas(ideas)
        assert len(ccw.ideas) == 5
        assert ccw.ideas[0].score == 0.92

    def test_10_token_reduction_dramatic(self):
        """CCW reduces token count vs full content."""
        ccw = ConsolidatedContextWindow()
        papers = [self._make_paper(str(i), f"Paper {i}", f"Abstract {i}. " + "X" * 2000) for i in range(30)]
        ccw.add_papers(papers)

        # Full abstracts would be ~2000 chars * 30 = 60K chars = ~15K tokens
        full_tokens = sum(len(p.abstract if hasattr(p, 'abstract') else "") for p in papers) // 4
        ccw_tokens = ccw.estimate_tokens()

        # CCW should be dramatically smaller
        assert ccw_tokens < full_tokens * 0.15  # Less than 15% of full context

    def test_11_format_for_prompt(self):
        """format_for_prompt produces readable LLM input."""
        ccw = ConsolidatedContextWindow()
        ccw.add_papers([self._make_paper("1", "Transformer Paper", "Introduces self-attention mechanism.")])
        ccw.add_gaps([self._make_gap("g1", "MoE Routing Gap", "No systematic comparison of routing strategies.")])

        formatted = ccw.format_for_prompt()
        assert "Transformer Paper" in formatted
        assert "MoE Routing Gap" in formatted
        assert "Papers" in formatted
        assert "Gaps" in formatted

    def test_12_to_dict_serializable(self):
        """CCW serializes to JSON-compatible dict."""
        ccw = ConsolidatedContextWindow()
        ccw.add_papers([self._make_paper("1", "Test", "Abstract.")])
        d = ccw.to_dict()
        # Should be JSON-serializable
        json_str = __import__("json").dumps(d)
        assert "papers" in json_str

    def test_13_empty_ccw(self):
        """Empty CCW produces empty output."""
        ccw = ConsolidatedContextWindow()
        assert ccw.get_paper_summaries() == []
        assert ccw.get_gap_summaries() == []
        assert ccw.estimate_tokens() == 0

    def test_14_realistic_paper_content(self):
        """Test with realistic paper abstract."""
        abstract = (
            "We propose a novel mixture-of-experts architecture that dynamically routes tokens "
            "through sparse expert networks. Our approach achieves 2x speedup over dense transformers "
            "while maintaining 98% of model quality on standard benchmarks. The key innovation is a "
            "load-balancing auxiliary loss that prevents expert collapse."
        )
        ccw = ConsolidatedContextWindow()
        ccw.add_papers([self._make_paper("1", "Sparse MoE Architecture", abstract)])
        assert "mixture-of-experts" in ccw.papers[0].summary
        assert len(ccw.papers[0].summary) <= 203
