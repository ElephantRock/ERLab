"""Tests for DAG activation: ROUTE, conditional branching, and full execution."""

import asyncio

from backend.pipeline.agents.message_bus import AgentMessage, MessageBus
from backend.pipeline.agents.registry import AgentRegistry
from backend.pipeline.gap_analysis.models import ResearchGap
from backend.pipeline.generation.dag_executor import DAGExecutor
from backend.pipeline.generation.topology import (
    DAGEdge,
    DAGNode,
    ExecutionDAG,
    NodeType,
)


def _make_gap(title: str, desc: str = "Desc") -> ResearchGap:
    return ResearchGap(title=title, description=desc, gap_type="test", confidence=0.5)


class TestRouteNode:
    def test_route_classifies_via_provider(self, fake_provider):
        """ROUTE node should call the provider to classify items."""
        fake_provider._responses["structured_output"] = {
            "complexity": "simple",
            "reason": "narrow gap",
        }

        dag = ExecutionDAG(
            entry_node="route",
            nodes=[DAGNode(id="route", node_type=NodeType.ROUTE, config={})],
            edges=[],
        )
        bus = MessageBus()
        registry = AgentRegistry(bus)
        executor = DAGExecutor(dag, registry=registry, provider=fake_provider)

        gap = _make_gap("Simple gap")
        results = asyncio.run(executor.execute([{"title": gap.title, "description": gap.description}]))
        assert len(results) == 1
        assert results[0].get("_route") == "simple"

    def test_route_without_provider_defaults_complex(self):
        """ROUTE node without provider should default to 'complex'."""
        dag = ExecutionDAG(
            entry_node="route",
            nodes=[DAGNode(id="route", node_type=NodeType.ROUTE, config={})],
            edges=[],
        )
        bus = MessageBus()
        registry = AgentRegistry(bus)
        executor = DAGExecutor(dag, registry=registry, provider=None)

        results = asyncio.run(executor.execute([_make_gap("Any gap")]))
        assert len(results) == 1
        assert getattr(results[0], "_route", None) == "complex"

    def test_route_on_dict_items(self, fake_provider):
        """ROUTE should annotate dict items with _route."""
        fake_provider._responses["structured_output"] = {
            "complexity": "complex",
            "reason": "broad scope",
        }

        dag = ExecutionDAG(
            entry_node="route",
            nodes=[DAGNode(id="route", node_type=NodeType.ROUTE, config={})],
            edges=[],
        )
        bus = MessageBus()
        registry = AgentRegistry(bus)
        executor = DAGExecutor(dag, registry=registry, provider=fake_provider)

        results = asyncio.run(executor.execute([{"title": "X", "description": "Y"}]))
        assert results[0]["_route"] == "complex"


class TestSwitchNode:
    def test_switch_tags_items(self):
        """SWITCH node should tag items with _route based on config key."""
        dag = ExecutionDAG(
            entry_node="sw",
            nodes=[
                DAGNode(
                    id="sw",
                    node_type=NodeType.SWITCH,
                    config={"condition_key": "type"},
                )
            ],
            edges=[],
        )
        executor = DAGExecutor(dag)

        results = asyncio.run(executor.execute([{"type": "fast"}, {"type": "slow"}]))
        assert results[0]["_route"] == "fast"
        assert results[1]["_route"] == "slow"


class TestConditionalBranching:
    def test_conditional_branches_route_correctly(self):
        """Items with _route labels should only reach matching conditional successors."""
        dag = ExecutionDAG(
            entry_node="route",
            nodes=[
                DAGNode(id="route", node_type=NodeType.ROUTE, config={}),
                DAGNode(id="simple", node_type=NodeType.MAP, config={}),
                DAGNode(id="complex", node_type=NodeType.MAP, config={}),
                DAGNode(id="merge", node_type=NodeType.MERGE, config={}),
            ],
            edges=[
                DAGEdge(from_node="route", to_node="simple", condition="simple"),
                DAGEdge(from_node="route", to_node="complex", condition="complex"),
                DAGEdge(from_node="simple", to_node="merge"),
                DAGEdge(from_node="complex", to_node="merge"),
            ],
        )
        bus = MessageBus()
        registry = AgentRegistry(bus)
        executor = DAGExecutor(dag, registry=registry)

        # Pre-routed items (no LLM needed)
        simple_item = {"title": "Simple", "_route": "simple"}
        complex_item = {"title": "Complex", "_route": "complex"}
        results = asyncio.run(executor.execute([simple_item, complex_item]))

        # MERGE should have both items
        assert len(results) == 2

    def test_non_conditional_edges_get_all_outputs(self):
        """Edges without conditions should receive all predecessor outputs."""
        dag = ExecutionDAG(
            entry_node="entry",
            nodes=[
                DAGNode(id="entry", node_type=NodeType.MAP, config={}),
                DAGNode(id="gate", node_type=NodeType.GATE, config={"min_score": 0}),
            ],
            edges=[DAGEdge(from_node="entry", to_node="gate")],
        )
        bus = MessageBus()
        registry = AgentRegistry(bus)
        executor = DAGExecutor(dag, registry=registry)

        results = asyncio.run(executor.execute([{"item": 1}, {"item": 2}]))
        assert len(results) == 2


