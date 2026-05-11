"""Citation tree explorer: recursive citation/reference traversal (B161).

Starting from seed papers found via keyword search, traverses the citation
graph bidirectionally:
  - References (backwards): foundational papers this work cites
  - Citations (forwards): newer papers that cite this work

Configurable breadth × depth. Respects API rate limits.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from backend.pipeline.literature.models import Paper

logger = logging.getLogger(__name__)


@dataclass
class TreeNode:
    """A node in the citation tree."""
    paper: Paper
    depth: int
    direction: str  # "forward" (citations) or "backward" (references)
    parent_title: str = ""


@dataclass
class TreeExplorationResult:
    """Result of a citation tree exploration."""
    seed_papers: int = 0
    total_discovered: int = 0
    forward_papers: int = 0       # papers citing seed papers
    backward_papers: int = 0      # papers cited by seed papers
    tree: list[TreeNode] = field(default_factory=list)
    elapsed_seconds: float = 0.0


class CitationExplorer:
    """Explore citation graph recursively from seed papers.

    Usage:
        explorer = CitationExplorer(s2_source, openalex_source)
        result = await explorer.explore(seed_papers, max_depth=2, breadth=5)
    """

    def __init__(
        self,
        s2_source: Any = None,
        openalex_source: Any = None,
        cooldown: float = 1.0,
    ) -> None:
        self._s2 = s2_source
        self._openalex = openalex_source
        self._cooldown = cooldown

    async def explore(
        self,
        seed_papers: list[Paper],
        max_depth: int = 2,
        breadth: int = 5,
        direction: str = "both",  # "forward", "backward", "both"
    ) -> TreeExplorationResult:
        """Explore citation tree from seed papers.

        Args:
            seed_papers: Starting papers from keyword search.
            max_depth: How many citation hops (1 = direct only, 2 = one more level).
            breadth: Max papers to follow per seed paper per level.
            direction: "forward" (citing), "backward" (cited), or "both".

        Returns:
            TreeExplorationResult with all discovered papers.
        """
        start = time.time()
        result = TreeExplorationResult(seed_papers=len(seed_papers))

        seen_titles = {p.title.lower().strip() for p in seed_papers}
        queue: list[tuple[Paper, int]] = [(p, 0) for p in seed_papers[:breadth * 2]]

        while queue:
            paper, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            # Forward: papers that cite this paper
            if direction in ("forward", "both"):
                forward = await self._get_citations(paper, breadth)
                for fp in forward:
                    title_key = fp.title.lower().strip()
                    if title_key not in seen_titles:
                        seen_titles.add(title_key)
                        node = TreeNode(paper=fp, depth=depth + 1, direction="forward", parent_title=paper.title)
                        result.tree.append(node)
                        result.forward_papers += 1
                        if depth + 1 < max_depth:
                            queue.append((fp, depth + 1))

                if forward:
                    await asyncio.sleep(self._cooldown)

            # Backward: papers this paper cites (foundational)
            if direction in ("backward", "both"):
                backward = await self._get_references(paper, breadth)
                for bp in backward:
                    title_key = bp.title.lower().strip()
                    if title_key not in seen_titles:
                        seen_titles.add(title_key)
                        node = TreeNode(paper=bp, depth=depth + 1, direction="backward", parent_title=paper.title)
                        result.tree.append(node)
                        result.backward_papers += 1
                        if depth + 1 < max_depth:
                            queue.append((bp, depth + 1))

                if backward:
                    await asyncio.sleep(self._cooldown)

        result.total_discovered = result.forward_papers + result.backward_papers
        result.elapsed_seconds = time.time() - start

        logger.info(
            "Citation tree exploration: %d seeds → %d discovered (%d forward, %d backward) in %.1fs",
            result.seed_papers, result.total_discovered,
            result.forward_papers, result.backward_papers,
            result.elapsed_seconds,
        )
        return result

    def extract_papers(self, result: TreeExplorationResult) -> list[Paper]:
        """Extract unique Paper objects from tree exploration result."""
        return [node.paper for node in result.tree]

    async def _get_citations(self, paper: Paper, limit: int) -> list[Paper]:
        """Get papers that cite this paper."""
        # Try S2 first, then OpenAlex
        for source in [self._s2, self._openalex]:
            if source is None:
                continue
            try:
                if hasattr(source, "get_citations"):
                    return await source.get_citations(paper.id, limit=limit)
            except Exception as e:
                logger.debug("Citation lookup failed on %s: %s", type(source).__name__, e)
        return []

    async def _get_references(self, paper: Paper, limit: int) -> list[Paper]:
        """Get papers cited by this paper."""
        for source in [self._s2, self._openalex]:
            if source is None:
                continue
            try:
                if hasattr(source, "get_references"):
                    return await source.get_references(paper.id, limit=limit)
            except Exception as e:
                logger.debug("Reference lookup failed on %s: %s", type(source).__name__, e)
        return []
