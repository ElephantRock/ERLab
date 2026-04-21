"""Tests for composable activation adaptors."""

import statistics

from backend.pipeline.knowledge.activation import (
    ActivationContext,
    ActivationPipeline,
    BaseLevelDecay,
    ContextSpreading,
    StochasticNoise,
)
from backend.pipeline.knowledge.truth import TruthValue


class TestBaseLevelDecay:
    def test_zero_time_unchanged(self):
        decay = BaseLevelDecay(0.5)
        ctx = ActivationContext(
            entity_id="e1", current_truth=TruthValue(frequency=0.8, confidence=0.7)
        )
        result = decay.adjust(0.56, ctx)
        assert result == 0.56

    def test_reduces_activation(self):
        decay = BaseLevelDecay(0.5)
        ctx = ActivationContext(
            entity_id="e1",
            current_truth=TruthValue(frequency=0.8, confidence=0.7),
            time_since_last_access=10.0,
        )
        result = decay.adjust(0.56, ctx)
        assert result < 0.56

    def test_custom_rate(self):
        decay_low = BaseLevelDecay(0.1)
        decay_high = BaseLevelDecay(1.0)
        ctx = ActivationContext(
            entity_id="e1",
            current_truth=TruthValue(frequency=0.8, confidence=0.7),
            time_since_last_access=10.0,
        )
        assert decay_high.adjust(0.56, ctx) < decay_low.adjust(0.56, ctx)

    def test_name(self):
        assert "base_level_decay" in BaseLevelDecay(0.5).name


class TestContextSpreading:
    def test_no_neighbors_unchanged(self):
        spread = ContextSpreading(0.1)
        ctx = ActivationContext(
            entity_id="e1", current_truth=TruthValue(frequency=0.8, confidence=0.7)
        )
        result = spread.adjust(0.56, ctx)
        assert result == 0.56

    def test_with_neighbors_boosts(self):
        spread = ContextSpreading(0.1)
        ctx = ActivationContext(
            entity_id="e1",
            current_truth=TruthValue(frequency=0.8, confidence=0.7),
            neighbor_activations={"n1": 0.5, "n2": 0.3},
        )
        result = spread.adjust(0.56, ctx)
        assert result > 0.56

    def test_spreading_rate(self):
        low = ContextSpreading(0.05)
        high = ContextSpreading(0.2)
        ctx = ActivationContext(
            entity_id="e1",
            current_truth=TruthValue(frequency=0.8, confidence=0.7),
            neighbor_activations={"n1": 0.5},
        )
        assert high.adjust(0.56, ctx) > low.adjust(0.56, ctx)


class TestStochasticNoise:
    def test_small_perturbation(self):
        noise = StochasticNoise(0.02)
        ctx = ActivationContext(
            entity_id="e1", current_truth=TruthValue(frequency=0.8, confidence=0.7)
        )
        results = [noise.adjust(0.56, ctx) for _ in range(100)]
        mean_diff = abs(statistics.mean(results) - 0.56)
        assert mean_diff < 0.02

    def test_name(self):
        assert "stochastic_noise" in StochasticNoise(0.02).name


class TestActivationPipeline:
    def test_empty_chain_returns_expectation(self):
        pipeline = ActivationPipeline([])
        ctx = ActivationContext(
            entity_id="e1", current_truth=TruthValue(frequency=0.8, confidence=0.5)
        )
        assert pipeline.compute(ctx) == 0.4

    def test_chain_applies_adaptors(self):
        pipeline = ActivationPipeline(
            [
                BaseLevelDecay(0.5),
                ContextSpreading(0.1),
            ]
        )
        ctx = ActivationContext(
            entity_id="e1",
            current_truth=TruthValue(frequency=0.8, confidence=0.7),
            time_since_last_access=5.0,
            neighbor_activations={"n1": 0.4},
        )
        result = pipeline.compute(ctx)
        assert 0.0 < result < 1.0

    def test_deterministic_without_noise(self):
        pipeline = ActivationPipeline([BaseLevelDecay(0.5)])
        ctx = ActivationContext(
            entity_id="e1", current_truth=TruthValue(frequency=0.8, confidence=0.7)
        )
        r1 = pipeline.compute(ctx)
        r2 = pipeline.compute(ctx)
        assert r1 == r2

    def test_compute_clamps_to_zero(self):
        pipeline = ActivationPipeline([BaseLevelDecay(100)])
        ctx = ActivationContext(
            entity_id="e1",
            current_truth=TruthValue(frequency=0.01, confidence=0.01),
            time_since_last_access=10000.0,
        )
        assert pipeline.compute(ctx) >= 0.0

    def test_adaptor_count_and_names(self):
        pipeline = ActivationPipeline([BaseLevelDecay(0.5), StochasticNoise(0.01)])
        assert pipeline.adaptor_count == 2
        assert len(pipeline.adaptor_names) == 2
