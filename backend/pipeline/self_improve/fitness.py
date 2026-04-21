"""Multi-dimensional fitness scoring for evolved artifacts.

Adopted from hermes-agent-self-evolution (DSPy+GEPA). Replaces scalar
metrics with per-dimension breakdown (correctness, procedure_following,
conciseness) plus a length penalty ramp that prevents evolved artifacts
from growing unboundedly.
"""

from dataclasses import dataclass


@dataclass
class FitnessScore:
    correctness: float = 0.0
    procedure_following: float = 0.0
    conciseness: float = 0.0
    length_penalty: float = 0.0
    feedback: str = ""

    @property
    def composite(self) -> float:
        """Weighted composite: 0.5*correctness + 0.3*procedure + 0.2*conciseness - penalty."""
        raw = 0.5 * self.correctness + 0.3 * self.procedure_following + 0.2 * self.conciseness
        return max(0.0, raw - self.length_penalty)

    @staticmethod
    def length_penalty_ramp(size: int, max_size: int) -> float:
        """Ramp penalty from 0 at 90% of max_size to 0.3 at max_size.

        Prevents evolved artifacts from growing unboundedly while allowing
        natural variation below the threshold.
        """
        if max_size <= 0:
            return 0.0
        ratio = size / max_size
        if ratio > 0.9:
            return min(0.3, (ratio - 0.9) * 3.0)
        return 0.0
