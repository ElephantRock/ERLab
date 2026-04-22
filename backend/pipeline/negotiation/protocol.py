"""Negotiation protocol models — phases, proposals, votes, and config."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class NegotiationPhase(str, Enum):
    PROPOSAL = "proposal"
    CRITIQUE = "critique"
    REBUTTAL = "rebuttal"
    VOTE = "vote"
    CONSENSUS = "consensus"
    DEADLOCK = "deadlock"


class NegotiationMessage(BaseModel):
    phase: NegotiationPhase
    sender_id: str
    content: str
    proposal_id: str | None = None
    metadata: dict = Field(default_factory=dict)


class Proposal(BaseModel):
    id: str
    content: str
    proposer_id: str
    round_num: int = 1
    score: float = 0.0


class Vote(BaseModel):
    voter_id: str
    proposal_id: str
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""


class ConsensusResult(BaseModel):
    proposal_id: str | None = None
    consensus_score: float = 0.0
    votes: list[Vote] = Field(default_factory=list)
    round_num: int = 0
    is_consensus: bool = False
    is_deadlock: bool = False


class NegotiationConfig(BaseModel):
    max_rounds: int = 5
    consensus_threshold: float = 0.7
    min_voters: int = 2
    deadlock_threshold: float = 0.02
    proposal_timeout: float = 60.0
    critique_timeout: float = 30.0
