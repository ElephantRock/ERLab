"""Tests for WP-6 Knowledge Graph write path: papers, gaps, ideas."""

import asyncio
import sys
import tempfile
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

# Stub out chromadb
_chromadb = ModuleType("chromadb")
_chromadb.PersistentClient = MagicMock
_chromadb.HttpClient = MagicMock
sys.modules.setdefault("chromadb", _chromadb)

from backend.pipeline.knowledge.entities import EntityType
from backend.pipeline.knowledge.graph import KnowledgeGraph


def _make_paper(paper_id="p1", title="Test Paper on NLP", abstract="Abstract text"):
    paper = MagicMock()
    paper.id = paper_id
    paper.title = title
    paper.abstract = abstract
    paper.source = "semantic_scholar"
    paper.year = 2024
    paper.citation_count = 10
    return paper


class MockStore:
    async def add_papers(self, papers, chunks):
        return sum(len(c) for c in chunks)


class MockBM25:
    def add_documents(self, ids, texts, metas):
        pass


class MockEmbedding:
    pass


class TestIngestionStageWritesToKG:
    def test_papers_written_to_kg(self):
        with tempfile.TemporaryDirectory() as tmp:
            kg = KnowledgeGraph(persist_path=f"{tmp}/kg.json")
            from backend.pipeline.stages import IngestionStage

            stage = IngestionStage(MockStore(), MockBM25(), MockEmbedding(), kg=kg)

            # Build minimal context
            papers = [_make_paper("p1", "Paper One"), _make_paper("p2", "Paper Two")]
            ctx = MagicMock()
            ctx.all_papers = papers

            asyncio.run(stage.execute(ctx))

            paper_entities = [
                e for e in kg._entities.values()
                if e.entity_type == EntityType.PAPER
            ]
            assert len(paper_entities) == 2
            assert any("Paper One" in e.name for e in paper_entities)

    def test_kg_none_graceful(self):
        from backend.pipeline.stages import IngestionStage

        stage = IngestionStage(MockStore(), MockBM25(), MockEmbedding(), kg=None)
        ctx = MagicMock()
        ctx.all_papers = [_make_paper()]

        # Should not raise
        result = asyncio.run(stage.execute(ctx))
        assert result is True


class TestGapAnalysisStageWritesToKG:
    def test_gaps_written_to_kg(self):
        with tempfile.TemporaryDirectory() as tmp:
            kg = KnowledgeGraph(persist_path=f"{tmp}/kg.json")
            from backend.pipeline.stages import GapAnalysisStage

            gap = MagicMock()
            gap.title = "Evaluation metrics gap in LLM"
            gap.description = "No standardized evaluation"
            gap.confidence = 0.8
            gap.gap_type = "methodology"
            gap.potential_impact = "high"

            analyzer = MagicMock()
            analyzer.analyze = AsyncMock(return_value=([gap], MagicMock()))

            hooks = MagicMock()
            hooks.dispatch_sync_safe = AsyncMock()

            stage = GapAnalysisStage(
                gap_analyzer=analyzer,
                goal_manager=None,
                hooks=hooks,
                memory=None,
                kg=kg,
            )

            ctx = MagicMock()
            ctx.domain = "AI/NLP"
            ctx.all_papers = []
            ctx.max_gaps = 5

            asyncio.run(stage.execute(ctx))

            gap_entities = [
                e for e in kg._entities.values()
                if e.entity_type == EntityType.CONCEPT and "gap" in e.id
            ]
            assert len(gap_entities) == 1
            assert "Evaluation" in gap_entities[0].name


class TestIdeaGenerationStageWritesToKG:
    def test_ideas_and_relationships_written_to_kg(self):
        with tempfile.TemporaryDirectory() as tmp:
            kg = KnowledgeGraph(persist_path=f"{tmp}/kg.json")
            from backend.pipeline.generation.models import ResearchIdea

            # Pre-seed a gap entity
            from backend.pipeline.knowledge.entities import KnowledgeEntity
            from backend.pipeline.knowledge.truth import TruthValue
            from backend.pipeline.stages import IdeaGenerationStage

            gap_entity = KnowledgeEntity(
                id="gap:Test Gap About NLP",
                entity_type=EntityType.CONCEPT,
                name="Test Gap About NLP",
                truth=TruthValue.initial(),
            )
            kg.add_entity(gap_entity)

            idea = ResearchIdea(
                title="Novel Evaluation Method",
                problem_statement="Test",
                proposed_method="Test method",
                expected_contributions="Test",
                novelty_rationale="Test",
                evaluation_approach="Test",
                score=0.85,
                source_gap_ids=["Test Gap About NLP"],
            )

            agent = MagicMock()
            agent.run = AsyncMock(return_value=[idea])
            agent.last_critique_history = {}
            agent.last_refinement_history = {}

            hooks = MagicMock()
            hooks.dispatch_sync_safe = AsyncMock()

            stage = IdeaGenerationStage(
                agent=agent,
                hooks=hooks,
                kg=kg,
            )

            ctx = MagicMock()
            ctx.rounds = 1
            ctx.ideas_per = 1
            ctx.result = MagicMock()
            ctx.result.gaps = []
            ctx.all_papers = []

            asyncio.run(stage._execute_sequential(ctx))

            # Check idea entity
            idea_entities = [
                e for e in kg._entities.values()
                if e.entity_type == EntityType.CONCEPT and "idea" in e.id
            ]
            assert len(idea_entities) == 1

            # Check PROPOSES_METHOD relationship
            props_method_rels = [
                r for r in kg._relationships
                if r.relation_type.value == "proposes_method"
            ]
            assert len(props_method_rels) == 1


class TestKGSaveCalled:
    def test_kg_save_called_after_ingestion(self):
        with tempfile.TemporaryDirectory() as tmp:
            kg = KnowledgeGraph(persist_path=f"{tmp}/kg.json")
            from backend.pipeline.stages import IngestionStage

            stage = IngestionStage(MockStore(), MockBM25(), MockEmbedding(), kg=kg)

            ctx = MagicMock()
            ctx.all_papers = [_make_paper()]

            # Track save calls
            save_count = 0
            original_save = kg.save
            def counting_save():
                nonlocal save_count
                save_count += 1
                original_save()
            kg.save = counting_save

            asyncio.run(stage.execute(ctx))
            assert save_count == 1
