"""Tests for propagation debt tracking on TruthValue."""

from backend.pipeline.knowledge.truth import TruthValue


class TestPropagationDebt:
    def test_initial_debt_is_zero(self):
        tv = TruthValue.initial()
        assert tv.propagation_debt == 0.0

    def test_revise_accrues_debt(self):
        base = TruthValue(frequency=0.9, confidence=0.9, evidence_count=5)
        new = TruthValue(frequency=0.1, confidence=0.9, evidence_count=5)
        revised = base.revise(new)
        # Large frequency change with high confidence → significant debt
        assert revised.propagation_debt > 0.1

    def test_small_change_small_debt(self):
        base = TruthValue(frequency=0.5, confidence=0.8, evidence_count=5)
        similar = TruthValue(frequency=0.52, confidence=0.8, evidence_count=3)
        revised = base.revise(similar)
        assert revised.propagation_debt < 0.05

    def test_settle_clears_debt(self):
        tv = TruthValue(frequency=0.7, confidence=0.8, evidence_count=3, propagation_debt=0.3)
        settled = tv.settle_debt()
        assert settled.propagation_debt == 0.0
        assert settled.frequency == tv.frequency
        assert settled.confidence == tv.confidence

    def test_debt_proportional_to_confidence(self):
        """Higher confidence in old value = larger debt when revised."""
        low_conf = TruthValue(frequency=0.9, confidence=0.3, evidence_count=2)
        high_conf = TruthValue(frequency=0.9, confidence=0.9, evidence_count=10)
        challenger = TruthValue(frequency=0.1, confidence=0.9, evidence_count=5)
        assert (
            low_conf.revise(challenger).propagation_debt
            < high_conf.revise(challenger).propagation_debt
        )
