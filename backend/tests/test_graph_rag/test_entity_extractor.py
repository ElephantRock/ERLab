"""Tests for entity extraction."""

import pytest

from backend.pipeline.knowledge.entities import KnowledgeEntity, EntityType, TruthValue
from backend.pipeline.knowledge.entity_extractor import (
    EntityExtractor,
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from backend.tests.conftest import FakeLLMProvider


class TestExtractedEntity:
    def test_model_defaults(self):
        e = ExtractedEntity(name="BERT", entity_type="method")
        assert e.name == "BERT"
        assert e.description == ""
        assert e.properties == {}

    def test_model_with_all_fields(self):
        e = ExtractedEntity(
            name="GPT-4", entity_type="method", description="Large language model",
            properties={"year": 2023},
        )
        assert e.properties["year"] == 2023


class TestExtractedRelation:
    def test_model_defaults(self):
        r = ExtractedRelation(
            source_name="BERT", target_name="NLP", relation_type="applied_to",
        )
        assert r.evidence == ""


class TestExtractionResult:
    def test_empty_result(self):
        result = ExtractionResult()
        assert result.entities == []
        assert result.relationships == []

    def test_result_serialization(self):
        result = ExtractionResult(
            entities=[ExtractedEntity(name="BERT", entity_type="method")],
            relationships=[ExtractedRelation(
                source_name="BERT", target_name="NLP", relation_type="applied_to",
            )],
        )
        data = result.model_dump()
        restored = ExtractionResult(**data)
        assert len(restored.entities) == 1
        assert len(restored.relationships) == 1


class TestEntityExtractor:
    @pytest.fixture
    def provider(self):
        return FakeLLMProvider(responses={
            "structured_output": {
                "entities": [
                    {"name": "BERT", "entity_type": "method", "description": "Bidirectional encoder"},
                    {"name": "NLP", "entity_type": "concept"},
                ],
                "relationships": [
                    {"source_name": "BERT", "target_name": "NLP", "relation_type": "applied_to"},
                ],
            },
        })

    @pytest.mark.anyio
    async def test_extract_entities_from_text(self, provider):
        extractor = EntityExtractor(provider)
        result = await extractor.extract("BERT is a method for NLP tasks.")
        assert len(result.entities) == 2
        assert result.entities[0].name == "BERT"
        assert result.entities[0].entity_type == "method"

    @pytest.mark.anyio
    async def test_extract_relationships_linked(self, provider):
        extractor = EntityExtractor(provider)
        result = await extractor.extract("BERT is used in NLP.")
        assert len(result.relationships) == 1
        assert result.relationships[0].source_name == "BERT"

    @pytest.mark.anyio
    async def test_extract_deduplicates_entities(self):
        provider = FakeLLMProvider(responses={
            "structured_output": {
                "entities": [
                    {"name": "BERT", "entity_type": "method"},
                    {"name": "bert", "entity_type": "method"},
                ],
                "relationships": [],
            },
        })
        extractor = EntityExtractor(provider)
        result = await extractor.extract("text")
        assert len(result.entities) == 1

    @pytest.mark.anyio
    async def test_extract_empty_text(self):
        provider = FakeLLMProvider(responses={"structured_output": {"entities": []}})
        extractor = EntityExtractor(provider)
        result = await extractor.extract("")
        assert result.entities == []

    @pytest.mark.anyio
    async def test_extract_handles_malformed_response(self):
        provider = FakeLLMProvider(responses={"structured_output": {}})
        extractor = EntityExtractor(provider)
        result = await extractor.extract("Some text")
        assert result.entities == []

    @pytest.mark.anyio
    async def test_extract_with_entity_type_filter(self):
        provider = FakeLLMProvider(responses={
            "structured_output": {
                "entities": [{"name": "BERT", "entity_type": "method"}],
                "relationships": [],
            },
        })
        extractor = EntityExtractor(provider)
        result = await extractor.extract("text", entity_types=["method"])
        assert len(result.entities) == 1

    @pytest.mark.anyio
    async def test_extract_batch_processes_multiple(self, provider):
        extractor = EntityExtractor(provider)
        results = await extractor.extract_batch(["text1", "text2"])
        assert len(results) == 2
        assert provider._call_log[0]["method"] == "structured_output"

    @pytest.mark.anyio
    async def test_extracts_paper_author_method_dataset_concept(self):
        provider = FakeLLMProvider(responses={
            "structured_output": {
                "entities": [
                    {"name": "Paper1", "entity_type": "paper"},
                    {"name": "Author1", "entity_type": "author"},
                    {"name": "Method1", "entity_type": "method"},
                    {"name": "Dataset1", "entity_type": "dataset"},
                    {"name": "Concept1", "entity_type": "concept"},
                ],
                "relationships": [],
            },
        })
        extractor = EntityExtractor(provider)
        result = await extractor.extract("text")
        types = {e.entity_type for e in result.entities}
        assert types == {"paper", "author", "method", "dataset", "concept"}

    @pytest.mark.anyio
    async def test_provider_call_count_matches_batch_size(self, provider):
        extractor = EntityExtractor(provider)
        await extractor.extract_batch(["t1", "t2", "t3"])
        calls = [c for c in provider._call_log if c["method"] == "structured_output"]
        assert len(calls) == 3

    @pytest.mark.anyio
    async def test_extract_failure_returns_empty(self):
        provider = FakeLLMProvider()
        provider.structured_output = lambda **kw: (_ for _ in ()).throw(RuntimeError("fail"))
        extractor = EntityExtractor(provider)
        result = await extractor.extract("text")
        assert result.entities == []
