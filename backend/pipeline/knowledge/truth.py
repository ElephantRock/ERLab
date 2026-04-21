"""Epistemic truth maintenance via OpenNARS-inspired truth calculus.

Each knowledge assertion (gap, idea, relationship) carries a TruthValue
with frequency (proportion of supporting evidence) and confidence
(total evidence relative to evidential horizon). New evidence revises
existing truth via weighted averaging rather than overwriting.
"""

from pydantic import BaseModel


class TruthValue(BaseModel):
    """OpenNARS-inspired evidential truth value.

    frequency = P(proposition is true | evidence)
    confidence = P(evidence is sufficient)
    """

    frequency: float = 0.5
    confidence: float = 0.5
    evidence_count: int = 0
    propagation_debt: float = 0.0  # How stale downstream consumers are

    @property
    def expectation(self) -> float:
        """Weighted expectation: frequency * confidence."""
        return self.frequency * self.confidence

    def revise(self, other: "TruthValue") -> "TruthValue":
        """Weighted revision when new evidence arrives.

        Uses the OpenNARS revision rule: weights are derived from
        confidence values, and the new truth is a weighted average.
        """
        w1 = self.confidence / (1 - self.confidence + 1e-10)
        w2 = other.confidence / (1 - other.confidence + 1e-10)
        total_w = w1 + w2
        if total_w == 0:
            return TruthValue(
                frequency=0.5,
                confidence=0.5,
                evidence_count=self.evidence_count + other.evidence_count,
            )
        new_freq = (w1 * self.frequency + w2 * other.frequency) / total_w
        new_conf = total_w / (total_w + 1)
        # Propagation debt: how much truth changed, flagging downstream consumers as stale
        debt = abs(new_freq - self.frequency) * self.confidence
        return TruthValue(
            frequency=max(0.0, min(1.0, new_freq)),
            confidence=min(0.99, new_conf),
            evidence_count=self.evidence_count + other.evidence_count + 1,
            propagation_debt=debt,
        )

    def decay(self, rate: float = 0.99) -> "TruthValue":
        """Temporal truth decay. Confidence decreases over time."""
        return TruthValue(
            frequency=self.frequency,
            confidence=self.confidence * rate,
            evidence_count=self.evidence_count,
        )

    def settle_debt(self) -> "TruthValue":
        """Mark propagation debt as resolved after downstream update."""
        return TruthValue(
            frequency=self.frequency,
            confidence=self.confidence,
            evidence_count=self.evidence_count,
            propagation_debt=0.0,
        )

    @staticmethod
    def from_observation(frequency: float = 1.0) -> "TruthValue":
        """Create a TruthValue from a single observation."""
        return TruthValue(
            frequency=frequency,
            confidence=0.5,
            evidence_count=1,
        )

    @staticmethod
    def initial() -> "TruthValue":
        """Default truth value for new assertions with no prior evidence."""
        return TruthValue(
            frequency=0.5,
            confidence=0.5,
            evidence_count=0,
        )
