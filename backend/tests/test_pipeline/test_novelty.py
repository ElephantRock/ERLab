"""Unit tests for novelty checking stage."""

import asyncio
from unittest.mock import AsyncMock

from backend.pipeline.novelty.novelty_checker import NoveltyChecker, NoveltyReport
from backend.tests.conftest import FakeLLMProvider
from backend.tests.test_pipeline.conftest import (
    FakeVectorStore,
    SchemaAwareFakeProvider,
)


class TestFormatSimilar:
    def test_formats_with_metadata(self):
        similar = [
            {
                "metadata": {"paper_title": "Paper A"},
                "text": "Abstract text here",
                "distance": 0.3,
            }
        ]
        result = NoveltyChecker._format_similar(similar)
        assert "**Paper A**" in result
        assert "(distance: 0.300)" in result

    def test_handles_missing_metadata(self):
        similar = [{"text": "some text", "distance": 0.5}]
        result = NoveltyChecker._format_similar(similar)
        assert "Unknown" in result


class TestNoveltyChecker:
    def test_check_novelty_happy_path(self, sample_ideas, fake_store_with_results):
        checker = NoveltyChecker(SchemaAwareFakeProvider(), fake_store_with_results)
        report = asyncio.run(checker.check_novelty(sample_ideas[0]))
        assert isinstance(report, NoveltyReport)
        assert 0 <= report.overall_score <= 1.0
        assert 0 <= report.method_novelty <= 1.0
        assert 0 <= report.problem_novelty <= 1.0
        assert isinstance(report.novelty_arguments, str)

    def test_no_similar_papers(self, sample_ideas):
        checker = NoveltyChecker(SchemaAwareFakeProvider(), FakeVectorStore())
        report = asyncio.run(checker.check_novelty(sample_ideas[0]))
        assert report.overall_score == 0.8
        assert "No similar papers" in report.novelty_arguments
        assert report.closest_matches == []

    def test_with_similar_papers(self, sample_ideas, fake_store_with_results):
        provider = SchemaAwareFakeProvider()
        checker = NoveltyChecker(provider, fake_store_with_results)
        asyncio.run(checker.check_novelty(sample_ideas[0]))
        assert len(provider._call_log) == 1

    def test_scores_clamped(self, sample_ideas, fake_store_with_results):
        provider = FakeLLMProvider(
            responses={
                "structured_output": {
                    "overall_score": 1.5,
                    "method_novelty": -0.3,
                    "problem_novelty": 0.5,
                    "domain_transfer": 2.0,
                    "combination_novelty": 0.7,
                    "novelty_arguments": "test",
                }
            }
        )
        checker = NoveltyChecker(provider, fake_store_with_results)
        report = asyncio.run(checker.check_novelty(sample_ideas[0]))
        assert report.overall_score == 1.0
        assert report.method_novelty == 0.0
        assert report.domain_transfer == 1.0

    def test_llm_failure_distance_fallback(self, sample_ideas, fake_store_with_results):
        provider = SchemaAwareFakeProvider()

        async def _fail(*args, **kwargs):
            raise RuntimeError("LLM error")

        provider.structured_output = _fail
        checker = NoveltyChecker(provider, fake_store_with_results)
        report = asyncio.run(checker.check_novelty(sample_ideas[0]))
        assert isinstance(report, NoveltyReport)
        assert "Fallback" in report.novelty_arguments

    def test_llm_failure_fallback_populates_closest(self, sample_ideas, fake_store_with_results):
        provider = SchemaAwareFakeProvider()

        async def _fail(*args, **kwargs):
            raise RuntimeError("LLM error")

        provider.structured_output = _fail
        checker = NoveltyChecker(provider, fake_store_with_results)
        report = asyncio.run(checker.check_novelty(sample_ideas[0]))
        assert len(report.closest_matches) > 0
        assert report.closest_matches[0]["title"] == "Similar Paper"

    def test_closest_matches_populated(self, sample_ideas, fake_store_with_results):
        provider = SchemaAwareFakeProvider()
        checker = NoveltyChecker(provider, fake_store_with_results)
        report = asyncio.run(checker.check_novelty(sample_ideas[0]))
        assert len(report.closest_matches) > 0
        assert "title" in report.closest_matches[0]
        assert "distance" in report.closest_matches[0]

    def test_top_k_respected(self, sample_ideas):
        store = AsyncMock(spec=FakeVectorStore)
        store.query = AsyncMock(return_value=[])
        store.query_by_embedding = AsyncMock(return_value=[])
        checker = NoveltyChecker(SchemaAwareFakeProvider(), store)
        asyncio.run(checker.check_novelty(sample_ideas[0], top_k=5))
        store.query.assert_called_once()
        call_kwargs = store.query.call_args
        assert call_kwargs.kwargs.get("n_results") == 5 or (len(call_kwargs.args) >= 2 and call_kwargs.args[1] == 5)

    def test_retriever_path(self, sample_ideas, fake_store_with_results):
        retriever = AsyncMock()
        retriever.retrieve = AsyncMock(return_value=[])
        checker = NoveltyChecker(SchemaAwareFakeProvider(), fake_store_with_results, retriever=retriever)
        report = asyncio.run(checker.check_novelty(sample_ideas[0]))
        retriever.retrieve.assert_called_once()
        assert report.overall_score == 0.8
