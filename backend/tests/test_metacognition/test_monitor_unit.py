"""Tests for metacognitive self-monitor."""

from backend.pipeline.metacognition.monitor import (
    MetacognitiveMonitor,
    MonitoringThresholds,
    SignalType,
)


class TestMetacognitiveMonitor:
    def test_observe_and_check_no_signals(self):
        monitor = MetacognitiveMonitor()
        monitor.observe(score=0.8, round_num=1)
        signals = monitor.check()
        assert len(signals) == 0
        assert monitor.observation_count == 1
        assert monitor.latest_score == 0.8

    def test_quality_drop_detection(self):
        monitor = MetacognitiveMonitor(MonitoringThresholds(quality_drop_threshold=0.3))
        monitor.observe(score=0.9, round_num=1)
        monitor.observe(score=0.4, round_num=2)
        signals = monitor.check()
        assert len(signals) >= 1
        assert any(s.signal_type == SignalType.QUALITY_DROP for s in signals)

    def test_no_quality_drop_within_threshold(self):
        monitor = MetacognitiveMonitor(MonitoringThresholds(quality_drop_threshold=0.3))
        monitor.observe(score=0.8, round_num=1)
        monitor.observe(score=0.7, round_num=2)
        signals = monitor.check()
        assert not any(s.signal_type == SignalType.QUALITY_DROP for s in signals)

    def test_stagnation_detection(self):
        monitor = MetacognitiveMonitor(MonitoringThresholds(stagnation_rounds=3))
        for i in range(5):
            monitor.observe(score=0.5, round_num=i)
        signals = monitor.check()
        assert any(s.signal_type == SignalType.STAGNATION for s in signals)

    def test_no_stagnation_with_improvement(self):
        monitor = MetacognitiveMonitor(MonitoringThresholds(stagnation_rounds=3))
        monitor.observe(score=0.5)
        monitor.observe(score=0.6)
        monitor.observe(score=0.7)
        monitor.observe(score=0.8)
        signals = monitor.check()
        assert not any(s.signal_type == SignalType.STAGNATION for s in signals)

    def test_convergence_stall(self):
        monitor = MetacognitiveMonitor(MonitoringThresholds(convergence_stall_rounds=3))
        for i in range(4):
            monitor.observe(score=0.5, round_num=i, converged=False)
        signals = monitor.check()
        assert any(s.signal_type == SignalType.CONVERGENCE_STALL for s in signals)

    def test_no_stall_when_converged(self):
        monitor = MetacognitiveMonitor(MonitoringThresholds(convergence_stall_rounds=3))
        for i in range(3):
            monitor.observe(score=0.8, round_num=i, converged=False)
        monitor.observe(score=0.9, round_num=3, converged=True)
        signals = monitor.check()
        assert not any(s.signal_type == SignalType.CONVERGENCE_STALL for s in signals)

    def test_signals_accumulate(self):
        monitor = MetacognitiveMonitor(MonitoringThresholds(quality_drop_threshold=0.3))
        monitor.observe(score=0.9)
        monitor.observe(score=0.4)
        monitor.check()
        assert len(monitor.signals) == 1
        monitor.observe(score=0.1)
        monitor.check()
        assert len(monitor.signals) >= 2

    def test_latest_score_none_initially(self):
        monitor = MetacognitiveMonitor()
        assert monitor.latest_score is None
