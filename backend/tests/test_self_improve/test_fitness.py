"""Tests for multi-dimensional fitness scoring."""

from backend.pipeline.self_improve.fitness import FitnessScore


class TestFitnessScore:
    def test_composite_weighted_sum(self):
        fs = FitnessScore(correctness=1.0, procedure_following=1.0, conciseness=1.0)
        # 0.5*1 + 0.3*1 + 0.2*1 = 1.0, no penalty
        assert fs.composite == 1.0

    def test_composite_with_penalty(self):
        fs = FitnessScore(
            correctness=1.0, procedure_following=1.0, conciseness=1.0, length_penalty=0.2
        )
        assert abs(fs.composite - 0.8) < 1e-9

    def test_composite_clamps_to_zero(self):
        fs = FitnessScore(
            correctness=0.0, procedure_following=0.0, conciseness=0.0, length_penalty=0.5
        )
        assert fs.composite == 0.0

    def test_partial_scores(self):
        fs = FitnessScore(correctness=0.8, procedure_following=0.6, conciseness=0.4)
        # 0.5*0.8 + 0.3*0.6 + 0.2*0.4 = 0.4 + 0.18 + 0.08 = 0.66
        assert abs(fs.composite - 0.66) < 1e-9

    def test_length_penalty_ramp_below_threshold(self):
        # 80% of max — no penalty
        assert FitnessScore.length_penalty_ramp(80, 100) == 0.0

    def test_length_penalty_ramp_at_threshold(self):
        # 90% of max — penalty starts
        assert FitnessScore.length_penalty_ramp(90, 100) == 0.0

    def test_length_penalty_ramp_mid_range(self):
        # 95% of max — (0.95-0.9)*3 = 0.15
        assert abs(FitnessScore.length_penalty_ramp(95, 100) - 0.15) < 1e-9

    def test_length_penalty_ramp_capped_at_max(self):
        # 100% of max — (1.0-0.9)*3 = 0.3
        assert abs(FitnessScore.length_penalty_ramp(100, 100) - 0.3) < 1e-9

    def test_length_penalty_ramp_over_max(self):
        # 200% of max — capped at 0.3
        assert FitnessScore.length_penalty_ramp(200, 100) == 0.3

    def test_length_penalty_zero_max(self):
        assert FitnessScore.length_penalty_ramp(50, 0) == 0.0
