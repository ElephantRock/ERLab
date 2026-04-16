"""DAG execution topology for agent orchestration.

Replaces the fixed sequential Ideator→Critic→Refiner loop with a
programmable DAG supporting MAP (parallel fan-out), SWITCH (conditional
routing), LOOP (iterative refinement), MERGE (fan-in), GATE (quality
gate), and ROUTE (LLM-based strategy selection) node types.
"""

import logging
from enum import Enum

from pydantic import BaseModel

from backend.pipeline.generation.models import ResearchIdea

logger = logging.getLogger(__name__)


class NodeType(str, Enum):
    MAP = "map"        # Parallel fan-out (one gap -> N idea branches)
    SWITCH = "switch"  # Conditional routing (simple vs complex gap)
    LOOP = "loop"      # Iterative refinement (Ideator-Critic-Refiner cycle)
    MERGE = "merge"    # Fan-in (collect results from parallel branches)
    GATE = "gate"      # Quality gate (KeepBestN)
    ROUTE = "route"    # LLM-based router for strategy selection


class DAGNode(BaseModel):
    id: str
    node_type: NodeType
    agent_name: str | None = None   # "ideator", "critic", "refiner", "router"
    config: dict = {}


class DAGEdge(BaseModel):
    from_node: str
    to_node: str
    condition: str | None = None    # For SWITCH edges: "simple" or "complex"


class ExecutionDAG(BaseModel):
    nodes: list[DAGNode]
    edges: list[DAGEdge]
    entry_node: str = "entry"


def keep_best_n(ideas: list[ResearchIdea], n: int, min_score: float = 0.3) -> list[ResearchIdea]:
    """Quality gate: keep top-N ideas above minimum score threshold."""
    filtered = [i for i in ideas if i.score >= min_score]
    return sorted(filtered, key=lambda i: i.score, reverse=True)[:n]


def build_default_dag() -> ExecutionDAG:
    """Build the default research ideation DAG.

    ENTRY -> MAP (fan-out over gaps)
      -> ROUTE (per gap: classify simple vs complex)
        -> simple: fast Ideator -> GATE
        -> complex: LOOP(Ideator->Critic->Refiner) -> GATE
      -> MERGE (collect from all branches)
      -> GATE (global KeepBestN)
      -> EXIT
    """
    return ExecutionDAG(
        entry_node="entry",
        nodes=[
            DAGNode(id="entry", node_type=NodeType.MAP, agent_name=None, config={"fan_out_on": "gaps"}),
            DAGNode(id="route", node_type=NodeType.ROUTE, agent_name="router", config={}),
            DAGNode(id="simple_ideator", node_type=NodeType.MAP, agent_name="ideator",
                    config={"strategy": "react", "temperature": 0.8}),
            DAGNode(id="complex_loop", node_type=NodeType.LOOP, agent_name=None,
                    config={"agents": ["ideator", "critic", "refiner"], "max_iters": 3}),
            DAGNode(id="simple_gate", node_type=NodeType.GATE, config={"min_score": 0.3}),
            DAGNode(id="complex_gate", node_type=NodeType.GATE, config={"min_score": 0.3}),
            DAGNode(id="merge", node_type=NodeType.MERGE, config={}),
            DAGNode(id="final_gate", node_type=NodeType.GATE, config={"min_score": 0.4, "top_n": 10}),
        ],
        edges=[
            DAGEdge(from_node="entry", to_node="route"),
            DAGEdge(from_node="route", to_node="simple_ideator", condition="simple"),
            DAGEdge(from_node="route", to_node="complex_loop", condition="complex"),
            DAGEdge(from_node="simple_ideator", to_node="simple_gate"),
            DAGEdge(from_node="complex_loop", to_node="complex_gate"),
            DAGEdge(from_node="simple_gate", to_node="merge"),
            DAGEdge(from_node="complex_gate", to_node="merge"),
            DAGEdge(from_node="merge", to_node="final_gate"),
        ],
    )
