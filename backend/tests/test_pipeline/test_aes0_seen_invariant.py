"""AES-0: Regression for the latent `seen` NameError in LiteratureSearchStage.

The knowledge-library, local-upload, and citation-tree enrichment branches
in `LiteratureSearchStage.execute()` reference a `seen` set that was never
initialized. This file exercises each branch against a duplicate of an
initial governed candidate and verifies:

  - no NameError is raised;
  - the duplicate does not appear twice in the final corpus.

The local-upload fixture deliberately uses ``doi=None`` because the
local-upload branch computes a title-only key, while the ``seen``
initialization uses DOI-first identity. An initial paper with a DOI
would expose the separate pre-existing key inconsistency rather than
the ``seen`` invariant under test.
"""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Stub heavy imports before anything else.
sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.pipeline.literature.citation_explorer import (
    CitationExplorer,
    TreeExplorationResult,
    TreeNode,
)
from backend.pipeline.literature.contracts import SearchBatchOutcome
from backend.pipeline.literature.models import Author, Paper
from backend.pipeline.persistence import CandidateWithDiscoveries
from backend.pipeline.result import PipelineResult
from backend.pipeline.stages import LiteratureSearchStage, StageContext
from backend.pipeline.strategies.models import StageConfig, StrategyConfig


# ── Helpers ──────────────────────────────────────────────────────────────────


def _ctx(**overrides) -> StageContext:
    defaults = dict(result=PipelineResult(), all_papers=[], domain="AI/NLP")
    defaults.update(overrides)
    return StageContext(**defaults)


def _stage_with_mock_search(papers: list[Paper]) -> tuple[
    LiteratureSearchStage, StageContext
]:
    """Build a stage whose search returns the given papers."""
    search = AsyncMock()
    search.search_all_with_provenance = AsyncMock(
        return_value=SearchBatchOutcome(
            candidates=[CandidateWithDiscoveries(paper=p) for p in papers],
            executions=[],
        )
    )
    hooks = MagicMock()
    hooks.dispatch_sync_safe = AsyncMock()
    stage = LiteratureSearchStage(search=search, hooks=hooks)
    ctx = _ctx(search_queries=["test query"])
    return stage, ctx


def _assert_single_match(ctx: StageContext, title: str) -> None:
    """Assert exactly one paper in ctx.all_papers matches the given title."""
    matches = [
        p for p in ctx.all_papers
        if p.title.lower().strip() == title.lower().strip()
    ]
    assert len(matches) == 1, (
        f"Expected exactly 1 paper matching '{title}', "
        f"found {len(matches)} in {len(ctx.all_papers)} total papers"
    )


# ── 1. Knowledge-library duplicate ──────────────────────────────────────────


