"""Tests for consensus voting algorithms."""


from backend.pipeline.negotiation.consensus import ConsensusAlgorithm, ConsensusEngine
from backend.pipeline.negotiation.protocol import Vote


def _vote(voter: str, proposal: str, score: float) -> Vote:
    return Vote(voter_id=voter, proposal_id=proposal, score=score)


class TestConsensusEngine:
    def test_empty_votes_returns_deadlock(self):
        engine = ConsensusEngine()
        result = engine.evaluate([])
        assert result.is_deadlock is True

    def test_majority_vote_consensus(self):
        engine = ConsensusEngine(ConsensusAlgorithm.MAJORITY_VOTE)
        votes = [
            _vote("a1", "p1", 0.9),
            _vote("a2", "p1", 0.8),
            _vote("a3", "p2", 0.6),
        ]
        result = engine.evaluate(votes, threshold=0.7)
        assert result.is_consensus is True
        assert result.proposal_id == "p1"

    def test_majority_vote_no_consensus(self):
        engine = ConsensusEngine(ConsensusAlgorithm.MAJORITY_VOTE)
        votes = [
            _vote("a1", "p1", 0.5),
            _vote("a2", "p2", 0.4),
        ]
        result = engine.evaluate(votes, threshold=0.8)
        assert result.is_consensus is False

    def test_weighted_score_consensus(self):
        engine = ConsensusEngine(ConsensusAlgorithm.WEIGHTED_SCORE)
        votes = [
            _vote("a1", "p1", 0.9),
            _vote("a2", "p1", 0.8),
        ]
        result = engine.evaluate(votes, threshold=0.7)
        assert result.is_consensus is True
        assert result.proposal_id == "p1"

    def test_weighted_score_no_consensus(self):
        engine = ConsensusEngine(ConsensusAlgorithm.WEIGHTED_SCORE)
        votes = [
            _vote("a1", "p1", 0.4),
            _vote("a2", "p1", 0.3),
        ]
        result = engine.evaluate(votes, threshold=0.7)
        assert result.is_consensus is False

    def test_unanimous_consensus(self):
        engine = ConsensusEngine(ConsensusAlgorithm.UNANIMOUS)
        votes = [
            _vote("a1", "p1", 0.9),
            _vote("a2", "p1", 0.8),
        ]
        result = engine.evaluate(votes, threshold=0.7)
        assert result.is_consensus is True

    def test_unanimous_no_consensus(self):
        engine = ConsensusEngine(ConsensusAlgorithm.UNANIMOUS)
        votes = [
            _vote("a1", "p1", 0.9),
            _vote("a2", "p1", 0.5),
        ]
        result = engine.evaluate(votes, threshold=0.7)
        assert result.is_consensus is False
        assert result.is_deadlock is True

    def test_borda_count_single_proposal_falls_back(self):
        engine = ConsensusEngine(ConsensusAlgorithm.BORDA_COUNT)
        votes = [_vote("a1", "p1", 0.9)]
        result = engine.evaluate(votes, threshold=0.5)
        assert result.proposal_id == "p1"

    def test_borda_count_multiple_proposals(self):
        engine = ConsensusEngine(ConsensusAlgorithm.BORDA_COUNT)
        votes = [
            _vote("a1", "p1", 0.9),
            _vote("a1", "p2", 0.3),
            _vote("a2", "p1", 0.8),
            _vote("a2", "p2", 0.4),
        ]
        result = engine.evaluate(votes, threshold=0.5)
        assert result.proposal_id == "p1"

    def test_default_algorithm_is_weighted_score(self):
        engine = ConsensusEngine()
        assert engine._algorithm == ConsensusAlgorithm.WEIGHTED_SCORE
