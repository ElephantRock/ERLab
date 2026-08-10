"""Tests for negotiation protocol models."""


from backend.pipeline.negotiation.protocol import (
    ConsensusResult,
    NegotiationConfig,
    NegotiationMessage,
    NegotiationPhase,
    Proposal,
    Vote,
)


class TestProtocolModels:
    def test_negotiation_phase_enum(self):
        assert NegotiationPhase.PROPOSAL.value == "proposal"
        assert NegotiationPhase.CRITIQUE.value == "critique"
        assert NegotiationPhase.REBUTTAL.value == "rebuttal"
        assert NegotiationPhase.VOTE.value == "vote"
        assert NegotiationPhase.CONSENSUS.value == "consensus"
        assert NegotiationPhase.DEADLOCK.value == "deadlock"

    def test_proposal_model(self):
        p = Proposal(id="p1", content="Test proposal", proposer_id="agent_1", round_num=2, score=0.8)
        assert p.id == "p1"
        assert p.round_num == 2
        assert p.score == 0.8

    def test_vote_model(self):
        v = Vote(voter_id="a1", proposal_id="p1", score=0.9, reasoning="Strong")
        assert v.score == 0.9
        assert v.reasoning == "Strong"

    def test_vote_score_bounds(self):
        v = Vote(voter_id="a1", proposal_id="p1", score=1.0)
        assert v.score == 1.0
        v2 = Vote(voter_id="a1", proposal_id="p1", score=0.0)
        assert v2.score == 0.0

    def test_negotiation_config_defaults(self):
        config = NegotiationConfig()
        assert config.max_rounds == 5
        assert config.consensus_threshold == 0.7
        assert config.min_voters == 2
        assert config.deadlock_threshold == 0.02

    def test_negotiation_config_custom(self):
        config = NegotiationConfig(max_rounds=3, consensus_threshold=0.9)
        assert config.max_rounds == 3
        assert config.consensus_threshold == 0.9

    def test_negotiation_message(self):
        msg = NegotiationMessage(
            phase=NegotiationPhase.PROPOSAL,
            sender_id="agent_1",
            content="Hello",
            proposal_id="p1",
        )
        assert msg.phase == NegotiationPhase.PROPOSAL
        assert msg.proposal_id == "p1"

    def test_consensus_result_defaults(self):
        result = ConsensusResult()
        assert result.is_consensus is False
        assert result.is_deadlock is False
        assert result.votes == []

    def test_consensus_result_consensus(self):
        result = ConsensusResult(proposal_id="p1", consensus_score=0.85, is_consensus=True)
        assert result.is_consensus is True
