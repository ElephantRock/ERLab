"""Tests for ProgressLedger and LedgerEntry."""


from backend.pipeline.metacognitive.ledger import LedgerEntry, ProgressLedger
from backend.tests.test_metacognitive.conftest import make_entry


class TestLedgerEntry:
    def test_defaults(self):
        entry = LedgerEntry(stage="s", metric_name="m", value=1.0)
        assert entry.round_num is None
        assert entry.threshold is None
        assert entry.passed is True
        assert entry.metadata == {}
        assert entry.timestamp > 0

    def test_custom_fields(self):
        entry = LedgerEntry(
            stage="idea_generation",
            metric_name="novelty",
            value=0.8,
            threshold=0.5,
            passed=True,
            round_num=2,
            metadata={"source": "test"},
        )
        assert entry.round_num == 2
        assert entry.threshold == 0.5
        assert entry.metadata["source"] == "test"


class TestProgressLedgerRecord:
    def test_record_appends(self, ledger: ProgressLedger):
        ledger.record(make_entry(value=0.1))
        ledger.record(make_entry(value=0.2))
        assert len(ledger._entries) == 2

    def test_record_preserves_order(self, ledger: ProgressLedger):
        ledger.record(make_entry(value=1.0))
        ledger.record(make_entry(value=2.0))
        assert ledger._entries[0].value == 1.0
        assert ledger._entries[1].value == 2.0


class TestProgressLedgerQuery:
    def test_query_by_stage(self, ledger: ProgressLedger):
        ledger.record(make_entry(stage="gen", value=0.5))
        ledger.record(make_entry(stage="eval", value=0.7))
        ledger.record(make_entry(stage="gen", value=0.6))
        results = ledger.query(stage="gen")
        assert len(results) == 2
        assert all(e.stage == "gen" for e in results)

    def test_query_by_metric(self, ledger: ProgressLedger):
        ledger.record(make_entry(metric_name="novelty", value=0.3))
        ledger.record(make_entry(metric_name="feasibility", value=0.4))
        ledger.record(make_entry(metric_name="novelty", value=0.5))
        results = ledger.query(metric="novelty")
        assert len(results) == 2

    def test_query_by_both(self, ledger: ProgressLedger):
        ledger.record(make_entry(stage="gen", metric_name="a", value=1.0))
        ledger.record(make_entry(stage="gen", metric_name="b", value=2.0))
        ledger.record(make_entry(stage="eval", metric_name="a", value=3.0))
        results = ledger.query(stage="gen", metric="a")
        assert len(results) == 1
        assert results[0].value == 1.0

    def test_query_no_filters(self, ledger: ProgressLedger):
        ledger.record(make_entry())
        ledger.record(make_entry())
        assert len(ledger.query()) == 2

    def test_query_empty_ledger(self, ledger: ProgressLedger):
        assert ledger.query(stage="anything") == []


class TestProgressLedgerLatest:
    def test_latest_returns_most_recent(self, ledger: ProgressLedger):
        ledger.record(make_entry(metric_name="score", value=0.1))
        ledger.record(make_entry(metric_name="score", value=0.9))
        latest = ledger.latest("score")
        assert latest is not None
        assert latest.value == 0.9

    def test_latest_missing_metric(self, ledger: ProgressLedger):
        assert ledger.latest("nonexistent") is None


class TestProgressLedgerTrajectory:
    def test_trajectory_returns_values(self, ledger: ProgressLedger):
        for v in [0.1, 0.3, 0.5, 0.7]:
            ledger.record(make_entry(metric_name="score", value=v))
        assert ledger.trajectory("score") == [0.1, 0.3, 0.5, 0.7]

    def test_trajectory_last_n(self, ledger: ProgressLedger):
        for v in [0.1, 0.2, 0.3, 0.4, 0.5]:
            ledger.record(make_entry(metric_name="score", value=v))
        assert ledger.trajectory("score", last_n=3) == [0.3, 0.4, 0.5]

    def test_trajectory_empty(self, ledger: ProgressLedger):
        assert ledger.trajectory("missing") == []


class TestProgressLedgerSummary:
    def test_empty_summary(self, ledger: ProgressLedger):
        s = ledger.summary()
        assert s["entry_count"] == 0
        assert s["pass_rate"] == 0.0

    def test_summary_counts(self, ledger: ProgressLedger):
        ledger.record(make_entry(metric_name="a", passed=True))
        ledger.record(make_entry(metric_name="b", passed=False))
        ledger.record(make_entry(metric_name="a", passed=True))
        s = ledger.summary()
        assert s["entry_count"] == 3
        assert s["metrics"] == ["a", "b"]
        assert abs(s["pass_rate"] - 2 / 3) < 1e-9


class TestProgressLedgerReset:
    def test_reset_clears(self, ledger: ProgressLedger):
        ledger.record(make_entry())
        ledger.reset()
        assert len(ledger._entries) == 0
        assert ledger.summary()["entry_count"] == 0
