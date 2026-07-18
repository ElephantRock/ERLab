"""Tests for negotiation agent — propose, critique, rebut, vote, synthesize."""

import pytest

from backend.pipeline.negotiation.agent import NegotiationAgent
from backend.pipeline.negotiation.protocol import Proposal


class FakeProvider:
    def __init__(self, responses: dict | None = None):
        self._responses = responses or {}
        self._calls: list[dict] = []

    async def complete(self, messages, temperature=0.7, max_tokens=4096) -> str:
        return "test"

    async def complete_stream(self, messages, temperature=0.7, max_tokens=4096):
        yield "test"

    async def structured_output(self, messages, schema, temperature=0.3) -> dict:
        self._calls.append({"messages": messages, "schema": schema})
        return self._responses.get("structured_output", {
            "proposal": "Generated proposal",
            "reasoning": "Test reasoning",
            "critique": "Test critique",
            "severity": "medium",
            "scores": {},
            "synthesized_proposal": "Synthesized",
        })

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def default_model(self) -> str:
        return "fake-model"


class TestNegotiationAgent:
    @pytest.mark.anyio
    async def test_propose(self):
        provider = FakeProvider(responses={"structured_output": {"proposal": "New idea", "reasoning": "Because"}})
        agent = NegotiationAgent("agent_1", provider)
        proposal = await agent.propose("test topic")
        assert proposal.content == "New idea"
        assert proposal.proposer_id == "agent_1"

    @pytest.mark.anyio
    async def test_propose_with_prior(self):
        provider = FakeProvider()
        agent = NegotiationAgent("agent_1", provider)
        prior = Proposal(id="p0", content="Old idea", proposer_id="other")
        proposal = await agent.propose("topic", prior_proposals=[prior])
        assert proposal.proposer_id == "agent_1"

    @pytest.mark.anyio
    async def test_critique(self):
        provider = FakeProvider(responses={"structured_output": {"critique": "Weak method", "severity": "high"}})
        agent = NegotiationAgent("agent_1", provider)
        proposal = Proposal(id="p1", content="Test", proposer_id="other")
        critique = await agent.critique(proposal)
        assert "Weak" in critique

    @pytest.mark.anyio
    async def test_rebut(self):
        provider = FakeProvider(responses={"structured_output": {"proposal": "Improved version", "reasoning": "Better"}})
        agent = NegotiationAgent("agent_1", provider)
        proposal = Proposal(id="p1", content="Original", proposer_id="agent_1")
        rebuttal = await agent.rebut(proposal, "Not novel enough")
        assert rebuttal == "Improved version"

    @pytest.mark.anyio
    async def test_vote(self):
        provider = FakeProvider(responses={"structured_output": {
            "scores": {"p1": 0.9, "p2": 0.5},
            "reasoning": "p1 is stronger",
        }})
        agent = NegotiationAgent("agent_1", provider)
        proposals = [
            Proposal(id="p1", content="Idea 1", proposer_id="a"),
            Proposal(id="p2", content="Idea 2", proposer_id="b"),
        ]
        votes = await agent.vote(proposals)
        assert len(votes) == 2
        assert votes[0].proposal_id == "p1"
        assert votes[0].score == 0.9
        assert votes[1].score == 0.5

    @pytest.mark.anyio
    async def test_vote_clamps_scores(self):
        provider = FakeProvider(responses={"structured_output": {
            "scores": {"p1": 1.5, "p2": -0.3},
            "reasoning": "test",
        }})
        agent = NegotiationAgent("agent_1", provider)
        proposals = [
            Proposal(id="p1", content="A", proposer_id="x"),
            Proposal(id="p2", content="B", proposer_id="y"),
        ]
        votes = await agent.vote(proposals)
        assert votes[0].score == 1.0
        assert votes[1].score == 0.0

    @pytest.mark.anyio
    async def test_synthesize(self):
        provider = FakeProvider(responses={"structured_output": {
            "synthesized_proposal": "Merged idea",
            "reasoning": "Best of both",
        }})
        agent = NegotiationAgent("agent_1", provider)
        proposals = [Proposal(id="p1", content="A", proposer_id="x")]
        result = await agent.synthesize(proposals, ["critique 1"])
        assert result.content == "Merged idea"

    @pytest.mark.anyio
    async def test_agent_capabilities(self):
        agent = NegotiationAgent("a1", FakeProvider(), capabilities=["propose", "vote"])
        assert "propose" in agent.capabilities
        assert "critique" not in agent.capabilities

    @pytest.mark.anyio
    async def test_agent_role(self):
        agent = NegotiationAgent("a1", FakeProvider(), role="mediator")
        assert agent.role == "mediator"

    @pytest.mark.anyio
    async def test_vote_with_missing_score(self):
        provider = FakeProvider(responses={"structured_output": {
            "scores": {"p1": 0.8},
            "reasoning": "test",
        }})
        agent = NegotiationAgent("a1", provider)
        proposals = [
            Proposal(id="p1", content="A", proposer_id="x"),
            Proposal(id="p2", content="B", proposer_id="y"),
        ]
        votes = await agent.vote(proposals)
        assert len(votes) == 2
        assert votes[1].score == 0.5  # default for missing score
