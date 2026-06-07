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
    def test_with_similar_papers(self, sample_ideas, fake_store_with_results):
        provider = SchemaAwareFakeProvider()
        checker = NoveltyChecker(provider, fake_store_with_results)
        asyncio.run(checker.check_novelty(sample_ideas[0]))
        assert len(provider._call_log) == 1

    def test_top_k_respected(self, sample_ideas):
        store = AsyncMock(spec=FakeVectorStore)
        store.query = AsyncMock(return_value=[])
        store.query_by_embedding = AsyncMock(return_value=[])
        checker = NoveltyChecker(SchemaAwareFakeProvider(), store)
        asyncio.run(checker.check_novelty(sample_ideas[0], top_k=5))
        store.query.assert_called_once()
        call_kwargs = store.query.call_args
        assert call_kwargs.kwargs.get("n_results") == 5 or (len(call_kwargs.args) >= 2 and call_kwargs.args[1] == 5)
