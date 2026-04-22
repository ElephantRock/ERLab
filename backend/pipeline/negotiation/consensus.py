"""Consensus voting algorithms — majority, Borda count, unanimous, weighted."""

from __future__ import annotations

from enum import Enum

from backend.pipeline.generation.borda import aggregate_rankings
from backend.pipeline.negotiation.protocol import ConsensusResult, Vote


class ConsensusAlgorithm(str, Enum):
    MAJORITY_VOTE = "majority_vote"
    BORDA_COUNT = "borda_count"
    UNANIMOUS = "unanimous"
    WEIGHTED_SCORE = "weighted_score"


class ConsensusEngine:
    """Evaluates votes to determine consensus using configurable algorithms."""

    def __init__(self, algorithm: ConsensusAlgorithm = ConsensusAlgorithm.WEIGHTED_SCORE) -> None:
        self._algorithm = algorithm

    def evaluate(self, votes: list[Vote], threshold: float = 0.7) -> ConsensusResult:
        if not votes:
            return ConsensusResult(is_deadlock=True)

        handler = {
            ConsensusAlgorithm.MAJORITY_VOTE: self._majority_vote,
            ConsensusAlgorithm.BORDA_COUNT: self._borda_count,
            ConsensusAlgorithm.UNANIMOUS: self._unanimous,
            ConsensusAlgorithm.WEIGHTED_SCORE: self._weighted_score,
        }[self._algorithm]

        return handler(votes, threshold)

    def _majority_vote(self, votes: list[Vote], threshold: float) -> ConsensusResult:
        proposal_scores: dict[str, list[float]] = {}
        for v in votes:
            proposal_scores.setdefault(v.proposal_id, []).append(v.score)

        best_id: str | None = None
        best_score = 0.0
        for pid, scores in proposal_scores.items():
            avg = sum(scores) / len(scores)
            if avg > best_score:
                best_score = avg
                best_id = pid

        is_consensus = best_score >= threshold
        return ConsensusResult(
            proposal_id=best_id,
            consensus_score=best_score,
            votes=votes,
            is_consensus=is_consensus,
            is_deadlock=not is_consensus and best_score < threshold * 0.5,
        )

    def _borda_count(self, votes: list[Vote], threshold: float) -> ConsensusResult:
        proposal_ids = list({v.proposal_id for v in votes})
        if len(proposal_ids) < 2:
            return self._majority_vote(votes, threshold)

        rankings: list[list[str]] = []
        voter_ids = sorted({v.voter_id for v in votes})
        for vid in voter_ids:
            voter_votes = [v for v in votes if v.voter_id == vid]
            voter_votes.sort(key=lambda v: v.score, reverse=True)
            rankings.append([v.proposal_id for v in voter_votes])

        winner, scores = aggregate_rankings(rankings, labels=proposal_ids)
        max_score = max(scores.values()) if scores else 0
        total = sum(scores.values()) if scores else 1
        normalized = max_score / total if total > 0 else 0.0

        return ConsensusResult(
            proposal_id=winner,
            consensus_score=normalized,
            votes=votes,
            is_consensus=normalized >= threshold,
            is_deadlock=not (normalized >= threshold),
        )

    def _unanimous(self, votes: list[Vote], threshold: float) -> ConsensusResult:
        proposal_scores: dict[str, list[float]] = {}
        for v in votes:
            proposal_scores.setdefault(v.proposal_id, []).append(v.score)

        for pid, scores in proposal_scores.items():
            if all(s >= threshold for s in scores):
                avg = sum(scores) / len(scores)
                return ConsensusResult(
                    proposal_id=pid,
                    consensus_score=avg,
                    votes=votes,
                    is_consensus=True,
                )

        return ConsensusResult(
            proposal_id=None,
            consensus_score=0.0,
            votes=votes,
            is_consensus=False,
            is_deadlock=True,
        )

    def _weighted_score(self, votes: list[Vote], threshold: float) -> ConsensusResult:
        proposal_scores: dict[str, float] = {}
        proposal_counts: dict[str, int] = {}
        for v in votes:
            proposal_scores[v.proposal_id] = proposal_scores.get(v.proposal_id, 0.0) + v.score
            proposal_counts[v.proposal_id] = proposal_counts.get(v.proposal_id, 0) + 1

        best_id: str | None = None
        best_avg = 0.0
        for pid in proposal_scores:
            avg = proposal_scores[pid] / proposal_counts[pid]
            if avg > best_avg:
                best_avg = avg
                best_id = pid

        is_consensus = best_avg >= threshold
        return ConsensusResult(
            proposal_id=best_id,
            consensus_score=best_avg,
            votes=votes,
            is_consensus=is_consensus,
            is_deadlock=not is_consensus,
        )
