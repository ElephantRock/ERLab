"""Fixtures for pipeline smoke tests."""

import sys
from unittest.mock import MagicMock

import pytest

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.pipeline.feasibility.feasibility_scorer import FeasibilityReport
from backend.pipeline.generation.models import Critique
from backend.pipeline.literature.models import Author, Paper
from backend.pipeline.novelty.novelty_checker import NoveltyReport
from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal
from backend.providers.base import LLMProvider


class SchemaAwareFakeProvider(LLMProvider):
    """Fake LLM that generates conformant output by inspecting JSON schema."""

    def __init__(self):
        self._call_log: list[dict] = []

    def _generate_from_schema(self, schema: dict) -> dict:
        result = {}
        props = schema.get("properties", {})
        for key, prop_schema in props.items():
            prop_type = prop_schema.get("type")
            if prop_type == "string":
                result[key] = self._fake_string(key)
            elif prop_type == "number":
                result[key] = 0.7
            elif prop_type == "array":
                items_schema = prop_schema.get("items", {})
                if items_schema.get("type") == "object":
                    result[key] = [self._generate_from_schema(items_schema)]
                elif items_schema.get("type") == "string":
                    result[key] = [f"{key}_item"]
                elif items_schema.get("type") == "integer":
                    result[key] = [0]
                else:
                    result[key] = []
            elif prop_type == "object":
                result[key] = self._generate_from_schema(prop_schema)
        return result

    @staticmethod
    def _fake_string(key: str) -> str:
        templates = {
            "title": "Novel approach to research methodology",
            "description": "This research addresses gaps in current methodology",
            "problem_statement": "Current approaches lack scalability and robustness",
            "proposed_method": (
                "We propose a hybrid retrieval-generation framework that combines dense passage "
                "retrieval with autoregressive generation for improved factual grounding. The "
                "method uses a two-stage pipeline: first retrieving relevant passages from a "
                "curated knowledge base using learned dense embeddings, then conditioning "
                "generation on the retrieved context through novel cross-attention fusion layers "
                "that dynamically weight passage relevance during decoding. We formally define "
                "the retrieval probability as P(d|q) and the generation probability as P(y|d,q) "
                "where q is the query, d is the retrieved document, and y is the output sequence. "
                "The fusion layer computes attention scores between decoder hidden states and "
                "retrieved passage representations to select the most relevant context tokens."
            ),
            "expected_contributions": "Improved performance on standard benchmarks",
            "novelty_rationale": "Combines techniques not previously explored together",
            "evaluation_approach": "Evaluate on standard benchmarks with ablation studies",
            "reasoning": "Based on analysis of existing literature",
            "overall_assessment": "Strong potential for impact",
            "abstract": (
                "This paper proposes a novel approach combining multiple techniques for "
                "natural language processing tasks. Our method integrates retrieval-augmented "
                "generation with multi-head attention mechanisms to improve factual accuracy "
                "and reduce hallucination rates across diverse domains. We evaluate on standard "
                "benchmarks including SQuAD, Natural Questions, and TriviaQA, showing "
                "significant improvements over existing baselines in both accuracy and efficiency. "
                "The proposed framework represents a meaningful advance in grounded generation."
            ),
            "introduction": (
                "Recent advances in natural language processing have opened new possibilities "
                "for automated research and knowledge-intensive applications across many domains. "
                "However, existing approaches struggle with factual consistency, domain adaptation, "
                "and computational efficiency at scale. These limitations hinder real-world "
                "deployment of language models in critical settings such as healthcare, legal "
                "analysis, and scientific discovery. In this work, we propose a novel framework "
                "that addresses these limitations through a combination of retrieval mechanisms "
                "and structured generation strategies. Our approach achieves state-of-the-art "
                "results on multiple benchmarks while maintaining interpretability and efficiency. "
                "The remainder of this paper is organized as follows: Section 2 reviews related "
                "work, Section 3 describes our method, Section 4 presents experiments, and "
                "Section 5 concludes with future directions."
            ),
            "related_work": (
                "Prior work has explored similar directions in retrieval-augmented generation "
                "and multi-task learning. Lewis et al. introduced RAG for knowledge-intensive "
                "NLP tasks, while subsequent work extended this to multi-domain settings. Our "
                "approach differs by incorporating structured attention over retrieved passages."
            ),
            "evaluation_plan": "Comprehensive evaluation on standard benchmarks with ablation studies",
            "timeline": "12 months",
            "novelty_arguments": "The approach is novel in its combination of techniques",
            "closest_match_title": "Similar prior work",
            "estimated_timeline": "6-12 months",
        }
        for pattern, text in templates.items():
            if pattern in key:
                return text
        return f"Generated {key}"

    async def structured_output(self, messages, schema, temperature=0.3) -> dict:
        self._call_log.append({"method": "structured_output", "schema": schema})
        return self._generate_from_schema(schema)

    async def complete(self, messages, temperature=0.7, max_tokens=4096) -> str:
        return "Test response"

    async def complete_stream(self, messages, temperature=0.7, max_tokens=4096):
        yield "Test"

    async def embed(self, texts) -> list[list[float]]:
        return [[0.1] * 10 for _ in texts]

    @property
    def provider_name(self) -> str:
        return "schema_aware_fake"

    @property
    def default_model(self) -> str:
        return "fake-model"


