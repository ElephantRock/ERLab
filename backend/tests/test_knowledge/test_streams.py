"""Tests for reactive value streams: FormulaStream, StreamRegistry, QueueValue."""

from backend.pipeline.knowledge.streams import (
    FormulaStream,
    QueueValue,
    StreamRegistry,
    StreamValue,
)
from backend.pipeline.knowledge.truth import TruthValue


class TestFormulaStream:
    def test_evaluate_caches(self):
        call_count = [0]

        def formula(kg):
            call_count[0] += 1
            return 0.8

        stream = FormulaStream("test", formula, ["e1"])
        result = stream.evaluate(None, 1)
        assert result == 0.8
        assert call_count[0] == 1

        # Same version, not stale — cached
        result2 = stream.evaluate(None, 1)
        assert result2 == 0.8
        assert call_count[0] == 1

    def test_mark_stale_forces_reevaluation(self):
        call_count = [0]

        def formula(kg):
            call_count[0] += 1
            return 0.9

        stream = FormulaStream("test", formula, ["e1"])
        stream.evaluate(None, 1)
        stream.mark_stale()
        stream.evaluate(None, 1)
        assert call_count[0] == 2

    def test_check_freshness_no_change(self):
        from backend.pipeline.knowledge.versioning import ChangeRecord

        stream = FormulaStream("test", lambda kg: 0.5, ["e1"])
        stream.evaluate(None, 1)
        records = [
            ChangeRecord(version=2, operation="add_entity", target_id="e2", target_type="entity")
        ]
        stale = stream.check_freshness(records)
        assert not stale

    def test_check_freshness_dependency_changed(self):
        from backend.pipeline.knowledge.versioning import ChangeRecord

        stream = FormulaStream("test", lambda kg: 0.5, ["e1"])
        stream.evaluate(None, 1)
        records = [
            ChangeRecord(version=2, operation="update_truth", target_id="e1", target_type="entity")
        ]
        stale = stream.check_freshness(records)
        assert stale

    def test_dependencies_property(self):
        stream = FormulaStream("test", lambda kg: 0.5, ["e1", "e2"])
        assert stream.dependencies == {"e1", "e2"}


class TestStreamRegistry:
    def test_register_and_get(self):
        registry = StreamRegistry()
        stream = FormulaStream("s1", lambda kg: 0.5, [])
        registry.register(stream)
        assert registry.get("s1") is stream
        assert registry.stream_count == 1

    def test_process_changes_stale_detection(self):
        from backend.pipeline.knowledge.versioning import ChangeRecord

        registry = StreamRegistry()
        registry.register(FormulaStream("s1", lambda kg: 0.5, ["e1"]))
        registry.register(FormulaStream("s2", lambda kg: 0.7, ["e2"]))

        records = [
            ChangeRecord(version=1, operation="update_truth", target_id="e1", target_type="entity")
        ]
        stale = registry.process_changes(records)
        assert "s1" in stale
        assert "s2" not in stale

    def test_evaluate_all(self):
        registry = StreamRegistry()
        registry.register(FormulaStream("s1", lambda kg: 0.5, []))
        registry.register(FormulaStream("s2", lambda kg: 0.7, []))
        results = registry.evaluate_all(None, 1)
        assert results["s1"] == 0.5
        assert results["s2"] == 0.7

    def test_evaluate_stream(self):
        registry = StreamRegistry()
        registry.register(FormulaStream("s1", lambda kg: 0.5, []))
        assert registry.evaluate_stream("s1", None, 1) == 0.5
        assert registry.evaluate_stream("nonexistent", None, 1) is None


class TestQueueValue:
    def test_push_and_drain(self):
        q = QueueValue("test_q")
        q.push(TruthValue(frequency=0.8, confidence=0.5))
        q.push(TruthValue(frequency=0.9, confidence=0.6))
        result = q.drain()
        assert result is not None
        assert result.frequency > 0.8
        assert q.size == 0

    def test_drain_empty(self):
        q = QueueValue("empty")
        assert q.drain() is None

    def test_peek_does_not_drain(self):
        q = QueueValue("peek_test")
        q.push(TruthValue(frequency=0.8, confidence=0.5))
        q.peek()
        assert q.size == 1

    def test_max_size(self):
        q = QueueValue("bounded", max_size=3)
        for i in range(5):
            q.push(TruthValue(frequency=float(i) / 10, confidence=0.5))
        assert q.size == 3

    def test_revision_converges(self):
        q = QueueValue("converge")
        for _ in range(10):
            q.push(TruthValue(frequency=0.9, confidence=0.6))
        result = q.drain()
        assert result is not None
        assert result.confidence > 0.6

    def test_name(self):
        assert QueueValue("my_queue").name == "my_queue"


class TestStreamValue:
    def test_default_not_stale(self):
        sv = StreamValue(value=0.5, last_evaluated_version=1)
        assert not sv.stale
