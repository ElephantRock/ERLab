"""Unit tests for gap analysis stage."""

import asyncio

import pytest

from backend.pipeline.gap_analysis.gap_analyzer import (
    GapAnalysisExecutionError,
    GapAnalyzer,
    _title_similarity,
)
from backend.pipeline.gap_analysis.models import ClusterInfo, ClusterReport, ResearchGap
from backend.tests.test_pipeline.conftest import SchemaAwareFakeProvider


class _GapJSONFakeProvider(SchemaAwareFakeProvider):
    """Provider whose structured_output() returns a valid typed gap payload.

    Gap analysis is routed through structured_output() (the canonical
    analyzer entrypoint). Returns all six required gap fields so the
    typed contract validator accepts the payload.
    """

    async def structured_output(self, messages, schema, temperature=0.3, max_tokens=4096):  # noqa: ARG002
        return {
            "gaps": [
                {
                    "title": "Novel approach to research methodology",
                    "description": "A structurally valid research gap",
                    "gap_type": "methodological",
                    "related_clusters": [0],
                    "potential_impact": "High",
                    "confidence": 0.8,
                },
            ]
        }


class TestTitleSimilarity:
    def test_identical(self):
        assert _title_similarity("Machine Learning for NLP", "Machine Learning for NLP") == 1.0

    def test_no_overlap(self):
        score = _title_similarity("Machine Learning", "Quantum Computing")
        assert score < 0.3

    def test_partial_overlap(self):
        score = _title_similarity(
            "Deep Learning for NLP", "Deep Learning for Computer Vision"
        )
        assert 0 < score < 1.0

    def test_case_insensitive(self):
        assert _title_similarity("machine learning", "Machine Learning") == 1.0

    def test_empty_string(self):
        assert _title_similarity("", "Some Title") == 0.0
        assert _title_similarity("Some Title", "") == 0.0


class TestFormatClusters:
    def test_with_citations(self):
        report = ClusterReport(
            clusters=[
                ClusterInfo(
                    cluster_id=0, label="NLP", paper_count=5, avg_citations=12.3
                )
            ],
            total_papers=5,
        )
        result = GapAnalyzer._format_clusters(report)
        assert "Cluster 0 (NLP): 5 papers" in result
        assert "12.3" in result

    def test_without_citations(self):
        report = ClusterReport(
            clusters=[
                ClusterInfo(cluster_id=0, label="ML", paper_count=3, avg_citations=None)
            ],
            total_papers=3,
        )
        result = GapAnalyzer._format_clusters(report)
        assert "Cluster 0 (ML): 3 papers" in result
        assert "avg citations" not in result


class TestFormatPaperSummaries:
    def test_formats_paper_list(self, sample_papers):
        result = GapAnalyzer._format_paper_summaries(sample_papers)
        assert "1." in result
        assert "2." in result
        assert "Test Paper 1" in result

    def test_limits_to_30(self):
        from backend.pipeline.literature.models import Paper

        papers = [
            Paper(id=f"p{i}", source="test", title=f"Paper {i}", year=2024)
            for i in range(35)
        ]
        result = GapAnalyzer._format_paper_summaries(papers)
        # Each paper produces 2 lines: title + abstract, so 30 papers = 60 lines
        numbered_entries = [line for line in result.split("\n") if line.strip() and line.strip()[0].isdigit()]
        assert len(numbered_entries) == 30


class TestGapAnalyzer:
    def test_analyze_happy_path(self, many_papers):
        provider = _GapJSONFakeProvider()
        analyzer = GapAnalyzer(provider)
        gaps, report = asyncio.run(analyzer.analyze(many_papers, max_gaps=2))
        assert isinstance(gaps, list)
        assert isinstance(report, ClusterReport)
        if gaps:
            for g in gaps:
                assert g.title
                assert 0 <= g.confidence <= 1.0

    def test_analyze_with_prior_gaps(self, many_papers):
        provider = _GapJSONFakeProvider()
        analyzer = GapAnalyzer(provider)
        prior = [
            ResearchGap(
                title="Novel approach to research methodology",
                description="Prior gap",
                gap_type="methodological",
                confidence=0.7,
            )
        ]
        gaps, _ = asyncio.run(analyzer.analyze(many_papers, prior_gaps=prior))
        assert isinstance(gaps, list)

    def test_analyze_llm_failure(self, many_papers):
        provider = _GapJSONFakeProvider()

        async def _fail(*args, **kwargs):
            raise RuntimeError("LLM down")

        # An exhausted provider failure must surface as a typed execution
        # error, NOT be swallowed into an empty gap list. See the gap-contract
        # outcome matrix: "No execution failure becomes []".
        provider.structured_output = _fail
        analyzer = GapAnalyzer(provider)
        with pytest.raises(GapAnalysisExecutionError):
            asyncio.run(analyzer.analyze(many_papers))

    def test_analyze_sorted_by_confidence(self, many_papers):
        provider = _GapJSONFakeProvider()
        analyzer = GapAnalyzer(provider)
        gaps, _ = asyncio.run(analyzer.analyze(many_papers, max_gaps=5))
        if len(gaps) > 1:
            for i in range(len(gaps) - 1):
                assert gaps[i].confidence >= gaps[i + 1].confidence
