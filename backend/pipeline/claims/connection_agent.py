"""Cross-Paper Connection Agent — LLM-grounded relationship inference.

AIV v5.3 — BATCH-129 (original) → BATCH-135 (LLM deepening)
Adds LLM-based connection inference beyond COMPARISON claims + shared methods.
"""

from __future__ import annotations

import json

from backend.pipeline.utils.json_extraction import extract_json
import logging
from dataclasses import dataclass
from pathlib import Path

from backend.pipeline.claims.models import Claim, ClaimType

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "connection_inference.md"


@dataclass
class PaperConnection:
    paper_a: str
    paper_b: str
    connection_type: str  # builds_on | contradicts | complements
    confidence: float
    evidence: str


class ConnectionAgent:
    """Find non-obvious relationships between papers via claim matching + LLM inference."""

    def __init__(self, provider=None) -> None:
        self._provider = provider
        self._prompt_template = self._load_prompt()

    @staticmethod
    def _load_prompt() -> str:
        if _PROMPT_PATH.exists():
            return _PROMPT_PATH.read_text(encoding="utf-8")
        return "Classify relationship between papers. Return JSON: {connection_type, confidence, evidence}\n\nPaper A: {claims_a}\nPaper B: {claims_b}"

    def find_connections(self, claims: list[Claim]) -> list[PaperConnection]:
        """Find connections between papers."""
        connections: list[PaperConnection] = []

        # Path 1: Direct COMPARISON claims (existing B129 logic)
        for claim in claims:
            if claim.claim_type == ClaimType.COMPARISON and claim.compared_to:
                connections.append(PaperConnection(
                    paper_a=claim.source_paper_id,
                    paper_b=claim.compared_to,
                    connection_type=self._map_relationship(claim.relationship),
                    confidence=claim.confidence,
                    evidence=claim.title,
                ))

        # Path 2: Shared methods across papers (existing B129 logic)
        method_papers: dict[str, set[str]] = {}
        for claim in claims:
            if claim.claim_type == ClaimType.METHOD and claim.method_name:
                method_papers.setdefault(claim.method_name.lower(), set()).add(claim.source_paper_id)

        for method, papers in method_papers.items():
            papers = list(papers)
            for i in range(len(papers)):
                for j in range(i + 1, len(papers)):
                    connections.append(PaperConnection(
                        paper_a=papers[i], paper_b=papers[j],
                        connection_type="complements", confidence=0.6,
                        evidence=f"Both use {method}",
                    ))

        # Path 3: LLM-based inference for papers sharing datasets
        if self._provider is not None:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            use_llm = not (loop and loop.is_running())

            dataset_papers: dict[str, set[str]] = {}
            paper_claims: dict[str, list[str]] = {}
            for claim in claims:
                if claim.claim_type == ClaimType.RESULT and claim.dataset:
                    dataset_papers.setdefault(claim.dataset.lower(), set()).add(claim.source_paper_id)
                paper_claims.setdefault(claim.source_paper_id, []).append(
                    f"[{claim.claim_type.value}] {claim.title}: {claim.description[:100]}"
                )

            for dataset, papers in dataset_papers.items():
                papers = list(papers)
                for i in range(len(papers)):
                    for j in range(i + 1, len(papers)):
                        pair = tuple(sorted([papers[i], papers[j]]))
                        if any(tuple(sorted([c.paper_a, c.paper_b])) == pair for c in connections):
                            continue
                        if use_llm:
                            try:
                                conn = asyncio.run(self._infer_connection(
                                    paper_claims.get(papers[i], []),
                                    paper_claims.get(papers[j], []),
                                    papers[i], papers[j],
                                ))
                                if conn:
                                    connections.append(conn)
                            except Exception as e:
                                logger.warning("LLM connection inference failed: %s", e)

        return self._deduplicate(connections)

    async def _infer_connection(
        self, claims_a: list[str], claims_b: list[str], paper_a: str, paper_b: str
    ) -> PaperConnection | None:
        """Use LLM to infer a connection between two papers."""
        try:
            prompt = self._prompt_template
            prompt = prompt.replace("{claims_a}", "\n".join(claims_a[:5]))
            prompt = prompt.replace("{claims_b}", "\n".join(claims_b[:5]))

            messages = [{"role": "user", "content": prompt}]
            response = await self._provider.complete(messages, temperature=0.1, max_tokens=256)

            result = extract_json(response)
            return PaperConnection(
                paper_a=paper_a,
                paper_b=paper_b,
                connection_type=result.get("connection_type", "complements"),
                confidence=float(result.get("confidence", 0.5)),
                evidence=result.get("evidence", ""),
            )
        except Exception as e:
            logger.warning("Connection inference failed: %s", e)
            return None

    @staticmethod
    def _map_relationship(rel: str | None) -> str:
        if not rel:
            return "complements"
        return {"improves_on": "builds_on", "extends": "builds_on",
                "contradicts": "contradicts", "different": "complements",
                "complements": "complements"}.get(rel, "complements")

    @staticmethod
    def _deduplicate(connections: list[PaperConnection]) -> list[PaperConnection]:
        seen: set[tuple[str, str, str]] = set()
        unique: list[PaperConnection] = []
        for conn in connections:
            pair = tuple(sorted([conn.paper_a, conn.paper_b]))
            key = (pair[0], pair[1], conn.connection_type)
            if key not in seen:
                seen.add(key)
                unique.append(conn)
        return unique
