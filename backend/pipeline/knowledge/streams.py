"""Reactive value streams for derived knowledge graph values.

FormulaStream lazily computes derived values and auto-invalidates
when dependencies change (via ChangeRecord) or have stale truth
(propagation_debt > 0). QueueValue aggregates multiple TruthValue
observations into a consensus via iterative revision.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING

from pydantic import BaseModel

from backend.pipeline.knowledge.truth import TruthValue

if TYPE_CHECKING:
    from backend.pipeline.knowledge.versioning import ChangeRecord


class StreamValue(BaseModel):
    """Cached result of a stream evaluation."""

    value: float
    last_evaluated_version: int
    stale: bool = False


class FormulaStream:
    """Lazy-evaluated derived value that depends on graph elements.

    The formula is only re-evaluated when:
    1. A ChangeRecord affects one of the declared dependencies
    2. A dependency's TruthValue has propagation_debt > 0
    """

    def __init__(
        self,
        name: str,
        formula: Callable,
        dependencies: list[str],
    ):
        self._name = name
        self._formula = formula
        self._dependencies = set(dependencies)
        self._cached: StreamValue | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def dependencies(self) -> set[str]:
        return set(self._dependencies)

    def evaluate(self, kg, current_version: int) -> float:
        if (
            self._cached
            and not self._cached.stale
            and self._cached.last_evaluated_version == current_version
        ):
            return self._cached.value
        result = self._formula(kg)
        self._cached = StreamValue(value=result, last_evaluated_version=current_version)
        return result

    def mark_stale(self) -> None:
        if self._cached:
            self._cached.stale = True

    def check_freshness(self, change_records: list[ChangeRecord], kg=None) -> bool:
        """Check if any change affects a dependency. Returns True if stale."""
        became_stale = False
        for record in change_records:
            if record.target_id in self._dependencies:
                self.mark_stale()
                became_stale = True
                break

        # Also check propagation_debt on dependencies
        if not became_stale and kg:
            for dep_id in self._dependencies:
                entity = kg.get_entity(dep_id)
                if entity and entity.truth.propagation_debt > 0:
                    self.mark_stale()
                    became_stale = True
                    break

        return became_stale


class StreamRegistry:
    """Manages all active formula streams."""

    def __init__(self):
        self._streams: dict[str, FormulaStream] = {}

    def register(self, stream: FormulaStream) -> None:
        self._streams[stream.name] = stream

    def get(self, name: str) -> FormulaStream | None:
        return self._streams.get(name)

    def process_changes(self, changes: list[ChangeRecord], kg=None) -> list[str]:
        """Mark affected streams stale. Returns names of stale streams."""
        stale_names = []
        for stream in self._streams.values():
            if stream.check_freshness(changes, kg):
                stale_names.append(stream.name)
        return stale_names

    def evaluate_all(self, kg, current_version: int) -> dict[str, float]:
        return {
            name: stream.evaluate(kg, current_version) for name, stream in self._streams.items()
        }

    def evaluate_stream(self, name: str, kg, current_version: int) -> float | None:
        stream = self._streams.get(name)
        if stream:
            return stream.evaluate(kg, current_version)
        return None

    @property
    def stream_count(self) -> int:
        return len(self._streams)


class QueueValue:
    """Bounded FIFO for aggregating TruthValue observations.

    Push observations from multiple pipeline stages, drain to
    get the consensus truth via iterative revision.
    """

    def __init__(self, name: str, max_size: int = 1000):
        self._name = name
        self._queue: deque[TruthValue] = deque(maxlen=max_size)

    def push(self, tv: TruthValue) -> None:
        self._queue.append(tv)

    def drain(self) -> TruthValue | None:
        if not self._queue:
            return None
        result = self._queue.popleft()
        while self._queue:
            result = result.revise(self._queue.popleft())
        return result

    def peek(self) -> TruthValue | None:
        if not self._queue:
            return None
        result = self._queue[0]
        for tv in list(self._queue)[1:]:
            result = result.revise(tv)
        return result

    @property
    def size(self) -> int:
        return len(self._queue)

    @property
    def name(self) -> str:
        return self._name
