"""Tests for message bus, agent registry, and DAG executor."""

import asyncio

from backend.pipeline.agents.message_bus import AgentMessage, MessageBus
from backend.pipeline.agents.registry import AgentRegistry


class TestMessageBus:
    def test_publish_subscribe(self):
        asyncio.run(self._test_pubsub())

    async def _test_pubsub(self):
        bus = MessageBus()
        received = []

        async def handler(msg: AgentMessage):
            received.append(msg)

        bus.subscribe("agent_a", "ideation", handler)
        msg = AgentMessage(
            message_type="ideation", payload={"gap": "test gap"}, sender_id="orchestrator"
        )
        count = await bus.publish(msg)

        assert count == 1
        assert len(received) == 1
        assert received[0].payload["gap"] == "test gap"

    def test_broadcast_to_multiple_subscribers(self):
        asyncio.run(self._test_broadcast())

    async def _test_broadcast(self):
        bus = MessageBus()
        received_a, received_b = [], []

        async def handler_a(msg: AgentMessage):
            received_a.append(msg)

        async def handler_b(msg: AgentMessage):
            received_b.append(msg)

        bus.subscribe("agent_a", "critique", handler_a)
        bus.subscribe("agent_b", "critique", handler_b)

        msg = AgentMessage(message_type="critique", payload="review this", sender_id="ideator")
        count = await bus.publish(msg)

        assert count == 2
        assert len(received_a) == 1
        assert len(received_b) == 1

    def test_direct_message(self):
        asyncio.run(self._test_direct())

    async def _test_direct(self):
        bus = MessageBus()
        received_a, received_b = [], []

        async def handler_a(msg: AgentMessage):
            received_a.append(msg)

        async def handler_b(msg: AgentMessage):
            received_b.append(msg)

        bus.subscribe("agent_a", "direct", handler_a)
        bus.subscribe("agent_b", "direct", handler_b)

        msg = AgentMessage(
            message_type="direct",
            payload="private",
            sender_id="orchestrator",
            recipient_id="agent_b",
        )
        await bus.publish(msg)

        assert len(received_a) == 0
        assert len(received_b) == 1

    def test_no_subscribers(self):
        async def _test():
            bus = MessageBus()
            msg = AgentMessage(message_type="unknown_topic", payload="data", sender_id="test")
            count = await bus.publish(msg)
            assert count == 0

        asyncio.run(_test())

    def test_message_history(self):
        asyncio.run(self._test_history())

    async def _test_history(self):
        bus = MessageBus()

        async def noop(msg: AgentMessage):
            pass

        bus.subscribe("a", "test", noop)
        await bus.publish(AgentMessage(message_type="test", payload="msg1", sender_id="x"))
        await bus.publish(AgentMessage(message_type="test", payload="msg2", sender_id="x"))
        await bus.publish(AgentMessage(message_type="other", payload="msg3", sender_id="x"))

        history = bus.get_history(message_type="test")
        assert len(history) == 2

        all_history = bus.get_history()
        assert len(all_history) == 3


class TestAgentRegistry:
    def test_register_and_discover(self):
        registry = AgentRegistry()
        registry.register("ideator", ["ideation", "generation"])
        registry.register("critic", ["critique", "evaluation"])

        agents = registry.discover("ideation")
        assert len(agents) == 1
        assert agents[0].agent_id == "ideator"

    def test_discover_multiple(self):
        registry = AgentRegistry()
        registry.register("a", ["generation", "critique"])
        registry.register("b", ["generation"])

        agents = registry.discover("generation")
        assert len(agents) == 2

    def test_unregister(self):
        registry = AgentRegistry()
        registry.register("a", ["ideation"])
        assert registry.agent_count == 1

        ok = registry.unregister("a")
        assert ok
        assert registry.agent_count == 0
        assert len(registry.discover("ideation")) == 0

    def test_auto_subscribe_to_bus(self):
        bus = MessageBus()

        async def handler(msg: AgentMessage):
            pass

        registry = AgentRegistry(bus)
        registry.register("agent_a", ["ideation"], handler)
        assert bus.subscriber_count == 2  # "ideation" + "direct:agent_a"

    def test_all_capabilities(self):
        registry = AgentRegistry()
        registry.register("a", ["x", "y"])
        registry.register("b", ["y", "z"])

        caps = registry.all_capabilities()
        assert set(caps) == {"x", "y", "z"}


class TestDAGExecutor:
    def test_topological_sort(self):
        from backend.pipeline.generation.dag_executor import DAGExecutor
        from backend.pipeline.generation.topology import build_default_dag

        dag = build_default_dag()
        executor = DAGExecutor(dag)
        order = executor._topological_sort()

        seen = set()
        for node in order:
            preds = executor._get_predecessors(node.id)
            for p in preds:
                assert p in seen, f"Predecessor {p} not seen before {node.id}"
            seen.add(node.id)

        assert len(order) == len(dag.nodes)

    def test_gate_node_filters_by_score(self):
        asyncio.run(self._test_gate())

    async def _test_gate(self):
        from backend.pipeline.generation.dag_executor import DAGExecutor
        from backend.pipeline.generation.models import ResearchIdea
        from backend.pipeline.generation.topology import DAGNode, ExecutionDAG, NodeType

        dag = ExecutionDAG(
            entry_node="gate",
            nodes=[
                DAGNode(id="gate", node_type=NodeType.GATE, config={"min_score": 0.5, "top_n": 2})
            ],
            edges=[],
        )
        executor = DAGExecutor(dag)

        ideas = [
            ResearchIdea(
                title="Low",
                problem_statement="",
                proposed_method="",
                expected_contributions="",
                novelty_rationale="",
                evaluation_approach="",
                score=0.2,
            ),
            ResearchIdea(
                title="High",
                problem_statement="",
                proposed_method="",
                expected_contributions="",
                novelty_rationale="",
                evaluation_approach="",
                score=0.9,
            ),
            ResearchIdea(
                title="Mid",
                problem_statement="",
                proposed_method="",
                expected_contributions="",
                novelty_rationale="",
                evaluation_approach="",
                score=0.6,
            ),
        ]

        result = await executor._execute_gate(dag.nodes[0], ideas)
        assert len(result) == 2
        assert result[0].title == "High"

    def test_merge_node_deduplicates(self):
        asyncio.run(self._test_merge())

    async def _test_merge(self):
        from backend.pipeline.generation.dag_executor import DAGExecutor
        from backend.pipeline.generation.topology import DAGNode, ExecutionDAG, NodeType

        dag = ExecutionDAG(
            entry_node="merge",
            nodes=[DAGNode(id="merge", node_type=NodeType.MERGE)],
            edges=[],
        )
        executor = DAGExecutor(dag)

        inputs = ["a", "b", "a", "c", "b"]
        result = await executor._execute_merge(dag.nodes[0], inputs)
        assert len(result) == 3
