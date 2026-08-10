"""Tests for ContextIsolator and BufferedErrorTaxonomy."""


from backend.pipeline.gap_analysis.models import ResearchGap
from backend.pipeline.generation.buffered_taxonomy import BufferedErrorTaxonomy
from backend.pipeline.generation.context_isolator import ContextIsolator
from backend.pipeline.generation.error_taxonomy import ErrorCategory, ErrorTaxonomy
from backend.pipeline.literature.models import Paper


def _make_paper(pid: str, title: str, abstract: str = "Abstract") -> Paper:
    return Paper(id=pid, source="test", title=title, abstract=abstract)


def _make_gap(title: str, desc: str = "Description") -> ResearchGap:
    return ResearchGap(title=title, description=desc, gap_type="test", confidence=0.5)


class TestContextIsolator:
    def test_isolated_context_returns_deep_copies(self):
        papers = [_make_paper("p1", "Paper 1")]
        gaps = [_make_gap("Gap 1")]
        isolator = ContextIsolator(gaps, papers)

        gaps_copy, papers_copy = isolator.isolated_context()
        # Mutate copies
        gaps_copy[0].title = "MUTATED"
        papers_copy[0].title = "MUTATED"

        assert gaps[0].title == "Gap 1"
        assert papers[0].title == "Paper 1"

    def test_isolated_context_for_single_gap(self):
        papers = [_make_paper("p1", "Paper 1"), _make_paper("p2", "Paper 2")]
        gaps = [_make_gap("Gap 1"), _make_gap("Gap 2")]
        isolator = ContextIsolator(gaps, papers)

        gaps_copy, papers_copy = isolator.isolated_context_for_gap(gaps[0])
        assert len(gaps_copy) == 1
        assert gaps_copy[0].title == "Gap 1"
        assert len(papers_copy) == 2

    def test_isolated_context_for_gap_does_not_affect_original(self):
        gap = _make_gap("Original")
        isolator = ContextIsolator([gap], [_make_paper("p1", "P1")])

        gaps_copy, _ = isolator.isolated_context_for_gap(gap)
        gaps_copy[0].title = "MUTATED"

        assert gap.title == "Original"

    def test_empty_gaps_and_papers(self):
        isolator = ContextIsolator([], [])
        gaps, papers = isolator.isolated_context()
        assert gaps == []
        assert papers == []

    def test_multiple_isolations_are_independent(self):
        gap = _make_gap("Gap")
        isolator = ContextIsolator([gap], [_make_paper("p1", "P")])

        gaps1, _ = isolator.isolated_context_for_gap(gap)
        gaps2, _ = isolator.isolated_context_for_gap(gap)
        gaps1[0].title = "MUTATED1"
        gaps2[0].title = "MUTATED2"

        assert gap.title == "Gap"


class TestBufferedErrorTaxonomy:
    def test_buffers_records(self, tmp_path):
        real = ErrorTaxonomy(str(tmp_path / "taxonomy.json"))
        buffered = BufferedErrorTaxonomy(real)

        buffered.record(ErrorCategory.METHODOLOGICAL, "test desc")
        assert buffered.buffer_size == 1
        # Real taxonomy should not have it yet
        assert sum(real._counts.values()) == 0

    def test_flush_writes_to_real(self, tmp_path):
        real = ErrorTaxonomy(str(tmp_path / "taxonomy.json"))
        buffered = BufferedErrorTaxonomy(real)

        buffered.record(ErrorCategory.METHODOLOGICAL, "test desc 1")
        buffered.record(ErrorCategory.NOVELTY, "test desc 2")
        buffered.flush()

        assert sum(real._counts.values()) == 2
        assert buffered.buffer_size == 0

    def test_classify_delegates_to_real(self, tmp_path):
        real = ErrorTaxonomy(str(tmp_path / "taxonomy.json"))
        buffered = BufferedErrorTaxonomy(real)

        result = buffered.classify("weak evaluation metrics")
        assert result is not None

    def test_format_prompt_delegates(self, tmp_path):
        real = ErrorTaxonomy(str(tmp_path / "taxonomy.json"))
        buffered = BufferedErrorTaxonomy(real)

        real.record(ErrorCategory.METHODOLOGICAL, "test")
        text = buffered.format_prompt_section()
        assert "methodological" in text

    def test_multiple_flushes(self, tmp_path):
        real = ErrorTaxonomy(str(tmp_path / "taxonomy.json"))
        buffered = BufferedErrorTaxonomy(real)

        buffered.record(ErrorCategory.METHODOLOGICAL, "first")
        buffered.flush()
        buffered.record(ErrorCategory.NOVELTY, "second")
        buffered.flush()

        assert sum(real._counts.values()) == 2
