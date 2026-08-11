"""BATCH-167: Error Analysis, Guard Commands & Plateau Detection."""
from backend.pipeline.metacognition.plateau import GuardAction, PlateauCheck, PlateauDetector


class TestPlateauDetector:

    def test_01_not_enough_data(self):
        det = PlateauDetector(window_size=3)
        result = det.check("test", [0.5, 0.6])
        assert not result.is_plateau
        assert result.action == GuardAction.CONTINUE

    def test_02_improving_not_plateau(self):
        det = PlateauDetector(window_size=3, threshold=0.01)
        result = det.check("test", [0.5, 0.6, 0.7])
        assert not result.is_plateau
        assert result.delta > 0.01

    def test_03_plateau_triggers_retry(self):
        det = PlateauDetector(window_size=3, threshold=0.01, max_retries=2)
        result = det.check("test", [0.5, 0.5, 0.505])
        assert result.is_plateau
        assert result.action == GuardAction.RETRY

    def test_04_max_retries_triggers_skip(self):
        det = PlateauDetector(window_size=3, threshold=0.01, max_retries=1)
        det.check("test", [0.5, 0.5, 0.505])  # First retry
        result = det.check("test", [0.5, 0.5, 0.505])  # Second check
        assert result.is_plateau
        assert result.action == GuardAction.SKIP

    def test_05_reset_clears_retries(self):
        det = PlateauDetector(window_size=3, threshold=0.01, max_retries=1)
        det.check("test", [0.5, 0.5, 0.505])
        det.reset("test")
        result = det.check("test", [0.5, 0.5, 0.505])
        assert result.action == GuardAction.RETRY  # Fresh retry

    def test_06_reset_all(self):
        det = PlateauDetector(window_size=3, threshold=0.01, max_retries=1)
        det.check("a", [0.5, 0.5, 0.505])
        det.check("b", [0.5, 0.5, 0.505])
        det.reset()
        assert det._retry_counts == {}

    def test_07_plateau_check_dataclass(self):
        pc = PlateauCheck(stage_name="test", is_plateau=True, score_history=[0.5])
        assert pc.stage_name == "test"
        assert pc.delta == 0.0
        assert pc.action == GuardAction.CONTINUE

    def test_08_guard_action_enum(self):
        assert GuardAction.CONTINUE.value == "continue"
        assert GuardAction.RETRY.value == "retry"
        assert GuardAction.SKIP.value == "skip"
        assert GuardAction.HALT.value == "halt"

    def test_09_exact_zero_delta_is_plateau(self):
        det = PlateauDetector(window_size=3, threshold=0.01)
        result = det.check("test", [0.5, 0.5, 0.5])
        assert result.is_plateau
        assert result.delta == 0.0

    def test_10_metacognition_monitor_exists(self):
        from backend.pipeline.metacognition.monitor import InterventionSignal, SignalType
        assert SignalType.STAGNATION is not None
        assert InterventionSignal is not None
