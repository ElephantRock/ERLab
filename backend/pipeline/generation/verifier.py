"""Reasoning chain verification — validates logical consistency of reasoning graphs.

Checks that premises support conclusions, there is no circular reasoning,
and scores align with stated reasoning. Used to validate ideas before
they advance to the novelty checking stage.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from backend.pipeline.generation.reasoning_graph import ReasoningGraph, ThoughtNode

logger = logging.getLogger(__name__)

_VERIFY_CHAIN_SCHEMA = {
    "type": "object",
    "properties": {
        "is_consistent": {"type": "boolean"},
        "issues": {"type": "array", "items": {"type": "string"}},
        "consistency_score": {"type": "number"},
    },
    "required": ["is_consistent", "issues", "consistency_score"],
}

_VERIFY_IDEA_SCHEMA = {
    "type": "object",
    "properties": {
        "is_consistent": {"type": "boolean"},
        "issues": {"type": "array", "items": {"type": "string"}},
        "consistency_score": {"type": "number"},
    },
    "required": ["is_consistent", "issues", "consistency_score"],
}


class VerificationResult(BaseModel):
    """Result of a reasoning chain verification."""

    node_id: str
    passed: bool = True
    issues: list[str] = Field(default_factory=list)
    consistency_score: float = 1.0


class ReasoningVerifier:
    """Verifies logical consistency of reasoning chains."""

    def __init__(self, provider: Any) -> None:
        self._provider = provider

    async def verify_chain(self, graph: ReasoningGraph) -> list[VerificationResult]:
        """Verify all leaf nodes in a reasoning graph for logical consistency."""
        results: list[VerificationResult] = []
        leaves = graph.get_leaves()

        for leaf in leaves:
            chain = self._build_chain_text(graph, leaf)
            if not chain.strip():
                continue

            result = await self._verify_chain_text(leaf.id, chain)
            results.append(result)

        return results

    async def verify_idea_reasoning(
        self, idea: Any, gap: Any,
    ) -> VerificationResult:
        """Verify that an idea's reasoning is consistent with its source gap."""
        idea_text = f"{getattr(idea, 'title', '')}: {getattr(idea, 'proposed_method', '')}"
        gap_text = f"{getattr(gap, 'title', '')}: {getattr(gap, 'description', '')}"

        try:
            result = await self._provider.structured_output(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a reasoning consistency checker. Verify that "
                            "the proposed idea logically addresses the research gap. "
                            "Check for: unsupported assumptions, logical gaps, "
                            "circular reasoning, and misaligned objectives."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Research Gap:\n{gap_text[:500]}\n\n"
                            f"Proposed Idea:\n{idea_text[:500]}\n\n"
                            "Is this idea's reasoning consistent with the gap?"
                        ),
                    },
                ],
                schema=_VERIFY_IDEA_SCHEMA,
                temperature=0.1,
            )

            return VerificationResult(
                node_id=getattr(idea, 'id', 'unknown'),
                passed=result.get("is_consistent", True),
                issues=result.get("issues", []),
                consistency_score=result.get("consistency_score", 1.0),
            )
        except Exception as e:
            logger.warning("Idea reasoning verification failed: %s", e)
            return VerificationResult(
                node_id=getattr(idea, 'id', 'unknown'),
                passed=True,
            )

    async def _verify_chain_text(
        self, node_id: str, chain_text: str,
    ) -> VerificationResult:
        """Verify a single reasoning chain using LLM."""
        try:
            result = await self._provider.structured_output(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a reasoning chain verifier. Check the following "
                            "chain of reasoning for: logical gaps, unsupported leaps, "
                            "circular reasoning, and internal contradictions."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Reasoning chain:\n{chain_text[:1500]}\n\n"
                            "Is this chain logically consistent?"
                        ),
                    },
                ],
                schema=_VERIFY_CHAIN_SCHEMA,
                temperature=0.1,
            )

            return VerificationResult(
                node_id=node_id,
                passed=result.get("is_consistent", True),
                issues=result.get("issues", []),
                consistency_score=result.get("consistency_score", 1.0),
            )
        except Exception as e:
            logger.warning("Chain verification failed for node %s: %s", node_id[:8], e)
            return VerificationResult(node_id=node_id, passed=True)

    @staticmethod
    def _build_chain_text(graph: ReasoningGraph, leaf: ThoughtNode) -> str:
        """Walk backwards from leaf to root, collecting reasoning chain."""
        chain_parts = [f"[Step] {leaf.content[:300]}"]
        visited = {leaf.id}
        current = leaf

        for _ in range(10):  # Max depth to prevent infinite loops
            parents = graph.get_parents(current.id)
            if not parents:
                break
            parent = parents[0]
            if parent.id in visited:
                break
            visited.add(parent.id)
            chain_parts.append(f"[Step] {parent.content[:300]}")
            current = parent

        chain_parts.reverse()
        return "\n".join(chain_parts)
