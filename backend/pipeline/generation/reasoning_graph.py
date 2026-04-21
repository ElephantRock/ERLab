"""Graph-of-thoughts reasoning for structured idea exploration.

Implements a DAG of ThoughtNodes with operations: Generate, Score,
KeepBestN, Aggregate, Validate. Supports branching and merging of
reasoning paths with configurable beam search width.

Adopted from graph-of-thoughts (DAG-based reasoning), reflexion
(strategy enum + iterative refinement), and BestFirstTreeOfThoughts
(beam search with path pruning).
"""

from __future__ import annotations

import logging
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ThoughtState(str, Enum):
    PROPOSED = "proposed"
    SCORED = "scored"
    VALIDATED = "validated"
    SOLVED = "solved"
    PRUNED = "pruned"


class OperationType(str, Enum):
    GENERATE = "generate"
    SCORE = "score"
    KEEP_BEST_N = "keep_best_n"
    AGGREGATE = "aggregate"
    VALIDATE = "validate"


class ThoughtNode(BaseModel):
    """A single reasoning step in the graph of thoughts."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    content: str
    state: ThoughtState = ThoughtState.PROPOSED
    score: float = 0.0
    parent_ids: list[str] = Field(default_factory=list)
    child_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def add_child(self, child_id: str) -> None:
        if child_id not in self.child_ids:
            self.child_ids.append(child_id)

    def add_parent(self, parent_id: str) -> None:
        if parent_id not in self.parent_ids:
            self.parent_ids.append(parent_id)


class Operation(BaseModel):
    """A graph operation that transforms thought nodes."""

    type: OperationType
    config: dict[str, Any] = Field(default_factory=dict)


class ReasoningGraph(BaseModel):
    """DAG of ThoughtNodes with branching and merging paths."""

    nodes: dict[str, ThoughtNode] = Field(default_factory=dict)
    root_ids: list[str] = Field(default_factory=list)
    operations: list[Operation] = Field(default_factory=list)

    def add_node(self, node: ThoughtNode, root: bool = False) -> str:
        self.nodes[node.id] = node
        if root:
            self.root_ids.append(node.id)
        for pid in node.parent_ids:
            if pid in self.nodes:
                self.nodes[pid].add_child(node.id)
        return node.id

    def add_edge(self, parent_id: str, child_id: str) -> None:
        if parent_id in self.nodes and child_id in self.nodes:
            self.nodes[parent_id].add_child(child_id)
            self.nodes[child_id].add_parent(parent_id)

    def get_children(self, node_id: str) -> list[ThoughtNode]:
        node = self.nodes.get(node_id)
        if not node:
            return []
        return [self.nodes[cid] for cid in node.child_ids if cid in self.nodes]

    def get_parents(self, node_id: str) -> list[ThoughtNode]:
        node = self.nodes.get(node_id)
        if not node:
            return []
        return [self.nodes[pid] for pid in node.parent_ids if pid in self.nodes]

    def get_leaves(self) -> list[ThoughtNode]:
        return [n for n in self.nodes.values() if not n.child_ids]

    def get_by_state(self, state: ThoughtState) -> list[ThoughtNode]:
        return [n for n in self.nodes.values() if n.state == state]

    def prune(self, node_id: str) -> None:
        node = self.nodes.get(node_id)
        if node:
            node.state = ThoughtState.PRUNED

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def active_count(self) -> int:
        return len([n for n in self.nodes.values() if n.state != ThoughtState.PRUNED])


class GraphOfOperations:
    """Executes operations on a ReasoningGraph with beam search.

    Operations are applied sequentially to transform the graph:
    - Generate: create child nodes from parents using a generator function
    - Score: assign scores to nodes using a scorer function
    - KeepBestN: prune all but top-N nodes by score
    - Aggregate: merge multiple nodes into a single aggregate node
    - Validate: validate nodes and mark as validated/solved
    """

    def __init__(self, graph: ReasoningGraph, beam_width: int = 3):
        self._graph = graph
        self._beam_width = beam_width

    @property
    def graph(self) -> ReasoningGraph:
        return self._graph

    def generate(
        self,
        parent_ids: list[str],
        generator: callable,
        n_branches: int = 1,
        **kwargs,
    ) -> list[str]:
        """Create child nodes from parents using generator function."""
        new_ids = []
        for pid in parent_ids:
            parent = self._graph.nodes.get(pid)
            if not parent:
                continue
            contents = generator(parent.content, n=n_branches, **kwargs)
            for content in contents:
                child = ThoughtNode(
                    content=content,
                    state=ThoughtState.PROPOSED,
                    parent_ids=[pid],
                )
                self._graph.add_node(child)
                self._graph.add_edge(pid, child.id)
                new_ids.append(child.id)
        return new_ids

    def score(
        self,
        node_ids: list[str],
        scorer: callable,
        **kwargs,
    ) -> list[str]:
        """Score nodes and update their state."""
        scored_ids = []
        for nid in node_ids:
            node = self._graph.nodes.get(nid)
            if not node or node.state == ThoughtState.PRUNED:
                continue
            node.score = scorer(node.content, **kwargs)
            node.state = ThoughtState.SCORED
            scored_ids.append(nid)
        return scored_ids

    def keep_best_n(self, node_ids: list[str], n: int | None = None) -> list[str]:
        """Keep top-N nodes by score, prune the rest."""
        if n is None:
            n = self._beam_width
        candidates = [
            self._graph.nodes[nid]
            for nid in node_ids
            if nid in self._graph.nodes and self._graph.nodes[nid].state != ThoughtState.PRUNED
        ]
        candidates.sort(key=lambda x: x.score, reverse=True)
        kept = candidates[:n]
        {c.id for c in kept}
        for c in candidates[n:]:
            self._graph.prune(c.id)
        return [c.id for c in kept]

    def aggregate(
        self,
        node_ids: list[str],
        aggregator: callable,
        **kwargs,
    ) -> str | None:
        """Merge multiple nodes into a single aggregate node."""
        nodes = [self._graph.nodes[nid] for nid in node_ids if nid in self._graph.nodes]
        if not nodes:
            return None
        content = aggregator([n.content for n in nodes], **kwargs)
        agg_node = ThoughtNode(
            content=content,
            state=ThoughtState.PROPOSED,
            parent_ids=[n.id for n in nodes],
            metadata={"aggregated_from": len(nodes)},
        )
        self._graph.add_node(agg_node)
        for n in nodes:
            self._graph.add_edge(n.id, agg_node.id)
        return agg_node.id

    def validate(
        self,
        node_ids: list[str],
        validator: callable,
        **kwargs,
    ) -> list[str]:
        """Validate nodes; mark solved if validator returns True."""
        validated = []
        for nid in node_ids:
            node = self._graph.nodes.get(nid)
            if not node or node.state == ThoughtState.PRUNED:
                continue
            if validator(node.content, node.score, **kwargs):
                node.state = ThoughtState.SOLVED
            else:
                node.state = ThoughtState.VALIDATED
            validated.append(nid)
        return validated

    def beam_search(
        self,
        root_ids: list[str],
        generator: callable,
        scorer: callable,
        validator: callable,
        max_depth: int = 3,
        n_branches: int = 2,
    ) -> list[ThoughtNode]:
        """Run beam search from root nodes.

        At each depth level:
        1. Generate n_branches children per active node
        2. Score all children
        3. Keep top beam_width
        4. Validate surviving nodes
        Returns all solved/validated leaf nodes.
        """
        current_ids = list(root_ids)
        for _depth in range(max_depth):
            if not current_ids:
                break

            generated = self.generate(current_ids, generator, n_branches=n_branches)
            if not generated:
                break

            self.score(generated, scorer)
            kept = self.keep_best_n(generated)
            self.validate(kept, validator)

            current_ids = [
                nid for nid in kept if self._graph.nodes[nid].state == ThoughtState.VALIDATED
            ]

        solved = self._graph.get_by_state(ThoughtState.SOLVED)
        if solved:
            return solved
        return [self._graph.nodes[nid] for nid in current_ids if nid in self._graph.nodes]
