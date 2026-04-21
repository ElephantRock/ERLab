"""Knowledge graph performance benchmarks."""

import tempfile

import pytest

from backend.pipeline.knowledge.entities import EntityType, KnowledgeEntity
from backend.pipeline.knowledge.truth import TruthValue

pytestmark = pytest.mark.slow


class TestKGBenchmark:
    def test_entity_lookup(self, benchmark, benchmark_kg):
        entity_ids = list(benchmark_kg._entities.keys())
        target = entity_ids[len(entity_ids) // 2]
        benchmark(benchmark_kg.get_entity, target)

    def test_neighbor_traversal(self, benchmark, benchmark_kg):
        entity_ids = list(benchmark_kg._entities.keys())
        target = entity_ids[0]
        benchmark(benchmark_kg.get_neighbors, target)

    def test_add_entity(self, benchmark):
        counter = [0]

        def add():
            counter[0] += 1
            with tempfile.TemporaryDirectory() as tmp:
                from backend.pipeline.knowledge.graph import KnowledgeGraph

                kg = KnowledgeGraph(persist_path=f"{tmp}/kg.json", versioning_enabled=True)
                kg.add_entity(
                    KnowledgeEntity(
                        id=f"new_{counter[0]}",
                        entity_type=EntityType.CONCEPT,
                        name=f"New {counter[0]}",
                        truth=TruthValue.from_observation(),
                    )
                )

        benchmark(add)
