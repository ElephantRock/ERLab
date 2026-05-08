"""Cross-Paper Connection Agent — finds relationships between papers.

AIV v5.3 — BATCH-129
Classifies connections as: builds_on, contradicts, complements.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from backend.pipeline.claims.models import Claim, ClaimType

logger = logging.getLogger(__name__)


@dataclass
class PaperConnection:
    """A typed relationship between two papers."""
    paper_a: str  # paper_id
    paper_b: str
    connection_type: str  # builds_on | contradicts | complements
    confidence: float
    evidence: str  # Which claims support this connection


class ConnectionAgent:
    """Find non-obvious relationships between papers via claim matching."""

    def find_connections(self, claims: list[Claim]) -> list[PaperConnection]:
        """Find connections between papers based on their claims.

        Uses COMPARISON claims directly, and infers from RESULT + METHOD overlaps.
        """
        connections: list[PaperConnection] = []

        # Direct COMPARISON claims
        for claim in claims:
            if claim.claim_type == ClaimType.COMPARISON and claim.compared_to:
                connections.append(PaperConnection(
                    paper_a=claim.source_paper_id,
                    paper_b=claim.compared_to,
                    connection_type=self._map_relationship(claim.relationship),
                    confidence=claim.confidence,
                    evidence=claim.title,
                ))

        # Infer from shared methods across papers
        method_papers: dict[str, list[str]] = {}  # method_name -> [paper_ids]
        for claim in claims:
            if claim.claim_type == ClaimType.METHOD and claim.method_name:
                method_papers.setdefault(claim.method_name.lower(), set()).add(claim.source_paper_id)
        
        for method, papers in method_papers.items():
            papers = list(papers)
            for i in range(len(papers)):
                for j in range(i + 1, len(papers)):
                    if papers[i] != papers[j]:
                        connections.append(PaperConnection(
                            paper_a=papers[i],
                            paper_b=papers[j],
                            connection_type="complements",
                            confidence=0.6,
                            evidence=f"Both use {method}",
                        ))

        return self._deduplicate(connections)

    @staticmethod
    def _map_relationship(rel: str | None) -> str:
        """Map claim relationship to connection type."""
        if not rel:
            return "complements"
        mapping = {
            "improves_on": "builds_on",
            "extends": "builds_on",
            "contradicts": "contradicts",
            "different": "complements",
            "complements": "complements",
        }
        return mapping.get(rel, "complements")

    @staticmethod
    def _deduplicate(connections: list[PaperConnection]) -> list[PaperConnection]:
        """Remove duplicate connections (same pair, same type)."""
        seen: set[tuple[str, str, str]] = set()
        unique: list[PaperConnection] = []
        for conn in connections:
            pair = tuple(sorted([conn.paper_a, conn.paper_b]))
            key = (pair[0], pair[1], conn.connection_type)
            if key not in seen:
                seen.add(key)
                unique.append(conn)
        return unique