def test_knowledge_library_duplicate_does_not_double():
    """Initial Paper A with a DOI; knowledge library returns a duplicate.

    The `seen` set must contain Paper A's DOI so the library branch
    rejects the duplicate without a NameError.
    """
    paper_a = Paper(
        id="p1",
        source="semantic_scholar",
        title="Transformer Attention Mechanisms for NLU",
        abstract="Abstract on attention.",
        authors=[Author(name="A")],
        year=2024,
        doi="10.1234/transformer-attn",
    )
    stage, ctx = _stage_with_mock_search([paper_a])

    with patch(
        "backend.pipeline.knowledge.integration.KnowledgeIntegrationService"
    ) as mock_ki:
        mock_instance = MagicMock()
        mock_instance.query_existing_knowledge.return_value = {
            "has_knowledge": True
        }
        # Return a duplicate entry with the same DOI.
        mock_instance._indexer.get_existing_papers.return_value = [
            {
                "id": "lib:dup1",
                "title": paper_a.title,
                "content": '{"abstract": "dup", "doi": "'
                + paper_a.doi
                + '", "year": 2024}',
            }
        ]
        mock_ki.return_value = mock_instance

        with patch("backend.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(embedding_base_url=None)
            asyncio.run(stage.execute(ctx))

    _assert_single_match(ctx, paper_a.title)


# ── 2. Local-upload duplicate ───────────────────────────────────────────────


def test_local_upload_duplicate_does_not_double():
    """Initial Paper B with doi=None; local upload returns a duplicate.

    The local-upload branch uses a title-only key. The initial paper
    has doi=None so the `seen` initialization also keys by title,
    making the dedup test precise for this branch.
    """
    paper_b = Paper(
        id="p2",
        source="semantic_scholar",
        title="Reinforcement Learning for Robotic Manipulation",
        abstract="Abstract on RL robotics.",
        authors=[Author(name="B")],
        year=2024,
        doi=None,
    )
    stage, ctx = _stage_with_mock_search([paper_b])

    mock_store = MagicMock()
    mock_store.query = AsyncMock(
        return_value=[
            {
                "content": "Local duplicate abstract.",
                "metadata": {
                    "source": "local_upload",
                    "paper_id": "upload_dup",
                    "title": paper_b.title,
                },
            }
        ]
    )

    with patch(
        "backend.pipeline.knowledge.integration.KnowledgeIntegrationService"
    ) as mock_ki:
        mock_instance = MagicMock()
        mock_instance.query_existing_knowledge.return_value = {
            "has_knowledge": False
        }
        mock_ki.return_value = mock_instance

        with patch(
            "backend.pipeline.knowledge.embedding_providers"
            ".create_embedding_provider"
        ), patch(
            "backend.pipeline.knowledge.embedding_service.EmbeddingService"
        ), patch(
            "backend.pipeline.knowledge.vector_store.VectorStore",
            return_value=mock_store,
        ), patch(
            "backend.config.get_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(
                embedding_base_url="http://localhost:1234/v1",
                embedding_provider="lmstudio",
                embedding_model="test-embed",
                openai_api_key="test",
                embedding_dimension=384,
                embedding_batch_size=10,
                chroma_persist_dir="/tmp/chroma",
                lmstudio_base_url="http://localhost:1234",
            )
            asyncio.run(stage.execute(ctx))

    _assert_single_match(ctx, paper_b.title)


# ── 3. Citation-tree duplicate ──────────────────────────────────────────────


def test_citation_tree_duplicate_does_not_double():
    """Initial Paper A; citation explorer returns a duplicate of A.

    The citation-explore branch must see Paper A's identity in the
    `seen` set and reject the duplicate. The test exercises the real
    ``TreeExplorationResult → extract_papers()`` path.
    """
    paper_a = Paper(
        id="p1",
        source="semantic_scholar",
        title="Graph Neural Networks for Molecular Property Prediction",
        abstract="Abstract on GNNs.",
        authors=[Author(name="C")],
        year=2024,
        doi="10.5678/gnn-molecular",
    )
    stage, ctx = _stage_with_mock_search([paper_a])

    # Strategy config with citation_explore enabled.
    strategy_config = StrategyConfig(
        name="deep_research",
        stages={
            "literature_search": StageConfig(
                enabled=True, params={"citation_explore": True}
            )
        },
    )
    ctx.params["strategy_config"] = strategy_config

    # Build a real TreeExplorationResult with a duplicate paper.
    dup_paper = Paper(
        id="cite_dup",
        source="citation_tree",
        title=paper_a.title,
        abstract="Cited by seed paper.",
        authors=[],
        year=2023,
        doi=paper_a.doi,
    )
    tree_result = TreeExplorationResult(
        seed_papers=1,
        total_discovered=1,
        backward_papers=1,
        tree=[
            TreeNode(
                paper=dup_paper,
                depth=1,
                direction="backward",
                parent_title=paper_a.title,
            )
        ],
    )

    mock_explorer = MagicMock(spec=CitationExplorer)
    mock_explorer.explore = AsyncMock(return_value=tree_result)
    # Leave extract_papers as the real method (spec=CitationExplorer
    # copies the class interface, so extract_papers is unbound —
    # bind it to the mock so it calls through to the real method).
    mock_explorer.extract_papers = CitationExplorer.extract_papers.__get__(
        mock_explorer
    )

    with patch(
        "backend.pipeline.knowledge.integration.KnowledgeIntegrationService"
    ) as mock_ki:
        mock_instance = MagicMock()
        mock_instance.query_existing_knowledge.return_value = {
            "has_knowledge": False
        }
        mock_ki.return_value = mock_instance

        with patch("backend.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(embedding_base_url=None)

            with patch(
                "backend.pipeline.literature.citation_explorer"
                ".CitationExplorer",
                return_value=mock_explorer,
            ):
                asyncio.run(stage.execute(ctx))

    _assert_single_match(ctx, paper_a.title)
