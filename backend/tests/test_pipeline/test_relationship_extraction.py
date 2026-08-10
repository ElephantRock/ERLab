"""Tests for relationship extraction (BATCH-74/TASK-01)."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

from backend.pipeline.knowledge.relationship_extractor import (
    _parse_relation_response,
    extract_relationships,
)
from backend.pipeline.knowledge.relationships import RelationType


def _make_paper(paper_id: str, title: str, abstract: str = "Test abstract"):
    p = MagicMock()
    p.id = paper_id
    p.title = title
    p.abstract = abstract
    p.source = "test"
    p.year = 2024
    return p


def _make_provider(responses: list[str]):
    """Create a mock provider that returns the given responses in order."""
    provider = MagicMock()
    provider.complete = AsyncMock(side_effect=responses)
    return provider


class TestParseRelationResponse:
    def test_valid_json(self):
        result = _parse_relation_response(
            '{"relation_type": "cites", "confidence": 0.8, "evidence": "A cites B"}'
        )
        assert result is not None
        assert result["relation_type"] == "cites"
        assert result["confidence"] == 0.8

    def test_json_with_code_fence(self):
        result = _parse_relation_response(
            '```json\n{"relation_type": "extends", "confidence": 0.7, "evidence": "test"}\n```'
        )
        assert result is not None
        assert result["relation_type"] == "extends"

    def test_json_with_surrounding_text(self):
        result = _parse_relation_response(
            'Here is my analysis:\n{"relation_type": "uses_method", "confidence": 0.9, "evidence": "x"}\nDone.'
        )
        assert result is not None
        assert result["relation_type"] == "uses_method"

    def test_invalid_json_returns_none(self):
        result = _parse_relation_response("not json at all")
        assert result is None

    def test_missing_relation_type_returns_none(self):
        result = _parse_relation_response('{"confidence": 0.5}')
        assert result is None


class TestExtractRelationships:
    def test_returns_cites_relationship(self):
        """TEST-74-01-01: extract_relationships returns CITES relationship."""
        papers = [
            _make_paper("p1", "Transformer Networks", "We build on attention mechanisms..."),
            _make_paper("p2", "Attention Is All You Need", "We propose the attention mechanism..."),
        ]
        provider = _make_provider([
            json.dumps({"relation_type": "cites", "confidence": 0.9, "evidence": "p1 cites p2"}),
        ])
        rels = asyncio.run(extract_relationships(papers, provider))
        assert len(rels) == 1
        assert rels[0].relation_type == RelationType.CITES
        assert rels[0].source_id == "paper:p1"
        assert rels[0].target_id == "paper:p2"

    def test_returns_extends_relationship(self):
        """TEST-74-01-02: extract_relationships returns EXTENDS relationship."""
        papers = [
            _make_paper("p1", "BERT: Pre-training", "We extend the transformer..."),
            _make_paper("p2", "GPT: Generative Pre-training", "We propose generative pre-training..."),
        ]
        provider = _make_provider([
            json.dumps({"relation_type": "extends", "confidence": 0.8, "evidence": "p1 extends p2"}),
        ])
        rels = asyncio.run(extract_relationships(papers, provider))
        assert len(rels) == 1
        assert rels[0].relation_type == RelationType.EXTENDS

    def test_skips_fewer_than_2_papers(self):
        """TEST-74-01-03: extract_relationships skips when <2 papers."""
        papers = [_make_paper("p1", "Single Paper")]
        provider = _make_provider([])
        rels = asyncio.run(extract_relationships(papers, provider))
        assert len(rels) == 0
        provider.complete.assert_not_called()

    def test_respects_comparison_limit(self):
        """TEST-74-01-04: extract_relationships respects 3-comparison limit."""
        # 5 papers: p1→p2,p3,p4 (3) + p2→p3,p4,p5 (3) + p3→p4,p5 (2) + p4→p5 (1) = 9
        papers = [_make_paper(f"p{i}", f"Paper {i}") for i in range(1, 6)]
        provider = _make_provider([
            json.dumps({"relation_type": "cites", "confidence": 0.9, "evidence": "x"})
            for _ in range(10)
        ])
        rels = asyncio.run(extract_relationships(papers, provider, max_comparisons=3))
        assert provider.complete.call_count == 9

    def test_skips_low_confidence(self):
        """Relationships below MIN_CONFIDENCE are not returned."""
        papers = [
            _make_paper("p1", "Paper 1"),
            _make_paper("p2", "Paper 2"),
        ]
        provider = _make_provider([
            json.dumps({"relation_type": "cites", "confidence": 0.2, "evidence": "weak"}),
        ])
        rels = asyncio.run(extract_relationships(papers, provider))
        assert len(rels) == 0

    def test_skips_none_relation(self):
        """'none' relation type is not returned."""
        papers = [
            _make_paper("p1", "Paper 1"),
            _make_paper("p2", "Paper 2"),
        ]
        provider = _make_provider([
            json.dumps({"relation_type": "none", "confidence": 0.0, "evidence": ""}),
        ])
        rels = asyncio.run(extract_relationships(papers, provider))
        assert len(rels) == 0

    def test_llm_failure_doesnt_halt(self):
        """Individual LLM failures don't stop extraction."""
        papers = [
            _make_paper("p1", "Paper 1"),
            _make_paper("p2", "Paper 2"),
            _make_paper("p3", "Paper 3"),
        ]
        provider = _make_provider([
            Exception("LLM error"),  # p1→p2 fails
            json.dumps({"relation_type": "cites", "confidence": 0.8, "evidence": "ok"}),  # p1→p3
            json.dumps({"relation_type": "extends", "confidence": 0.7, "evidence": "ok"}),  # p2→p3
        ])
        rels = asyncio.run(extract_relationships(papers, provider))
        assert len(rels) == 2


class TestIngestionStageIntegration:
    def test_ingestion_calls_relationship_extraction(self):
        """TEST-74-01-05: IngestionStage calls relationship extraction."""
        from backend.pipeline.result import PipelineResult
        from backend.pipeline.stages import IngestionStage, StageContext

        store = MagicMock()
        store.add_papers = AsyncMock(return_value=3)
        bm25 = MagicMock()
        embedding = MagicMock()
        kg = MagicMock()
        kg.add_entity = MagicMock()
        kg.add_relationship = MagicMock()
        kg.save = MagicMock()

        provider = MagicMock()
        provider.complete = AsyncMock(return_value=json.dumps({
            "relation_type": "cites",
            "confidence": 0.8,
            "evidence": "test",
        }))

        stage = IngestionStage(store, bm25, embedding, kg=kg, provider=provider)

        papers = [_make_paper(f"p{i}", f"Paper {i}") for i in range(1, 4)]
        ctx = StageContext(
            result=PipelineResult(run_id="test"),
            all_papers=papers,
        )

        asyncio.run(stage.execute(ctx))
        # Verify add_relationship was called (relationship extraction ran)
        assert kg.add_relationship.called
