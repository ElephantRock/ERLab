"""Tests for epistemic truth maintenance."""

from backend.pipeline.knowledge.truth import TruthValue


class TestTruthValue:
    def test_initial(self):
        tv = TruthValue.initial()
        assert tv.frequency == 0.5
        assert tv.confidence == 0.5
        assert tv.evidence_count == 0

    def test_from_observation(self):
        tv = TruthValue.from_observation(frequency=0.9)
        assert tv.frequency == 0.9
        assert tv.confidence == 0.5
        assert tv.evidence_count == 1

    def test_expectation(self):
        tv = TruthValue(frequency=0.8, confidence=0.6)
        assert abs(tv.expectation - 0.48) < 1e-10

    def test_revise_same_evidence(self):
        tv1 = TruthValue(frequency=1.0, confidence=0.5, evidence_count=1)
        tv2 = TruthValue(frequency=1.0, confidence=0.5, evidence_count=1)
        revised = tv1.revise(tv2)
        # Two agreeing observations should increase confidence
        assert revised.confidence > tv1.confidence
        assert revised.frequency > 0.9  # Should stay near 1.0
        assert revised.evidence_count == 3  # 1 + 1 + 1

    def test_revise_contradictory_evidence(self):
        tv1 = TruthValue(frequency=1.0, confidence=0.5, evidence_count=1)
        tv2 = TruthValue(frequency=0.0, confidence=0.5, evidence_count=1)
        revised = tv1.revise(tv2)
        # Contradictory evidence should pull frequency toward 0.5
        assert abs(revised.frequency - 0.5) < 0.01
        assert revised.confidence > tv1.confidence

    def test_revise_increases_confidence(self):
        tv = TruthValue(frequency=0.8, confidence=0.5, evidence_count=0)
        for _ in range(5):
            tv = tv.revise(TruthValue.from_observation(0.8))
        assert tv.confidence > 0.8
        assert abs(tv.frequency - 0.8) < 0.05

    def test_decay_reduces_confidence(self):
        tv = TruthValue(frequency=0.8, confidence=0.9, evidence_count=5)
        decayed = tv.decay(rate=0.99)
        assert abs(decayed.confidence - 0.891) < 1e-10
        assert decayed.frequency == tv.frequency  # Frequency unchanged
        assert decayed.evidence_count == tv.evidence_count

    def test_decay_multiple_steps(self):
        tv = TruthValue(frequency=0.8, confidence=0.9, evidence_count=5)
        for _ in range(100):
            tv = tv.decay(rate=0.99)
        assert tv.confidence < 0.4

    def test_revise_clamps_frequency(self):
        tv1 = TruthValue(frequency=1.0, confidence=0.99, evidence_count=100)
        tv2 = TruthValue(frequency=1.0, confidence=0.99, evidence_count=100)
        revised = tv1.revise(tv2)
        assert revised.frequency <= 1.0
        assert revised.frequency >= 0.0

    def test_revise_zero_confidence(self):
        tv1 = TruthValue(frequency=0.8, confidence=0.0, evidence_count=0)
        tv2 = TruthValue(frequency=0.6, confidence=0.0, evidence_count=0)
        revised = tv1.revise(tv2)
        # Should not crash, should produce reasonable defaults
        assert 0.0 <= revised.frequency <= 1.0
        assert 0.0 <= revised.confidence <= 1.0
