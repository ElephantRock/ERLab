"""Tests for metacognitive strategy selection."""

from backend.pipeline.generation.models import Critique, ResearchIdea
from backend.pipeline.generation.strategies import (
    CriticStrategy,
    check_convergence,
    detect_loop,
    keep_best_n,
    select_strategy,
)


class TestSelectStrategy:
    def test_round_1_shallow(self):
        assert select_strategy(1, 3, False) == CriticStrategy.SHALLOW_REVIEW

    def test_round_2_deep(self):
        assert select_strategy(2, 3, False) == CriticStrategy.DEEP_DIAGNOSIS

    def test_final_round_meta(self):
        assert select_strategy(3, 3, False) == CriticStrategy.META_REFLECTION

    def test_prior_converged_meta(self):
        assert select_strategy(2, 4, True) == CriticStrategy.META_REFLECTION

    def test_mid_rounds_deep(self):
        assert select_strategy(2, 4, False) == CriticStrategy.DEEP_DIAGNOSIS
        assert select_strategy(3, 5, False) == CriticStrategy.DEEP_DIAGNOSIS


class TestCheckConvergence:
    def _make_ideas(self, scores: list[float]) -> list[ResearchIdea]:
        return [
            ResearchIdea(
                title=f"Idea {i}",
                problem_statement="",
                proposed_method="",
                expected_contributions="",
                novelty_rationale="",
                evaluation_approach="",
                score=s,
            )
            for i, s in enumerate(scores)
        ]

    def test_converged_low_delta(self):
        prev = self._make_ideas([0.7, 0.6, 0.5])
        curr = self._make_ideas([0.71, 0.61, 0.51])
        critiques = [Critique(idea_title="X", suggestions=["improve X"])]

        result = check_convergence(curr, prev, critiques, threshold=0.05)
        assert result.converged
        assert "score_delta" in result.reason

    def test_not_converged_high_delta(self):
        prev = self._make_ideas([0.5, 0.4])
        curr = self._make_ideas([0.8, 0.7])
        critiques = [Critique(idea_title="X", suggestions=["improve X"])]

        result = check_convergence(curr, prev, critiques, threshold=0.05)
        assert not result.converged

    def test_converged_no_suggestions(self):
        prev = self._make_ideas([0.7])
        curr = self._make_ideas([0.5])
        critiques = [Critique(idea_title="X", suggestions=["", "  "])]

        result = check_convergence(curr, prev, critiques)
        assert result.converged
        assert result.reason == "no_substantive_suggestions"

    def test_insufficient_data(self):
        result = check_convergence([], [], [])
        assert not result.converged
        assert result.reason == "insufficient_data"


class TestDetectLoop:
    def _make_critiques(self, weaknesses: list[list[str]]) -> list[Critique]:
        return [
            Critique(idea_title=f"Idea {i}", weaknesses=w)
            for i, w in enumerate(weaknesses)
        ]

    def test_loop_detected(self):
        current = self._make_critiques([["lacks novelty", "poor evaluation"]])
        history = [self._make_critiques([["lacks novelty", "poor evaluation"]])]

        assert detect_loop(current, history) is True

    def test_no_loop(self):
        current = self._make_critiques([["needs more data"]])
        history = [self._make_critiques([["lacks novelty"]])]

        assert detect_loop(current, history) is False

    def test_empty_history(self):
        current = self._make_critiques([["weakness"]])
        assert detect_loop(current, []) is False

    def test_empty_critiques(self):
        assert detect_loop([], [["past"]]) is False


class TestKeepBestN:
    def test_filters_by_min_score(self):
        ideas = [
            ResearchIdea(title="A", problem_statement="", proposed_method="",
                         expected_contributions="", novelty_rationale="",
                         evaluation_approach="", score=0.8),
            ResearchIdea(title="B", problem_statement="", proposed_method="",
                         expected_contributions="", novelty_rationale="",
                         evaluation_approach="", score=0.2),
            ResearchIdea(title="C", problem_statement="", proposed_method="",
                         expected_contributions="", novelty_rationale="",
                         evaluation_approach="", score=0.5),
        ]
        result = keep_best_n(ideas, n=3, min_score=0.3)
        assert len(result) == 2
        assert result[0].title == "A"
        assert result[1].title == "C"

    def test_limits_to_n(self):
        ideas = [
            ResearchIdea(title=f"I{i}", problem_statement="", proposed_method="",
                         expected_contributions="", novelty_rationale="",
                         evaluation_approach="", score=0.9 - i * 0.1)
            for i in range(10)
        ]
        result = keep_best_n(ideas, n=3)
        assert len(result) == 3
        assert result[0].score >= result[1].score >= result[2].score

    def test_empty_input(self):
        assert keep_best_n([], n=5) == []
