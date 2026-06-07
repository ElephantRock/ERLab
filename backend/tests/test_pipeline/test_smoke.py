"""End-to-end pipeline smoke test using SchemaAwareFakeProvider.

Exercises pipeline stages that don't require chromadb (stages 3-4).
Stages 5-7 (novelty, feasibility, synthesis) import chromadb transitively
and are tested in CI where all dependencies are installed.
"""

import asyncio

import pytest

from backend.pipeline.gap_analysis.gap_analyzer import GapAnalyzer
from backend.pipeline.gap_analysis.models import ResearchGap
from backend.pipeline.generation.agent_orchestrator import AgentOrchestrator
from backend.pipeline.literature.models import Paper
from backend.tests.test_pipeline.conftest import SchemaAwareFakeProvider


@pytest.fixture
def provider():
    return SchemaAwareFakeProvider()


@pytest.fixture
def sample_papers():
    return [
        Paper(
            id=f"p{i}",
            source="test",
            title=f"Research Paper {i}: Advances in NLP Method {i}",
            abstract=(
                f"Abstract for paper {i}. This paper investigates novel approaches "
                f"to natural language processing. We propose a method that combines "
                f"transformer attention with retrieval augmented generation."
            ),
            year=2024,
        )
        for i in range(10)
    ]


class TestPipelineSmoke:
    def test_stage4_idea_generation(self, provider, sample_papers):
        gaps = [
            ResearchGap(
                title="Test Gap", description="desc", gap_type="methodological", confidence=0.8
            )
        ]
        orchestrator = AgentOrchestrator(provider)
        ideas = asyncio.run(
            orchestrator.run(gaps=gaps, context_papers=sample_papers, rounds=1, ideas_per_round=2)
        )
        assert len(ideas) >= 1
        assert all(idea.title for idea in ideas)

    def test_provider_generates_conformant_schemas(self, provider):
        """Verify SchemaAwareFakeProvider returns valid schemas for all stage types."""
        gap_schema = {
            "type": "object",
            "properties": {
                "gaps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "gap_type": {"type": "string"},
                            "confidence": {"type": "number"},
                        },
                        "required": ["title", "description", "gap_type", "confidence"],
                    },
                }
            },
            "required": ["gaps"],
        }
        result = asyncio.run(provider.structured_output([], gap_schema))
        assert "gaps" in result
        assert len(result["gaps"]) >= 1
        assert result["gaps"][0]["title"]
