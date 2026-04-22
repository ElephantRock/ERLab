"""Negotiation session lifecycle — propose, critique, rebut, vote, check consensus."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from backend.pipeline.negotiation.agent import NegotiationAgent
from backend.pipeline.negotiation.consensus import ConsensusEngine
from backend.pipeline.negotiation.protocol import (
    ConsensusResult,
    NegotiationConfig,
    NegotiationMessage,
    NegotiationPhase,
    Proposal,
    Vote,
)

if TYPE_CHECKING:
    from backend.pipeline.agents.message_bus import MessageBus

logger = logging.getLogger(__name__)


class NegotiationSession:
    """Manages a full negotiation lifecycle across multiple agents."""

    def __init__(
        self,
        topic: str,
        agents: list[NegotiationAgent],
        config: NegotiationConfig | None = None,
        consensus_engine: ConsensusEngine | None = None,
        message_bus: MessageBus | None = None,
    ) -> None:
        self._topic = topic
        self._agents = agents
        self._config = config or NegotiationConfig()
        self._engine = consensus_engine or ConsensusEngine()
        self._bus = message_bus
        self._history: list[NegotiationMessage] = []
        self._proposals: list[Proposal] = []
        self._critiques: list[str] = []
        self._round = 0

    async def run(self, context: str = "") -> ConsensusResult:
        for round_num in range(1, self._config.max_rounds + 1):
            self._round = round_num

            proposals = await self._run_proposal_phase(context)
            self._proposals.extend(proposals)

            critiques = await self._run_critique_phase(proposals, context)
            self._critiques.extend(critiques)

            await self._run_rebuttal_phase(proposals, critiques, context)

            votes = await self._run_vote_phase(proposals, context)
            if not votes:
                continue

            result = self._engine.evaluate(votes, self._config.consensus_threshold)
            result.round_num = round_num

            if result.is_consensus:
                logger.info("Consensus reached in round %d (score=%.2f)", round_num, result.consensus_score)
                return result

            if self._check_deadlock(result):
                logger.info("Deadlock detected in round %d, attempting synthesis", round_num)
                synthesis = await self._run_synthesis(proposals, critiques)
                if synthesis:
                    self._proposals.append(synthesis)
                return ConsensusResult(
                    proposal_id=synthesis.id if synthesis else result.proposal_id,
                    consensus_score=result.consensus_score,
                    votes=votes,
                    round_num=round_num,
                    is_deadlock=True,
                )

        logger.info("Max rounds (%d) reached without consensus", self._config.max_rounds)
        return ConsensusResult(
            proposal_id=self._proposals[0].id if self._proposals else None,
            consensus_score=0.0,
            round_num=self._config.max_rounds,
            is_deadlock=True,
        )

    async def _run_proposal_phase(self, context: str) -> list[Proposal]:
        proposals = []
        for agent in self._agents:
            if "propose" in agent.capabilities:
                proposal = await agent.propose(
                    self._topic, context,
                    prior_proposals=self._proposals[-len(self._agents):] if self._proposals else None,
                )
                proposal.round_num = self._round
                proposals.append(proposal)
                self._record(NegotiationPhase.PROPOSAL, agent.agent_id, proposal.content, proposal.id)
        return proposals

    async def _run_critique_phase(self, proposals: list[Proposal], context: str) -> list[str]:
        critiques = []
        for agent in self._agents:
            if "critique" not in agent.capabilities:
                continue
            for proposal in proposals:
                if proposal.proposer_id != agent.agent_id:
                    critique = await agent.critique(proposal, context)
                    critiques.append(critique)
                    self._record(NegotiationPhase.CRITIQUE, agent.agent_id, critique, proposal.id)
        return critiques

    async def _run_rebuttal_phase(self, proposals: list[Proposal], critiques: list[str], context: str) -> None:
        for agent in self._agents:
            if "rebut" not in agent.capabilities:
                continue
            own_proposals = [p for p in proposals if p.proposer_id == agent.agent_id]
            for proposal in own_proposals:
                relevant_critiques = [c for c in critiques if len(c) > 0]
                if relevant_critiques:
                    combined = "; ".join(relevant_critiques[:3])
                    rebuttal = await agent.rebut(proposal, combined, context)
                    self._record(NegotiationPhase.REBUTTAL, agent.agent_id, rebuttal, proposal.id)

    async def _run_vote_phase(self, proposals: list[Proposal], context: str) -> list[Vote]:
        all_votes: list[Vote] = []
        for agent in self._agents:
            if "vote" not in agent.capabilities:
                continue
            votes = await agent.vote(proposals, context)
            all_votes.extend(votes)
            for v in votes:
                self._record(NegotiationPhase.VOTE, agent.agent_id, f"score={v.score}", v.proposal_id)
        return all_votes

    def _check_deadlock(self, result: ConsensusResult) -> bool:
        return result.is_deadlock or (
            len(self._history) >= 4
            and result.consensus_score < self._config.deadlock_threshold
        )

    async def _run_synthesis(self, proposals: list[Proposal], critiques: list[str]) -> Proposal | None:
        synthesizer = next((a for a in self._agents if "propose" in a.capabilities), None)
        if not synthesizer:
            return None
        return await synthesizer.synthesize(proposals, critiques)

    def _record(self, phase: NegotiationPhase, sender: str, content: str, proposal_id: str | None = None) -> None:
        msg = NegotiationMessage(phase=phase, sender_id=sender, content=content, proposal_id=proposal_id)
        self._history.append(msg)
        if self._bus:
            from backend.pipeline.agents.message_bus import AgentMessage
            self._bus.publish(AgentMessage(
                message_type=f"negotiation.{phase.value}",
                payload=msg.model_dump(),
                sender_id=sender,
            ))

    def get_history(self) -> list[NegotiationMessage]:
        return list(self._history)

    def get_results_summary(self) -> dict[str, Any]:
        return {
            "topic": self._topic,
            "rounds": self._round,
            "total_proposals": len(self._proposals),
            "total_critiques": len(self._critiques),
            "agents": [a.agent_id for a in self._agents],
        }
