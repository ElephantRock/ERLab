"""End-to-end smoke test — runs the full 9-stage pipeline with a real LLM.

Exercises: literature search -> ingestion -> gap analysis -> idea generation ->
novelty checking -> feasibility scoring -> proposal synthesis -> export.

Uses the Anthropic-compatible z.ai endpoint configured in .env.
Embeddings use random vectors to avoid needing a separate OpenAI key.

Run with:  pytest -p no:asyncio backend/tests/test_pipeline/test_e2e_smoke.py -v -s
"""

import asyncio
import logging
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Mock google.generativeai only — chromadb must be real for e2e
sys.modules["google.generativeai"] = MagicMock()

from backend.config import Settings, get_settings
from backend.pipeline.orchestrator import PipelineOrchestrator

logger = logging.getLogger(__name__)


class RandomEmbeddingProvider:
    """Returns deterministic random vectors — no external API needed."""

    def __init__(self, dimension: int = 64):
        self._dim = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        rng = np.random.default_rng(42)
        return rng.standard_normal((len(texts), self._dim)).tolist()

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def provider_name(self) -> str:
        return "random-mock"


def _make_settings(tmp_dir: Path) -> Settings:
    base = get_settings()
    return Settings(
        default_provider=base.default_provider,
        anthropic_api_key=base.anthropic_api_key,
        anthropic_model=base.anthropic_model,
        anthropic_base_url=base.anthropic_base_url,
        openai_api_key=base.openai_api_key,
        embedding_provider=base.embedding_provider,
        embedding_model=base.embedding_model,
        chroma_persist_dir=str(tmp_dir / "chroma"),
        bm25_persist_dir=str(tmp_dir / "bm25"),
        embedding_dimension=64,
        database_url=f"sqlite:///{tmp_dir / 'test_e2e.db'}",
        memory_enabled=False,
        self_improve_enabled=False,
        governance_enabled=False,
        budget_enabled=False,
        autonomy_enabled=False,
        skills_enabled=False,
        multi_agent_enabled=False,
    )


@pytest.fixture(scope="module")
def test_env():
    """Create isolated test directories, cleaned up after module."""
    tmp = Path("./data/test_e2e")
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "chroma").mkdir(exist_ok=True)
    (tmp / "bm25").mkdir(exist_ok=True)
    (tmp / "exports").mkdir(exist_ok=True)
    settings = _make_settings(tmp)
    yield tmp, settings
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="module")
def orchestrator(test_env):
    """Build a PipelineOrchestrator with random embeddings."""
    tmp, settings = test_env
    random_emb = RandomEmbeddingProvider(64)

    # The conftest.py mocks chromadb for smoke tests, but this e2e test needs real ChromaDB.
    # Remove the mock and clear cached submodules so the real module loads fresh.
    _chromadb_keys = [k for k in sys.modules if k == "chromadb" or k.startswith("chromadb.")]
    for k in _chromadb_keys:
        del sys.modules[k]

    # Patch get_settings at all import sites and create_embedding_provider before construction
    with patch("backend.config.get_settings", return_value=settings), \
         patch("backend.pipeline.orchestrator.get_settings", return_value=settings), \
         patch("backend.providers.provider_factory.get_settings", return_value=settings), \
         patch(
        "backend.pipeline.knowledge.embedding_providers.create_embedding_provider",
        return_value=random_emb,
    ):
        orch = PipelineOrchestrator()

    orch._export._output_dir = str(tmp / "exports")
    yield orch


@pytest.mark.slow
@pytest.mark.integration
class TestEndToEndSmoke:
    def test_full_pipeline_9_stages(self, orchestrator, test_env):
        """Run all 9 stages and verify every stage produces output."""
        result = asyncio.run(
            orchestrator.run(
                domain="AI/NLP",
                search_queries=[
                    "natural language processing recent advances",
                    "NLP transformer models open problems",
                ],
                max_gaps=2,
                generation_rounds=1,
                ideas_per_round=1,
                export_format="markdown",
            )
        )

        # Stage 1: Literature search
        assert result.papers_found > 0, "No papers found — ArXiv search may be down"
        logger.info("Stage 1 (literature_search): %d papers", result.papers_found)

        # Stage 3: Gap analysis
        assert len(result.gaps) >= 1, "No research gaps identified"
        for gap in result.gaps:
            assert gap.title
        logger.info("Stage 3 (gap_analysis): %d gaps", len(result.gaps))

        # Stage 4: Idea generation
        assert len(result.ideas) >= 1, "No ideas generated"
        for idea in result.ideas:
            assert idea.title
            assert idea.proposed_method
        logger.info("Stage 4 (idea_generation): %d ideas", len(result.ideas))

        # Stage 5: Novelty checking
        assert len(result.novelty_reports) >= 1, "No novelty reports"
        for report in result.novelty_reports.values():
            assert report.overall_score is not None
            assert 0 <= report.overall_score <= 1
        logger.info("Stage 5 (novelty_checking): %d reports", len(result.novelty_reports))

        # Stage 6: Feasibility scoring
        assert len(result.feasibility_reports) >= 1, "No feasibility reports"
        for report in result.feasibility_reports.values():
            assert report.overall_score is not None
            assert 0 <= report.overall_score <= 10
        logger.info("Stage 6 (feasibility_scoring): %d reports", len(result.feasibility_reports))

        # Stage 7: Proposal synthesis
        assert len(result.proposals) >= 1, "No proposals generated"
        for proposal in result.proposals.values():
            md = proposal.to_markdown()
            assert md
            assert len(md) > 100
        logger.info("Stage 7 (proposal_synthesis): %d proposals", len(result.proposals))

        # Stage 8: Export
        assert len(result.export_paths) >= 1, "No files exported"
        for path in result.export_paths.values():
            assert Path(path).exists(), f"Export file missing: {path}"
            assert len(Path(path).read_text(encoding="utf-8")) > 50
        logger.info("Stage 8 (export): %d files", len(result.export_paths))

        logger.info(
            "=== E2E Complete: run=%s papers=%d gaps=%d ideas=%d proposals=%d ===",
            result.run_id,
            result.papers_found,
            len(result.gaps),
            len(result.ideas),
            len(result.proposals),
        )