class TestLoopNodeMultiAgent:
    def test_loop_runs_configured_agents(self):
        """LOOP with config.agents should run each agent per iteration."""
        call_log = []

        async def mock_handler(msg: AgentMessage) -> None:
            call_log.append(msg.message_type)
            msg.metadata["response"] = [{"title": "idea", "score": 0.5}]

        bus = MessageBus()
        registry = AgentRegistry(bus)
        registry.register("mock_ideator", ["ideator"], handler=mock_handler)
        registry.register("mock_critic", ["critic"], handler=mock_handler)
        registry.register("mock_refiner", ["refiner"], handler=mock_handler)

        dag = ExecutionDAG(
            entry_node="loop",
            nodes=[
                DAGNode(
                    id="loop",
                    node_type=NodeType.LOOP,
                    config={"agents": ["ideator", "critic", "refiner"], "max_iters": 1},
                )
            ],
            edges=[],
        )
        executor = DAGExecutor(dag, registry=registry)

        results = asyncio.run(executor.execute([{"gap": "test"}]))
        # Should have called ideator, critic, refiner once each
        assert "ideator" in call_log
        assert "critic" in call_log
        assert "refiner" in call_log

    def test_loop_with_no_agents_falls_back(self):
        """LOOP without config.agents should use single-agent mode."""
        call_count = [0]

        async def handler(msg: AgentMessage) -> None:
            call_count[0] += 1
            msg.metadata["response"] = msg.payload

        bus = MessageBus()
        registry = AgentRegistry(bus)
        registry.register("agent", ["agent"], handler=handler)

        dag = ExecutionDAG(
            entry_node="loop",
            nodes=[
                DAGNode(
                    id="loop",
                    node_type=NodeType.LOOP,
                    agent_name="agent",
                    config={"max_iters": 2},
                )
            ],
            edges=[],
        )
        executor = DAGExecutor(dag, registry=registry)

        asyncio.run(executor.execute([{"data": 1}]))
        # 1 item × 2 iterations = 2 calls
        assert call_count[0] == 2


class TestDAGExecutorBackwardCompat:
    def test_existing_gate_and_merge_still_work(self):
        """GATE + MERGE nodes should work as before."""
        dag = ExecutionDAG(
            entry_node="gate",
            nodes=[
                DAGNode(id="gate", node_type=NodeType.GATE, config={"min_score": 0.5, "top_n": 2}),
                DAGNode(id="merge", node_type=NodeType.MERGE, config={}),
            ],
            edges=[DAGEdge(from_node="gate", to_node="merge")],
        )
        executor = DAGExecutor(dag)

        class Scored:
            def __init__(self, s):
                self.score = s
                self.title = f"item_{s}"

        results = asyncio.run(executor.execute([Scored(0.3), Scored(0.7), Scored(0.9)]))
        scores = [r.score for r in results]
        assert 0.7 in scores
        assert 0.9 in scores
        assert 0.3 not in scores

    def test_empty_dag(self):
        """Empty DAG should return empty list."""
        dag = ExecutionDAG(entry_node="x", nodes=[], edges=[])
        executor = DAGExecutor(dag)
        results = asyncio.run(executor.execute([]))
        assert results == []

    def test_no_handler_passthrough(self):
        """Nodes without registered agents should pass through."""
        dag = ExecutionDAG(
            entry_node="map",
            nodes=[DAGNode(id="map", node_type=NodeType.MAP, agent_name="nonexistent")],
            edges=[],
        )
        bus = MessageBus()
        registry = AgentRegistry(bus)
        executor = DAGExecutor(dag, registry=registry)

        results = asyncio.run(executor.execute([{"data": 1}]))
        assert len(results) == 1
        assert results[0]["data"] == 1
