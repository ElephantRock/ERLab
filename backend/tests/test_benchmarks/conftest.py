"""Shared fixtures for performance benchmarks."""

import random
import tempfile

import pytest

from backend.pipeline.knowledge.activation import (
    ActivationPipeline,
    BaseLevelDecay,
    ContextSpreading,
)
from backend.pipeline.knowledge.bm25_index import BM25Index
from backend.pipeline.knowledge.entities import EntityType, KnowledgeEntity
from backend.pipeline.knowledge.graph import KnowledgeGraph
from backend.pipeline.knowledge.relationships import KnowledgeRelationship, RelationType
from backend.pipeline.knowledge.truth import TruthValue
from backend.pipeline.memory.models import MemoryEntry, MemoryType
from backend.pipeline.memory.tiers import TieredMemoryService

TOPICS = [
    "transformer attention mechanisms",
    "retrieval augmented generation",
    "knowledge graph embedding",
    "contrastive learning representations",
    "multilingual language models",
    "few-shot in-context learning",
    "neural machine translation",
    "dialogue systems and conversational AI",
    "named entity recognition",
    "sentiment analysis and opinion mining",
    "text summarization techniques",
    "question answering systems",
    "relation extraction from text",
    "cross-lingual transfer learning",
    "pre-training strategies for language models",
    "prompt engineering and design",
    "instruction tuning methods",
    "reinforcement learning from human feedback",
    "chain-of-thought reasoning",
    "code generation and program synthesis",
]


def generate_corpus(n: int = 1000) -> tuple[list[str], list[str], list[dict]]:
    """Generate synthetic document corpus with topic keywords."""
    random.seed(42)
    ids, texts, metadatas = [], [], []
    for i in range(n):
        topic = TOPICS[i % len(TOPICS)]
        filler = (
            f"This paper investigates {topic} and proposes a novel approach "
            f"combining {random.choice(TOPICS)} with {random.choice(TOPICS)}. "
            f"Experimental results show significant improvements over baseline methods."
        )
        ids.append(f"doc_{i}")
        texts.append(filler)
        metadatas.append({"topic": topic, "index": i})
    return ids, texts, metadatas


@pytest.fixture(scope="session")
def synthetic_corpus():
    return generate_corpus(1000)


@pytest.fixture(scope="session")
def benchmark_bm25(synthetic_corpus):
    ids, texts, metadatas = synthetic_corpus
    with tempfile.TemporaryDirectory() as tmp:
        idx = BM25Index(f"{tmp}/bm25_bench")
        idx.add_documents(ids, texts, metadatas)
        yield idx


@pytest.fixture(scope="session")
def benchmark_kg():
    with tempfile.TemporaryDirectory() as tmp:
        kg = KnowledgeGraph(persist_path=f"{tmp}/kg_bench.json", versioning_enabled=True)
        for i in range(500):
            kg.add_entity(
                KnowledgeEntity(
                    id=f"entity_{i}",
                    entity_type=EntityType.CONCEPT,
                    name=f"Concept {i}",
                    truth=TruthValue(
                        frequency=0.5 + random.random() * 0.4,
                        confidence=0.4 + random.random() * 0.5,
                    ),
                )
            )
        for _ in range(1000):
            src = f"entity_{random.randint(0, 499)}"
            tgt = f"entity_{random.randint(0, 499)}"
            if src != tgt:
                kg.add_relationship(
                    KnowledgeRelationship(
                        source_id=src,
                        target_id=tgt,
                        relation_type=RelationType.BUILDS_ON,
                        truth=TruthValue.from_observation(),
                    )
                )
        yield kg


@pytest.fixture
def benchmark_memory():
    with tempfile.TemporaryDirectory() as tmp:
        mem = TieredMemoryService(working_capacity=100, archival_path=f"{tmp}/archival")
        for i in range(50):
            entry = MemoryEntry(
                id=f"mem_{i}",
                content=f"Observation about {TOPICS[i % len(TOPICS)]} with findings",
                memory_type=MemoryType.SEMANTIC,
                namespace="benchmark",
                truth=TruthValue(
                    frequency=0.5 + random.random() * 0.4, confidence=0.4 + random.random() * 0.5
                ),
            )
            mem._working[entry.id] = entry
        yield mem


@pytest.fixture(scope="session")
def benchmark_pipeline():
    return ActivationPipeline(
        [
            BaseLevelDecay(0.5),
            ContextSpreading(0.1),
        ]
    )
