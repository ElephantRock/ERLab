"""Ratchet loop — terminates self-improvement when scores plateau.

Tracks a sliding window of composite scores and signals termination
when improvement stalls below a configurable threshold. Prevents
wasted compute on converged optimization.
"""

from __future__ import annotations


class RatchetLoop:
    """Monitors composite scores and signals when improvement has plateaued."""

    def __init__(
        self,
        window_size: int = 3,
        min_improvement: float = 0.02,
    ) -> None:
        self._scores: list[float] = []
        self._window_size = max(2, window_size)
        self._min_improvement = min_improvement

    def record(self, score: float) -> None:
        """Record a composite score from a run or evaluation."""
        self._scores.append(score)

    def should_terminate(self) -> bool:
        """True if the last window_size scores show no meaningful improvement.

        Compares the average of the first half of the window against the
        average of the second half. If improvement < min_improvement,
        the optimization has plateaued.
        """
        if len(self._scores) < self._window_size:
            return False

        window = self._scores[-self._window_size:]
        mid = len(window) // 2
        first_half_avg = sum(window[:mid]) / mid if mid > 0 else 0.0
        second_half_avg = sum(window[mid:]) / (len(window) - mid)

        improvement = second_half_avg - first_half_avg
        return improvement < self._min_improvement

    @property
    def best_score(self) -> float:
        """The best score recorded so far."""
        return max(self._scores) if self._scores else 0.0

    @property
    def latest_score(self) -> float:
        """The most recently recorded score."""
        return self._scores[-1] if self._scores else 0.0

    @property
    def run_count(self) -> int:
        return len(self._scores)

    def reset(self) -> None:
        """Clear all recorded scores."""
        self._scores.clear()
