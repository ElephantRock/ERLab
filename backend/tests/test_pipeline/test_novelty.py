"""Unit tests for novelty checking stage."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.pipeline.novelty.novelty_checker import (
    GovernedEmbeddingNotConfiguredError,
    NoveltyChecker,
    NoveltyReport,
)
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


# ─── P0.4B0.0 — governed novelty regression ──────────────────────────────


class _FakeGovernedRuntime:
    """Minimal stand-in for the fields ``_retrieve_governed`` reads.

    B0.6: GovernedVectorRuntime now has effective_embedding_config instead
    of separate embedding_profile_id/profile_dict fields.
    """

    def __init__(self) -> None:
        # Create a minimal object that has embedding_profile_id
        self.effective_embedding_config = MagicMock(
            embedding_profile_id="profile_test"
        )
        self.backend = MagicMock(name="governed_backend")
        self.session_factory = MagicMock(name="session_factory")
        self.embedding_adapter = MagicMock(name="embedding_adapter")


class _FakeGovernedEmbedding:
    """Satisfies ``GovernedEmbeddingProtocol`` (embed_texts only)."""

    def __init__(self, vectors: list[list[float]] | None = None) -> None:
        # ``vectors is None`` check so callers can pass ``[]`` explicitly
        # to exercise the empty-result short-circuit branch.
        self._vectors = [[0.1, 0.2, 0.3]] if vectors is None else vectors
        self.call_count = 0

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.call_count += 1
        return self._vectors


def _governed_novelty_checker(*, governed_embedding=None) -> NoveltyChecker:
    """Construct a NoveltyChecker wired for the governed path.

    Provider/store are stubs; they are not reached on the governed path
    because ``check_novelty`` short-circuits into ``_retrieve_governed``
    when ``run_id`` + ``db_engine`` are supplied and the provenance
    contract resolves to ``governed``.
    """
    store = AsyncMock(spec=FakeVectorStore)
    store.query = AsyncMock(return_value=[])
    store.query_by_embedding = AsyncMock(return_value=[])
    return NoveltyChecker(
        provider=SchemaAwareFakeProvider(),
        store=store,
        governed_runtime=_FakeGovernedRuntime(),
        governed_embedding=governed_embedding,
    )


class TestGovernedNoveltyEmbeddingDependency:
    """P0.4B0.0 BLOCKER #1 regression: ``_retrieve_governed`` must not raise
    ``AttributeError`` and must not fall back to legacy when the governed
    embedding dependency is missing. Miswired composition fails closed."""

    def test_missing_dependency_raises_explicit_error(self, sample_ideas):
        checker = _governed_novelty_checker(governed_embedding=None)

        with patch(
            "backend.pipeline.provenance_gate.select_run_execution_mode",
            return_value="governed",
        ), patch(
            "backend.pipeline.provenance_gate.load_run_provenance_contract",
            return_value=MagicMock(name="contract"),
        ):
            with pytest.raises(GovernedEmbeddingNotConfiguredError) as excinfo:
                asyncio.run(
                    checker.check_novelty(
                        sample_ideas[0],
                        run_id=1,
                        db_engine=MagicMock(name="db_engine"),
                    )
                )

        # Explicit, actionable failure message — not AttributeError
        msg = str(excinfo.value)
        assert "governed_embedding" in msg
        assert "governed novelty retrieval" in msg

    def test_with_dependency_calls_embed_texts(self, sample_ideas):
        embedding = _FakeGovernedEmbedding(vectors=[[0.4, 0.5, 0.6]])
        checker = _governed_novelty_checker(governed_embedding=embedding)

        # Stub the scoped retrieval so the governed path completes without
        # requiring a real ChromaDB/SQL backend.
        fake_outcome = MagicMock(name="retrieval_outcome")
        fake_outcome.results = []
        fake_outcome.retrieval_event_id = 42

        with patch(
            "backend.pipeline.provenance_gate.select_run_execution_mode",
            return_value="governed",
        ), patch(
            "backend.pipeline.provenance_gate.load_run_provenance_contract",
            return_value=MagicMock(name="contract"),
        ), patch(
            "backend.pipeline.scoped_vector_service.query_vectors",
            new=AsyncMock(return_value=fake_outcome),
        ):
            profile, directives = asyncio.run(
                checker.check_novelty(
                    sample_ideas[0],
                    run_id=1,
                    db_engine=MagicMock(name="db_engine"),
                )
            )

        # The fix's central assertion: the embedding dependency was actually
        # used. Pre-B0 this line raised AttributeError before any embed call.
        assert embedding.call_count == 1

        # Sanity: governed retrieval completed and returned structured output
        assert profile is not None
        assert directives is not None

    def test_zero_vector_embedding_returns_empty_governed_result(self, sample_ideas):
        """When the embedding dependency returns an empty list, the governed
        path returns an empty result — NOT a legacy fallback."""
        embedding = _FakeGovernedEmbedding(vectors=[])
        checker = _governed_novelty_checker(governed_embedding=embedding)

        with patch(
            "backend.pipeline.provenance_gate.select_run_execution_mode",
            return_value="governed",
        ), patch(
            "backend.pipeline.provenance_gate.load_run_provenance_contract",
            return_value=MagicMock(name="contract"),
        ), patch(
            "backend.pipeline.scoped_vector_service.query_vectors",
            new=AsyncMock(return_value=MagicMock(results=[], retrieval_event_id=None)),
        ) as mock_query:
            profile, directives = asyncio.run(
                checker.check_novelty(
                    sample_ideas[0],
                    run_id=1,
                    db_engine=MagicMock(name="db_engine"),
                )
            )

        # Empty embedding list short-circuits before query_vectors, so the
        # governed scoped service is NOT invoked.
        mock_query.assert_not_called()
        assert embedding.call_count == 1
        assert profile is not None
