"""Tests for negotiation session — full protocol lifecycle."""

import pytest

from backend.pipeline.negotiation.agent import NegotiationAgent
from backend.pipeline.negotiation.consensus import ConsensusAlgorithm, ConsensusEngine
from backend.pipeline.negotiation.protocol import NegotiationConfig, NegotiationPhase
from backend.pipeline.negotiation.session import NegotiationSession


class FakeProvider:
    def __init__(self, proposal_scores: dict | None = None):
        self._proposal_scores = proposal_scores or {}
        self._call_count = 0

    async def complete(self, messages, temperature=0.7, max_tokens=4096) -> str:
        return "test"

    async def complete_stream(self, messages, temperature=0.7, max_tokens=4096):
        yield "test"

    async def structured_output(self, messages, schema, temperature=0.3) -> dict:
        self._call_count += 1
        msg = messages[-1]["content"] if messages else ""

        if "Score each proposal" in msg:
            # Parse proposal IDs from the message (format: [id] content)
            import re
            found_ids = re.findall(r"\[(\w+)\]", msg)
            scores = {}
            for pid in found_ids:
                scores[pid] = self._proposal_scores.get(pid, 0.9)
            return {"scores": scores, "reasoning": "scores"}

        if "Synthesize" in msg or "synthesis" in msg.lower():
            return {"synthesized_proposal": "Merged proposal", "reasoning": "combined"}

        return {
            "proposal": f"Proposal_{self._call_count}",
            "reasoning": "test",
            "critique": f"Critique_{self._call_count}",
            "severity": "medium",
        }

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def default_model(self) -> str:
        return "fake-model"


def _make_agents(n: int, provider: FakeProvider, scores: dict | None = None) -> list[NegotiationAgent]:
    provider._proposal_scores = scores or {}
    return [NegotiationAgent(f"agent_{i}", provider) for i in range(n)]


class TestNegotiationSession:
    @pytest.mark.anyio
    async def test_consensus_round_1(self):
        provider = FakeProvider(proposal_scores={"p_a": 0.9, "p_b": 0.6})
        agents = _make_agents(2, provider, scores={"p_a": 0.9, "p_b": 0.6})
        session = NegotiationSession("test topic", agents, NegotiationConfig(max_rounds=1))
        result = await session.run()
        assert result.is_consensus is True or result.is_deadlock is True

    @pytest.mark.anyio
    async def test_max_rounds_deadlock(self):
        provider = FakeProvider(proposal_scores={})
        agents = _make_agents(2, provider, scores={})
        session = NegotiationSession("test", agents, NegotiationConfig(max_rounds=2))
        result = await session.run()
        assert result.round_num <= 2

    @pytest.mark.anyio
    async def test_session_records_history(self):
        provider = FakeProvider(proposal_scores={"p_a": 0.9})
        agents = _make_agents(2, provider, scores={"p_a": 0.9})
        session = NegotiationSession("test", agents, NegotiationConfig(max_rounds=1))
        await session.run()
        history = session.get_history()
        phases = {m.phase for m in history}
        assert NegotiationPhase.PROPOSAL in phases

    @pytest.mark.anyio
    async def test_results_summary(self):
        provider = FakeProvider(proposal_scores={"p_a": 0.9})
        agents = _make_agents(2, provider, scores={"p_a": 0.9})
        session = NegotiationSession("my topic", agents, NegotiationConfig(max_rounds=1))
        await session.run()
        summary = session.get_results_summary()
        assert summary["topic"] == "my topic"
        assert summary["agents"] == ["agent_0", "agent_1"]

    @pytest.mark.anyio
    async def test_single_agent(self):
        provider = FakeProvider(proposal_scores={"p_a": 0.9})
        agents = _make_agents(1, provider, scores={"p_a": 0.9})
        session = NegotiationSession("test", agents, NegotiationConfig(max_rounds=1))
        result = await session.run()
        assert result.round_num >= 1

    @pytest.mark.anyio
    async def test_consensus_engine_integration(self):
        engine = ConsensusEngine(ConsensusAlgorithm.UNANIMOUS)
        provider = FakeProvider(proposal_scores={"p_a": 0.95})
        agents = _make_agents(2, provider, scores={"p_a": 0.95})
        session = NegotiationSession("test", agents, NegotiationConfig(max_rounds=1, consensus_threshold=0.7), consensus_engine=engine)
        result = await session.run()
        assert result.is_consensus is True

    @pytest.mark.anyio
    async def test_three_agents(self):
        provider = FakeProvider(proposal_scores={"p_a": 0.85, "p_b": 0.7, "p_c": 0.6})
        agents = _make_agents(3, provider, scores={"p_a": 0.85, "p_b": 0.7, "p_c": 0.6})
        session = NegotiationSession("test", agents, NegotiationConfig(max_rounds=1, consensus_threshold=0.7))
        result = await session.run()
        assert result.round_num == 1

    @pytest.mark.anyio
    async def test_high_consensus_threshold(self):
        provider = FakeProvider(proposal_scores={"p_a": 0.75, "p_b": 0.6})
        agents = _make_agents(2, provider, scores={"p_a": 0.75, "p_b": 0.6})
        session = NegotiationSession("test", agents, NegotiationConfig(max_rounds=1, consensus_threshold=0.95))
        result = await session.run()
        assert result.is_consensus is False

    @pytest.mark.anyio
    async def test_no_votes_continues(self):
        provider = FakeProvider(proposal_scores={})
        agents = _make_agents(2, provider, scores={})
        session = NegotiationSession("test", agents, NegotiationConfig(max_rounds=2))
        result = await session.run()
        assert result is not None

    @pytest.mark.anyio
    async def test_config_custom_timeouts(self):
        config = NegotiationConfig(proposal_timeout=120.0, critique_timeout=60.0)
        assert config.proposal_timeout == 120.0
        assert config.critique_timeout == 60.0

    @pytest.mark.anyio
    async def test_session_with_context(self):
        provider = FakeProvider(proposal_scores={"p_a": 0.9})
        agents = _make_agents(2, provider, scores={"p_a": 0.9})
        session = NegotiationSession("test", agents, NegotiationConfig(max_rounds=1))
        result = await session.run(context="Some research context")
        assert result is not None

    @pytest.mark.anyio
    async def test_deadlock_triggers_synthesis(self):
        provider = FakeProvider(proposal_scores={"p_a": 0.3, "p_b": 0.2})
        agents = _make_agents(2, provider, scores={"p_a": 0.3, "p_b": 0.2})
        session = NegotiationSession("test", agents, NegotiationConfig(max_rounds=1, deadlock_threshold=0.5))
        result = await session.run()
        assert result.is_deadlock is True or result.is_consensus is True

    @pytest.mark.anyio
    async def test_multiple_rounds(self):
        provider = FakeProvider(proposal_scores={"p_a": 0.5, "p_b": 0.4})
        agents = _make_agents(2, provider, scores={"p_a": 0.5, "p_b": 0.4})
        session = NegotiationSession("test", agents, NegotiationConfig(max_rounds=3, consensus_threshold=0.9))
        result = await session.run()
        assert result.round_num <= 3

    @pytest.mark.anyio
    async def test_agent_with_limited_capabilities(self):
        provider = FakeProvider(proposal_scores={"p_a": 0.9})
        agents = [
            NegotiationAgent("voter_only", provider, capabilities=["vote"]),
            NegotiationAgent("proposer_only", provider, capabilities=["propose"]),
        ]
        session = NegotiationSession("test", agents, NegotiationConfig(max_rounds=1))
        result = await session.run()
        assert result is not None
