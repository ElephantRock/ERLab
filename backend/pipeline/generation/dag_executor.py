"""DAG executor for TopologyDAG traversal.

Executes the already-defined ExecutionDAG by traversing nodes in topological
order. Supports MAP (parallel fan-out), MERGE (fan-in), LOOP (iterative),
SWITCH (conditional routing), ROUTE (LLM-based strategy), and GATE (quality gate).

Reference: agentscope MsgHub pub-sub broadcasting mapped to TopologyDAG.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from backend.pipeline.agents.message_bus import AgentMessage, MessageBus
from backend.pipeline.agents.registry import AgentRegistry
from backend.pipeline.generation.topology import DAGNode, ExecutionDAG, NodeType

logger = logging.getLogger(__name__)

# Type for node execution functions
NodeExecutor = Callable[[DAGNode, list[Any]], Coroutine[Any, Any, list[Any]]]


def _get_route(item: Any) -> str | None:
    """Extract route label from an annotated item."""
    if isinstance(item, dict):
        return item.get("_route")
    return getattr(item, "_route", None)


def _has_routed_output(output: list[Any]) -> bool:
    """Check if any item in the output has route annotations."""
    return any(_get_route(item) is not None for item in output)


class DAGExecutor:
    """Executes an ExecutionDAG by traversing nodes in topological order."""

    def __init__(
        self,
        dag: ExecutionDAG,
        registry: AgentRegistry | None = None,
        bus: MessageBus | None = None,
        provider: Any | None = None,
    ):
        self._dag = dag
        self._registry = registry
        self._bus = bus
        self._provider = provider
        self._executors: dict[NodeType, NodeExecutor] = {
            NodeType.MAP: self._execute_map,
            NodeType.MERGE: self._execute_merge,
            NodeType.LOOP: self._execute_loop,
            NodeType.SWITCH: self._execute_switch,
            NodeType.ROUTE: self._execute_route,
            NodeType.GATE: self._execute_gate,
            NodeType.HANDOFF: self._execute_handoff,
            NodeType.NEGOTIATE: self._execute_negotiate,
        }
        # Custom executor overrides keyed by node id
        self._custom_executors: dict[str, NodeExecutor] = {}

    def register_executor(self, node_id: str, executor: NodeExecutor) -> None:
        """Register a custom executor for a specific node."""
        self._custom_executors[node_id] = executor

    async def execute(self, initial_input: list[Any]) -> list[Any]:
        """Execute the DAG from entry node, returning final results.

        Supports conditional branching: when a ROUTE node annotates items
        with ``_route`` labels, downstream edges with ``condition`` values
        only receive matching items.
        """
        order = self._topological_sort()

        # Track outputs per node, keyed by condition label
        # node_outputs[node_id]["_all"] = all outputs
        # node_outputs[node_id]["simple"] = items routed as "simple", etc.
        node_outputs: dict[str, dict[str, list[Any]]] = {}
        current_data = initial_input

        for node in order:
            # Gather inputs from predecessor nodes
            inputs = self._gather_inputs(node.id, node_outputs, current_data)

            # Execute node
            if node.id in self._custom_executors:
                output = await self._custom_executors[node.id](node, inputs)
            else:
                executor = self._executors.get(node.node_type)
                if executor:
                    output = await executor(node, inputs)
                else:
                    logger.warning(
                        "No executor for node type %s, passing through",
                        node.node_type,
                    )
                    output = inputs

            node_outputs[node.id] = {"_all": output}

            # If outputs have route annotations, partition by condition
            if output and _has_routed_output(output):
                for edge in self._dag.edges:
                    if edge.from_node == node.id and edge.condition:
                        matching = [
                            item for item in output if _get_route(item) == edge.condition
                        ]
                        node_outputs[node.id][edge.condition] = matching

            logger.info(
                "DAG node '%s' (%s): %d inputs -> %d outputs",
                node.id,
                node.node_type.value,
                len(inputs),
                len(output),
            )

        # Return output from the last node in topological order
        last_node = order[-1] if order else None
        if last_node:
            return node_outputs.get(last_node.id, {}).get("_all", [])
        return []

    def _gather_inputs(
        self,
        node_id: str,
        node_outputs: dict[str, dict[str, list[Any]]],
        current_data: list[Any],
    ) -> list[Any]:
        """Gather inputs for a node, respecting conditional edges."""
        preds = self._get_predecessors(node_id)
        if not preds:
            return current_data

        # Check if any incoming edge has a condition
        incoming_conditions = [
            e.condition
            for e in self._dag.edges
            if e.to_node == node_id and e.condition
        ]

        if not incoming_conditions:
            # No conditions — collect all predecessor outputs
            inputs: list[Any] = []
            for pred_id in preds:
                inputs.extend(node_outputs.get(pred_id, {}).get("_all", []))
            return inputs

        # Conditional — only collect matching items from predecessors
        inputs = []
        for edge in self._dag.edges:
            if edge.to_node == node_id and edge.condition:
                pred_data = node_outputs.get(edge.from_node, {})
                # Use condition-partitioned data if available
                if edge.condition in pred_data:
                    inputs.extend(pred_data[edge.condition])
                else:
                    # Fallback: try all data (for nodes upstream of ROUTE)
                    inputs.extend(pred_data.get("_all", []))
        return inputs

    # ── Node Executors ──────────────────────────────────────────

    async def _execute_map(self, node: DAGNode, inputs: list[Any]) -> list[Any]:
        """MAP: fan-out — process each input in parallel."""
        if not inputs:
            return []

        tasks = [self._invoke_agent(node, item) for item in inputs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        outputs = []
        for r in results:
            if isinstance(r, Exception):
                logger.error("MAP node '%s' task failed: %s", node.id, r)
            elif isinstance(r, list):
                outputs.extend(r)
            else:
                outputs.append(r)
        return outputs

    async def _execute_merge(self, node: DAGNode, inputs: list[Any]) -> list[Any]:
        """MERGE: fan-in — collect and deduplicate."""
        seen = set()
        merged = []
        for item in inputs:
            key = str(item) if not isinstance(item, dict) else str(sorted(item.items()))
            if key not in seen:
                seen.add(key)
                merged.append(item)
        return merged

    async def _execute_loop(self, node: DAGNode, inputs: list[Any]) -> list[Any]:
        """LOOP: iterative multi-agent refinement cycle.

        Supports two modes:
        - Standard: config["agents"] for sequential multi-agent cycles
        - Tree-of-Thought: config["use_tree_of_thought"] = True for beam search

        Reads config["agents"] (e.g., ["ideator", "critic", "refiner"])
        and runs them in sequence per iteration. Accumulates critiques
        between iterations for the refiner.
        """
        # Tree-of-Thought mode
        if node.config.get("use_tree_of_thought", False):
            return await self._execute_tot_loop(node, inputs)

        max_iters = node.config.get("max_iters", 3)
        agent_names = node.config.get("agents", [])
        current = inputs
        accumulated_critiques: list[Any] = []

        for iteration in range(max_iters):
            if not agent_names:
                # Single-agent loop (original behavior)
                tasks = [self._invoke_agent(node, item) for item in current]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                next_input = self._flatten_results(results)
            else:
                # Multi-agent cycle: run each agent in sequence
                next_input = await self._run_agent_cycle(
                    node, agent_names, current, accumulated_critiques, iteration
                )

            if not next_input:
                break

            current = next_input
            logger.info(
                "LOOP node '%s' iteration %d/%d: %d items",
                node.id,
                iteration + 1,
                max_iters,
                len(current),
            )

        return current

    async def _run_agent_cycle(
        self,
        node: DAGNode,
        agent_names: list[str],
        current: list[Any],
        accumulated_critiques: list[Any],
        iteration: int,
    ) -> list[Any]:
        """Run one iteration of the multi-agent cycle within a LOOP node."""
        intermediate = current

        for agent_name in agent_names:
            # Build payloads for each item
            tasks = []
            for item in intermediate:
                payload = self._build_agent_payload(
                    agent_name, item, accumulated_critiques, iteration
                )
                tasks.append(self._invoke_agent_by_name(agent_name, payload))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            result = self._flatten_results(results)

            # If this was the critic, save the critiques for the refiner
            if agent_name == "critic":
                accumulated_critiques.extend(
                    r for r in result if hasattr(r, "idea_title")
                )

            intermediate = result

        return intermediate

    async def _execute_tot_loop(self, node: DAGNode, inputs: list[Any]) -> list[Any]:
        """Execute a Tree-of-Thought beam search within a LOOP node."""
        from backend.pipeline.generation.tot_adapter import ToTAdapter

        max_depth = node.config.get("tot_max_depth", 3)
        beam_width = node.config.get("tot_beam_width", 2)

        # Get agent instances from the registry
        ideator = self._registry.get("ideator")
        critic = self._registry.get("critic")
        refiner = self._registry.get("refiner")

        if not ideator or not critic:
            logger.warning("ToT requires ideator and critic agents, falling back to standard loop")
            return inputs

        adapter = ToTAdapter(
            ideator=ideator,
            critic=critic,
            refiner=refiner,
            score_threshold=node.config.get("tot_score_threshold", 0.7),
        )

        # Extract gaps and papers from inputs
        gaps = [item for item in inputs if hasattr(item, "title") and hasattr(item, "gap_type")]
        papers = [item for item in inputs if hasattr(item, "abstract") and not hasattr(item, "gap_type")]

        if not gaps:
            logger.warning("ToT: no gaps in inputs, returning raw inputs")
            return inputs

        results = adapter.run_beam_search(
            gaps=gaps,
            context_papers=papers,
            max_depth=max_depth,
            beam_width=beam_width,
        )

        logger.info("ToT produced %d thought nodes", len(results))
        return [node.content for node in results]

    def _build_agent_payload(
        self,
        agent_name: str,
        item: Any,
        critiques: list[Any],
        iteration: int,
    ) -> dict:
        """Build a payload dict for an agent invocation within the LOOP."""
        if isinstance(item, dict):
            payload = dict(item)
        else:
            payload = {"item": item}

        if agent_name == "ideator":
            payload["n_ideas"] = payload.get("n_ideas", 3)
        elif agent_name == "critic":
            payload["ideas"] = payload.get("ideas", [item])
            payload["round_num"] = iteration + 1
        elif agent_name == "refiner":
            payload["ideas"] = payload.get("ideas", [item])
            payload["critiques"] = critiques
            payload["round_num"] = iteration + 1

        return payload

    async def _invoke_agent_by_name(self, agent_name: str, payload: Any) -> Any:
        """Invoke a registered agent by its capability name."""
        if not self._registry:
            return payload

        agents = self._registry.discover(agent_name)
        if not agents:
            return payload

        handler = agents[0].handler
        if not handler:
            return payload

        msg = AgentMessage(
            message_type=agent_name,
            payload=payload,
            sender_id="dag:loop",
            recipient_id=agents[0].agent_id,
        )
        await handler(msg)
        return msg.metadata.get("response", payload)

    async def _execute_switch(self, node: DAGNode, inputs: list[Any]) -> list[Any]:
        """SWITCH: tag items with a route label based on a config key."""
        condition_key = node.config.get("condition_key", "type")
        for item in inputs:
            if isinstance(item, dict):
                item["_route"] = str(item.get(condition_key, "default"))
            else:
                item.__dict__["_route"] = str(
                    getattr(item, condition_key, "default")
                )
        return inputs

    async def _execute_route(self, node: DAGNode, inputs: list[Any]) -> list[Any]:
        """ROUTE: classify each item via LLM and annotate with route label."""
        if not self._provider:
            logger.warning("ROUTE node '%s': no provider, defaulting to 'complex'", node.id)
            for item in inputs:
                if isinstance(item, dict):
                    item["_route"] = "complex"
                else:
                    item.__dict__["_route"] = "complex"
            return inputs

        results = []
        for item in inputs:
            try:
                classification = await self._classify_item(item)
                route_label = classification.get("complexity", "complex")
            except Exception:
                logger.warning("ROUTE classification failed, defaulting to 'complex'")
                route_label = "complex"

            if isinstance(item, dict):
                item["_route"] = route_label
            else:
                item.__dict__["_route"] = route_label
            results.append(item)

        return results

    async def _classify_item(self, item: Any) -> dict:
        """Classify a single item (gap) using the LLM provider."""
        # Extract text for classification
        if isinstance(item, dict):
            title = item.get("title", item.get("gap", {}))
            if hasattr(title, "title"):
                title = title.title
            description = item.get("description", "")
        else:
            title = getattr(item, "title", str(item))
            description = getattr(item, "description", "")

        return await self._provider.structured_output(
            messages=[
                {
                    "role": "user",
                    "content": f"Classify this research gap as simple or complex:\n"
                    f"Title: {title}\nDescription: {description[:500]}",
                }
            ],
            schema={
                "type": "object",
                "properties": {
                    "complexity": {"type": "string", "enum": ["simple", "complex"]},
                    "reason": {"type": "string"},
                },
                "required": ["complexity"],
            },
            temperature=0.1,
        )

    async def _execute_gate(self, node: DAGNode, inputs: list[Any]) -> list[Any]:
        """GATE: quality gate — filter by score threshold."""
        min_score = node.config.get("min_score", 0.3)
        top_n = node.config.get("top_n")

        filtered = [
            item
            for item in inputs
            if hasattr(item, "score") and item.score >= min_score
        ]
        if not filtered:
            filtered = inputs  # If nothing passes, keep all

        if top_n:
            filtered = sorted(
                filtered,
                key=lambda x: getattr(x, "score", 0),
                reverse=True,
            )[:top_n]

        return filtered

    async def _execute_handoff(self, node: DAGNode, inputs: list[Any]) -> list[Any]:
        """HANDOFF: transfer context between agents with configurable input_filter.

        Config keys:
          - filter_type: "last_n" | "summary" | "gap_only" | "none" (default "none")
          - filter_n: number of items to keep for "last_n" filter (default 5)
          - agent_name: target agent to hand off to

        Inspired by OpenAI Agents handoff system with input_filter for context governance.
        """
        filter_type = node.config.get("filter_type", "none")
        filter_n = node.config.get("filter_n", 5)

        # Apply input filter
        if filter_type == "last_n":
            filtered = inputs[-filter_n:] if len(inputs) > filter_n else inputs
        elif filter_type == "gap_only":
            filtered = [
                item for item in inputs
                if isinstance(item, dict) and item.get("type") == "gap"
                or hasattr(item, "gap_type")
            ]
            if not filtered:
                filtered = inputs
        elif filter_type == "summary" and self._provider:
            filtered = await self._summarize_context(inputs, filter_n)
        else:
            filtered = inputs

        # If an agent is specified, invoke it with the filtered context
        if node.agent_name and self._registry:
            agent_name = node.agent_name
            agents = self._registry.discover(agent_name)
            if agents and agents[0].handler:
                msg = AgentMessage(
                    message_type=agent_name,
                    payload=filtered,
                    sender_id=f"dag:{node.id}",
                    recipient_id=agents[0].agent_id,
                )
                await agents[0].handler(msg)
                return msg.metadata.get("response", filtered)

        return filtered

    async def _summarize_context(self, items: list[Any], max_items: int) -> list[Any]:
        """Summarize context items using the LLM provider."""
        if not items or not self._provider:
            return items

        text_items = []
        for item in items[:max_items * 2]:
            if isinstance(item, dict):
                text_items.append(str(item)[:200])
            else:
                text_items.append(str(getattr(item, "title", item))[:200])

        try:
            result = await self._provider.structured_output(
                messages=[{
                    "role": "user",
                    "content": f"Summarize these research context items into {max_items} key points:\n"
                    + "\n".join(f"- {t}" for t in text_items),
                }],
                schema={
                    "type": "object",
                    "properties": {
                        "summaries": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                temperature=0.3,
            )
            summaries = result.get("summaries", [])
            if summaries:
                return [{"type": "summary", "content": s} for s in summaries]
        except Exception as e:
            logger.warning("Context summarization failed: %s", e)

        return items[-max_items:]

    async def _execute_negotiate(self, node: DAGNode, inputs: list[Any]) -> list[Any]:
        """NEGOTIATE: run multi-agent negotiation to reach consensus."""
        config = node.config or {}
        topic = config.get("topic", "")
        context = config.get("context", "")
        if not topic and inputs:
            topic = str(inputs[0])[:200]

        try:
            from backend.pipeline.negotiation.agent import NegotiationAgent
            from backend.pipeline.negotiation.consensus import ConsensusEngine
            from backend.pipeline.negotiation.protocol import NegotiationConfig
            from backend.pipeline.negotiation.session import NegotiationSession

            agent_names = config.get("agents", [])
            agents = []
            for name in agent_names:
                agents.append(NegotiationAgent(
                    agent_id=name,
                    provider=self._provider,
                    role=name,
                ))

            if not agents:
                return inputs

            neg_config = NegotiationConfig(
                max_rounds=config.get("max_rounds", 5),
                consensus_threshold=config.get("consensus_threshold", 0.7),
            )
            engine = ConsensusEngine()
            session = NegotiationSession(
                topic=topic,
                agents=agents,
                config=neg_config,
                consensus_engine=engine,
            )
            result = await session.run(context=context or "")
            if result.proposal_id:
                return [{"proposal_id": result.proposal_id, "consensus": result.is_consensus}]
        except Exception as e:
            logger.warning("Negotiation failed, passing through: %s", e)

        return inputs

    # ── Helpers ─────────────────────────────────────────────────

    async def _invoke_agent(self, node: DAGNode, item: Any) -> Any:
        """Invoke the agent associated with a node via the registry."""
        agent_name = node.agent_name
        if not agent_name or not self._registry:
            return item

        agents = self._registry.discover(agent_name)
        if not agents:
            logger.warning("No agent found for capability '%s'", agent_name)
            return item

        handler = agents[0].handler
        if not handler:
            return item

        msg = AgentMessage(
            message_type=agent_name,
            payload=item,
            sender_id=f"dag:{node.id}",
            recipient_id=agents[0].agent_id,
        )
        await handler(msg)
        return msg.metadata.get("response", item)

    @staticmethod
    def _flatten_results(results: list[Any]) -> list[Any]:
        """Flatten gather results, skipping exceptions."""
        flat = []
        for r in results:
            if isinstance(r, Exception):
                continue
            if isinstance(r, list):
                flat.extend(r)
            else:
                flat.append(r)
        return flat

    def _topological_sort(self) -> list[DAGNode]:
        """Kahn's algorithm for topological sort."""
        node_map = {n.id: n for n in self._dag.nodes}
        in_degree = {n.id: 0 for n in self._dag.nodes}

        for edge in self._dag.edges:
            if edge.to_node in in_degree:
                in_degree[edge.to_node] += 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        order: list[DAGNode] = []

        while queue:
            nid = queue.pop(0)
            if nid in node_map:
                order.append(node_map[nid])
            for edge in self._dag.edges:
                if edge.from_node == nid and edge.to_node in in_degree:
                    in_degree[edge.to_node] -= 1
                    if in_degree[edge.to_node] == 0:
                        queue.append(edge.to_node)

        return order

    def _get_predecessors(self, node_id: str) -> list[str]:
        """Get predecessor node IDs."""
        return [e.from_node for e in self._dag.edges if e.to_node == node_id]