class FakeVectorStore:
    """Minimal VectorStore mock for smoke testing novelty checks."""

    async def query(self, query_text, n_results=10, filter_metadata=None):
        return []

    async def query_by_embedding(self, embedding, n_results=10):
        return []


class FakeVectorStoreWithResults(FakeVectorStore):
    """FakeVectorStore returning non-empty results for novelty tests."""

    async def query(self, query_text, n_results=10, filter_metadata=None):
        return [
            {
                "id": "p1",
                "text": "Similar paper abstract about NLP methods",
                "metadata": {"paper_title": "Similar Paper"},
                "distance": 0.3,
            },
            {
                "id": "p2",
                "text": "Another abstract about transformer models",
                "metadata": {"paper_title": "Another Paper"},
                "distance": 0.5,
            },
        ]


@pytest.fixture
def sample_proposal():
    return ResearchProposal(
        title="Novel approach to research methodology",
        abstract="This paper proposes a novel approach combining multiple techniques",
        introduction="Recent advances have opened new possibilities",
        related_work="Prior work has explored similar directions",
        proposed_method="We propose a hybrid retrieval-generation framework",
        expected_contributions="Improved performance on standard benchmarks",
        evaluation_plan="Comprehensive evaluation on standard benchmarks",
        timeline="12 months",
        references=["Smith et al. 2024. Prior Work. ACL."],
    )


@pytest.fixture
def sample_novelty_report():
    return NoveltyReport(
        overall_score=0.75,
        method_novelty=0.8,
        problem_novelty=0.7,
        domain_transfer=0.5,
        combination_novelty=0.8,
        novelty_arguments="The approach is novel in its combination of techniques",
        closest_matches=[{"title": "Similar Paper", "distance": 0.3}],
    )


@pytest.fixture
def sample_feasibility_report():
    return FeasibilityReport(
        overall_score=7.5,
        data_availability=8.0,
        computational_requirements=7.0,
        methodological_complexity=6.0,
        evaluation_plan=8.0,
        novelty_grounding=7.0,
        impact_potential=8.0,
        reasoning="Strong feasibility with available datasets",
        estimated_timeline="6-12 months",
        key_risks=["Data quality", "Compute costs"],
    )


@pytest.fixture
def sample_critiques():
    return [
        Critique(
            idea_title="Idea A",
            strengths=["Novel approach"],
            weaknesses=["Lacks evaluation detail"],
            suggestions=["Add ablation study"],
        ),
        Critique(
            idea_title="Idea B",
            weaknesses=["Incremental novelty"],
            suggestions=["Explore new domain"],
        ),
    ]


@pytest.fixture
def fake_store_with_results():
    return FakeVectorStoreWithResults()


@pytest.fixture
def many_papers():
    """10+ papers with distinct content for clustering tests."""
    return [
        Paper(
            id=f"p{i}",
            source="test",
            title=f"Research Paper {i}: Advances in NLP Method {i}",
            abstract=(
                f"Abstract for paper {i}. This paper investigates novel approaches to "
                "natural language processing. We propose a method that combines transformer "
                "attention with retrieval augmented generation for improved performance."
            ),
            authors=[Author(name=f"Author {i}")],
            year=2024,
        )
        for i in range(10)
    ]
