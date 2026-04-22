"""Rolling-window latency tracker per provider."""

from __future__ import annotations

from collections import defaultdict, deque


class LatencyTracker:
    def __init__(self, window_size: int = 100) -> None:
        self._window_size = window_size
        self._windows: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=self._window_size)
        )

    def record(self, provider: str, duration_ms: float) -> None:
        self._windows[provider].append(duration_ms)

    def avg_latency(self, provider: str) -> float:
        w = self._windows.get(provider)
        if not w:
            return 0.0
        return sum(w) / len(w)

    def p50(self, provider: str) -> float:
        w = self._windows.get(provider)
        if not w:
            return 0.0
        s = sorted(w)
        mid = len(s) // 2
        return s[mid]

    def count(self, provider: str) -> int:
        return len(self._windows.get(provider, []))

    def snapshot(self) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for name, w in self._windows.items():
            if not w:
                continue
            result[name] = {
                "avg_ms": sum(w) / len(w),
                "p50_ms": sorted(w)[len(w) // 2],
                "count": len(w),
            }
        return result
