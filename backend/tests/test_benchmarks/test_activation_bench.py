"""Activation pipeline performance benchmarks."""

import pytest

from backend.pipeline.knowledge.activation import (
    ActivationContext,
    ActivationPipeline,
    BaseLevelDecay,
    ContextSpreading,
    StochasticNoise,
)
from backend.pipeline.knowledge.truth import TruthValue

pytestmark = pytest.mark.slow


class TestActivationBenchmark:
    def test_pipeline_compute(self, benchmark, benchmark_pipeline):
        ctx = ActivationContext(
            entity_id="e1",
            current_truth=TruthValue(frequency=0.8, confidence=0.7),
            time_since_last_access=10.0,
            neighbor_activations={"n1": 0.4, "n2": 0.3},
        )
        benchmark(benchmark_pipeline.compute, ctx)

    def test_pipeline_chain_scaling(self, benchmark):
        pipeline = ActivationPipeline(
            [
                BaseLevelDecay(0.5),
                ContextSpreading(0.1),
                StochasticNoise(0.02),
                BaseLevelDecay(0.3),
                ContextSpreading(0.05),
            ]
        )
        ctx = ActivationContext(
            entity_id="e1",
            current_truth=TruthValue(frequency=0.8, confidence=0.7),
            time_since_last_access=5.0,
            neighbor_activations={"n1": 0.5, "n2": 0.4, "n3": 0.3},
        )
        benchmark(pipeline.compute, ctx)
