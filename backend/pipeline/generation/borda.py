"""Borda tournament convergence for multi-agent idea generation.

Adopted from autoreason (ICLR 2026 Oral, 42/42 eval sweep). Each iteration
produces 3 competing versions — unchanged incumbent (A), adversarial revision
(B), synthesis (AB). Fresh judge agents rank them via blind Borda count.
"Do nothing" (A) is always a first-class option. Converges when incumbent
wins k consecutive times.
"""

import logging
import random
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def randomize_for_judge(va: str, vb: str, vab: str) -> tuple[str, dict[str, str]]:
    """Shuffle version labels to eliminate positional bias.

    Returns (randomized_prompt, order_map) where order_map maps
    display position ("1", "2", "3") to original labels ("A", "B", "AB").
    """
    versions = [("A", va), ("B", vb), ("AB", vab)]
    random.shuffle(versions)
    order = {str(i + 1): label for i, (label, _) in enumerate(versions)}
    parts = [f"PROPOSAL {i + 1}:\n---\n{content}\n---" for i, (_, content) in enumerate(versions)]
    return "\n\n".join(parts), order


def aggregate_rankings(
    rankings: list[list[str]],
    labels: list[str] | None = None,
) -> tuple[str, dict[str, int]]:
    """Borda count aggregation across multiple judge rankings.

    Each ranking is a list of labels in preference order (best first).
    Returns (winner_label, scores_dict).
    """
    if labels is None:
        labels = ["A", "B", "AB"]
    scores = {label: 0 for label in labels}
    n = len(labels)

    for ranking in rankings:
        for pos, label in enumerate(ranking):
            if label in scores and pos < n:
                scores[label] += n - pos

    winner = max(scores, key=scores.get)  # type: ignore[arg-type]
    return winner, scores


@dataclass
class TournamentState:
    """Tracks state across Borda tournament rounds."""

    streak: int = 0
    rounds: int = 0
    history: list[dict[str, int]] = field(default_factory=list)

    def update(self, winner: str, scores: dict[str, int]) -> None:
        self.rounds += 1
        self.history.append(scores)
        if winner == "A":
            self.streak += 1
        else:
            self.streak = 0

    @property
    def converged(self) -> bool:
        """True when the incumbent has won enough consecutive rounds."""
        return self.streak >= 2  # k=2 default from autoreason


class BordaTournament:
    """Borda tournament for idea refinement convergence.

    Each round:
      1. Produce 3 versions: incumbent (A), adversarial (B), synthesis (AB)
      2. Fresh judges rank them blindly (randomized order)
      3. Borda count determines winner
      4. If incumbent wins k consecutive times, tournament converges

    This prevents scope creep (incumbent competes as equal) and positional
    bias (labels are shuffled for each judge).
    """

    def __init__(self, k: int = 2):
        self._k = k
        self._state = TournamentState()

    @property
    def state(self) -> TournamentState:
        return self._state

    def check_converged(self, winner: str, scores: dict[str, int]) -> bool:
        """Record result and check if tournament has converged."""
        self._state.update(winner, scores)
        if self._state.converged:
            logger.info(
                "Borda tournament converged after %d rounds (streak=%d)",
                self._state.rounds,
                self._state.streak,
            )
        return self._state.converged

    @staticmethod
    def format_judge_prompt(randomized_text: str) -> str:
        """Format the blind judging prompt for a fresh judge agent."""
        return (
            "You are a blind judge. Rank these 3 proposals from best to worst.\n"
            "Consider: novelty, feasibility, and clarity.\n"
            "Respond with ONLY a ranking like: 1 > 2 > 3\n\n"
            f"{randomized_text}"
        )


def borda_rank_graph_nodes(
    node_scores: dict[str, list[float]],
) -> tuple[str, dict[str, int]]:
    """Borda count across multiple scoring dimensions for graph-of-thoughts nodes.

    Each node has a list of dimension scores (e.g., novelty, feasibility, impact).
    Aggregates across dimensions using Borda count, then returns the winner.

    Args:
        node_scores: maps node_id -> list of dimension scores.

    Returns:
        (winner_id, borda_scores_dict)
    """
    node_ids = list(node_scores.keys())
    if not node_ids:
        return "", {}
    if len(node_ids) == 1:
        return node_ids[0], {node_ids[0]: 1}

    n_dims = len(next(iter(node_scores.values())))
    scores = {nid: 0 for nid in node_ids}

    for dim in range(n_dims):
        dim_scores = [(nid, node_scores[nid][dim]) for nid in node_ids]
        dim_scores.sort(key=lambda x: x[1], reverse=True)
        for pos, (nid, _) in enumerate(dim_scores):
            scores[nid] += len(node_ids) - pos

    winner = max(scores, key=scores.get)  # type: ignore[arg-type]
    return winner, scores
