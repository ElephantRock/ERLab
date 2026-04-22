"""Tests for NEGOTIATE node type and DAG execution."""

import pytest

from backend.pipeline.generation.dag_executor import DAGExecutor
from backend.pipeline.generation.topology import DAGNode, DAGEdge, ExecutionDAG, NodeType


class FakeProvider:
    def __init__(self):
        self._calls: list[dict] = []

    async def complete(self, messages, temperature=0.7, max_tokens=4096) -> str:
        return "test"

    async def complete_stream(self, messages, temperature=0.7, max_tokens=4096):
        yield "test"

    async def structured_output(self, messages, schema, temperature=0.3) -> dict:
        self._calls.append({"messages": messages, "schema": schema})
        return {
            "proposal": "Negotiated outcome",
            "reasoning": "consensus",
            "scores": {"p_a": 0.9},
            "critique": "ok",
            "synthesized_proposal": "merged",
        }

    async def embed(self, texts) -> list[list[float]]:
        return [[0.1] * 10 for _ in texts]

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def default_model(self) -> str:
        return "fake-model"


class TestNegotiationDAG:
    def test_negotiate_node_type_exists(self):
        assert NodeType.NEGOTIATE.value == "negotiate"

    def test_negotiate_node_in_dag(self):
        node = DAGNode(id="neg1", node_type=NodeType.NEGOTIATE, config={"topic": "test", "agents": ["a1", "a2"]})
        dag = ExecutionDAG(
            nodes=[
                DAGNode(id="entry", node_type=NodeType.MAP),
                node,
                DAGNode(id="exit", node_type=NodeType.GATE),
            ],
            edges=[
                DAGEdge(from_node="entry", to_node="neg1"),
                DAGEdge(from_node="neg1", to_node="exit"),
            ],
            entry_node="entry",
        )
        neg_nodes = [n for n in dag.nodes if n.node_type == NodeType.NEGOTIATE]
        assert len(neg_nodes) == 1
        assert neg_nodes[0].config["topic"] == "test"

    @pytest.mark.anyio
    async def test_execute_negotiate_node(self):
        provider = FakeProvider()
        node = DAGNode(
            id="neg1",
            node_type=NodeType.NEGOTIATE,
            config={"topic": "Research direction", "agents": ["agent_a", "agent_b"]},
        )
        dag = ExecutionDAG(
            nodes=[
                DAGNode(id="entry", node_type=NodeType.MAP),
                node,
                DAGNode(id="exit", node_type=NodeType.GATE),
            ],
            edges=[
                DAGEdge(from_node="entry", to_node="neg1"),
                DAGEdge(from_node="neg1", to_node="exit"),
            ],
        )
        executor = DAGExecutor(dag, provider=provider)
        result = await executor._execute_negotiate(node, [{"topic": "test"}])
        assert isinstance(result, list)

    @pytest.mark.anyio
    async def test_execute_negotiate_fallback_on_error(self):
        provider = FakeProvider()
        node = DAGNode(
            id="neg_fail",
            node_type=NodeType.NEGOTIATE,
            config={"agents": []},  # No agents -> returns inputs
        )
        dag = ExecutionDAG(nodes=[node], edges=[])
        executor = DAGExecutor(dag, provider=provider)
        result = await executor._execute_negotiate(node, ["input_data"])
        assert result == ["input_data"]

    @pytest.mark.anyio
    async def test_execute_negotiate_no_topic_uses_input(self):
        provider = FakeProvider()
        node = DAGNode(
            id="neg_notopic",
            node_type=NodeType.NEGOTIATE,
            config={"agents": ["a1", "a2"]},
        )
        dag = ExecutionDAG(nodes=[node], edges=[])
        executor = DAGExecutor(dag, provider=provider)
        result = await executor._execute_negotiate(node, [{"some": "data"}])
        assert isinstance(result, list)
