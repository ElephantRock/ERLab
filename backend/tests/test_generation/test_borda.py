"""Tests for Borda tournament convergence."""

from backend.pipeline.generation.borda import (
    BordaTournament,
    TournamentState,
    aggregate_rankings,
    randomize_for_judge,
)


class TestRandomizeForJudge:
    def test_all_versions_present(self):
        prompt, order = randomize_for_judge("alpha", "beta", "gamma")
        assert "alpha" in prompt
        assert "beta" in prompt
        assert "gamma" in prompt

    def test_order_maps_to_labels(self):
        _, order = randomize_for_judge("a", "b", "c")
        assert set(order.values()) == {"A", "B", "AB"}

    def test_different_shuffles(self):
        # With random shuffling, running 20 times should produce at least 2 different orders
        orders = set()
        for _ in range(20):
            _, order = randomize_for_judge("a", "b", "c")
            orders.add(tuple(sorted(order.items())))
        assert len(orders) >= 2


class TestAggregateRankings:
    def test_clear_winner(self):
        rankings = [
            ["A", "B", "AB"],
            ["A", "AB", "B"],
            ["A", "B", "AB"],
        ]
        winner, scores = aggregate_rankings(rankings)
        assert winner == "A"
        assert scores["A"] > scores["B"]
        assert scores["A"] > scores["AB"]

    def test_borda_counts_correct(self):
        # A: 3+3+3=9, B: 2+1+2=5, AB: 1+2+1=4
        rankings = [
            ["A", "B", "AB"],
            ["A", "AB", "B"],
            ["A", "B", "AB"],
        ]
        _, scores = aggregate_rankings(rankings)
        assert scores["A"] == 9
        assert scores["B"] == 5
        assert scores["AB"] == 4

    def test_tiebreak(self):
        rankings = [
            ["A", "B", "AB"],
            ["B", "A", "AB"],
        ]
        winner, scores = aggregate_rankings(rankings)
        # A: 3+2=5, B: 2+3=5 — max picks first alphabetically
        assert winner in ("A", "B")
        assert scores["A"] == scores["B"]

    def test_custom_labels(self):
        rankings = [
            ["x", "y", "z"],
        ]
        winner, scores = aggregate_rankings(rankings, labels=["x", "y", "z"])
        assert winner == "x"


class TestTournamentState:
    def test_streak_increments_on_a(self):
        state = TournamentState()
        state.update("A", {"A": 5, "B": 3, "AB": 1})
        assert state.streak == 1
        assert state.rounds == 1

    def test_streak_resets_on_non_a(self):
        state = TournamentState()
        state.update("A", {"A": 5, "B": 3, "AB": 1})
        state.update("B", {"A": 2, "B": 5, "AB": 1})
        assert state.streak == 0
        assert state.rounds == 2

    def test_converged_at_k2(self):
        state = TournamentState()
        state.update("A", {"A": 5, "B": 3, "AB": 1})
        assert not state.converged
        state.update("A", {"A": 5, "B": 3, "AB": 1})
        assert state.converged


class TestBordaTournament:
    def test_converges_after_two_incumbent_wins(self):
        t = BordaTournament(k=2)
        assert not t.check_converged("A", {"A": 5, "B": 3, "AB": 1})
        assert t.check_converged("A", {"A": 5, "B": 3, "AB": 1})

    def test_does_not_converge_with_challenger_win(self):
        t = BordaTournament(k=2)
        t.check_converged("A", {"A": 5, "B": 3, "AB": 1})
        result = t.check_converged("B", {"A": 2, "B": 5, "AB": 1})
        assert not result

    def test_format_judge_prompt_contains_proposals(self):
        prompt = BordaTournament.format_judge_prompt("PROPOSAL 1:\n---\ntest\n---")
        assert "PROPOSAL 1" in prompt
        assert "blind judge" in prompt
