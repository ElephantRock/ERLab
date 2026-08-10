"""Negotiation agent — propose, critique, rebut, vote capabilities."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from backend.pipeline.negotiation.protocol import Proposal, Vote

if TYPE_CHECKING:
    from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

_PROPOSE_SCHEMA = {
    "type": "object",
    "properties": {
        "proposal": {"type": "string"},
        "reasoning": {"type": "string"},
    },
    "required": ["proposal", "reasoning"],
}

_CRITIQUE_SCHEMA = {
    "type": "object",
    "properties": {
        "critique": {"type": "string"},
        "severity": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["critique"],
}

_VOTE_SCHEMA = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "object",
            "additionalProperties": {"type": "number"},
        },
        "reasoning": {"type": "string"},
    },
    "required": ["scores", "reasoning"],
}

_SYNTHESIZE_SCHEMA = {
    "type": "object",
    "properties": {
        "synthesized_proposal": {"type": "string"},
        "reasoning": {"type": "string"},
    },
    "required": ["synthesized_proposal", "reasoning"],
}


class NegotiationAgent:
    """Agent that can propose, critique, rebut, and vote in a negotiation."""

    def __init__(
        self,
        agent_id: str,
        provider: LLMProvider,
        capabilities: list[str] | None = None,
        role: str = "agent",
    ) -> None:
        self.agent_id = agent_id
        self._provider = provider
        self.capabilities = capabilities or ["propose", "critique", "rebut", "vote"]
        self.role = role

    async def propose(
        self,
        topic: str,
        context: str = "",
        prior_proposals: list[Proposal] | None = None,
    ) -> Proposal:
        prior_text = ""
        if prior_proposals:
            prior_text = "\n".join(f"- {p.content}" for p in prior_proposals)

        messages = [
            {"role": "system", "content": f"You are a {self.role} in a negotiation. Generate a proposal."},
            {"role": "user", "content": f"Topic: {topic}\nContext: {context}\nPrior proposals:\n{prior_text}\n\nGenerate a new proposal."},
        ]
        result = await self._provider.structured_output(messages, _PROPOSE_SCHEMA)
        proposal_text = result.get("proposal", "No proposal generated")

        return Proposal(
            id=str(uuid.uuid4())[:8],
            content=proposal_text,
            proposer_id=self.agent_id,
        )

    async def critique(self, proposal: Proposal, context: str = "") -> str:
        messages = [
            {"role": "system", "content": f"You are a {self.role}. Critically evaluate this proposal."},
            {"role": "user", "content": f"Proposal: {proposal.content}\nContext: {context}\n\nProvide critique."},
        ]
        result = await self._provider.structured_output(messages, _CRITIQUE_SCHEMA)
        return result.get("critique", "No critique provided")

    async def rebut(self, proposal: Proposal, critique: str, context: str = "") -> str:
        messages = [
            {"role": "system", "content": f"You are a {self.role}. Defend or revise the proposal against critique."},
            {"role": "user", "content": f"Proposal: {proposal.content}\nCritique: {critique}\nContext: {context}\n\nProvide rebuttal."},
        ]
        result = await self._provider.structured_output(messages, _PROPOSE_SCHEMA)
        return result.get("proposal", result.get("reasoning", "No rebuttal"))

    async def vote(self, proposals: list[Proposal], context: str = "") -> list[Vote]:
        proposal_list = "\n".join(f"[{p.id}] {p.content}" for p in proposals)

        messages = [
            {"role": "system", "content": f"You are a {self.role}. Score each proposal from 0.0 to 1.0."},
            {"role": "user", "content": f"Proposals:\n{proposal_list}\nContext: {context}\n\nScore each proposal."},
        ]
        result = await self._provider.structured_output(messages, _VOTE_SCHEMA)
        scores = result.get("scores", {})
        reasoning = result.get("reasoning", "")

        votes: list[Vote] = []
        for p in proposals:
            score = scores.get(p.id, 0.5)
            try:
                score = float(score)
            except (TypeError, ValueError):
                score = 0.5
            score = max(0.0, min(1.0, score))
            votes.append(Vote(
                voter_id=self.agent_id,
                proposal_id=p.id,
                score=score,
                reasoning=reasoning,
            ))
        return votes

    async def synthesize(self, proposals: list[Proposal], critiques: list[str]) -> Proposal:
        prop_text = "\n".join(f"[{p.id}] {p.content}" for p in proposals)
        crit_text = "\n".join(f"- {c}" for c in critiques)

        messages = [
            {"role": "system", "content": "Synthesize the best elements of competing proposals."},
            {"role": "user", "content": f"Proposals:\n{prop_text}\n\nCritiques:\n{crit_text}\n\nCreate a merged proposal."},
        ]
        result = await self._provider.structured_output(messages, _SYNTHESIZE_SCHEMA)
        return Proposal(
            id=str(uuid.uuid4())[:8],
            content=result.get("synthesized_proposal", "No synthesis"),
            proposer_id=self.agent_id,
        )
