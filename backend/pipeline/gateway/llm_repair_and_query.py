"""LLM-backed JSON repair service — goes through the gateway for enforcement.

When mechanical JSON repair fails (backend.pipeline.utils.json_extraction),
this service attempts LLM-based repair. It uses stage="repair" so that
SmartRouter enforcement can gate it.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class LLMRepairService:
    """Gateway-backed JSON repair for structured outputs.

    Use when mechanical repair fails. Calls the LLM provider via the gateway,
    which is subject to SmartRouter enforcement for the 'repair' stage.
    """

    def __init__(self, gateway) -> None:
        from backend.pipeline.gateway.gateway import LLMGateway
        self._gateway: LLMGateway = gateway

    async def repair_json(
        self,
        broken_json: str,
        schema_hint: str = "",
        run_id: str = "",
    ) -> dict[str, Any] | None:
        """Attempt LLM-based JSON repair.

        Returns repaired dict on success, None on failure.
        The call goes through the gateway with stage='repair',
        enabling SmartRouter enforcement.
        """
        from backend.pipeline.gateway.gateway import LLMRequest

        prompt = (
            "The following text was supposed to be valid JSON but could not be parsed.\n"
            "Repair it and return ONLY valid JSON. No explanation.\n\n"
        )
        if schema_hint:
            prompt += f"Expected schema:\n{schema_hint}\n\n"
        prompt += f"Broken JSON:\n{broken_json[:3000]}\n\nReturn the repaired JSON:"

        request = LLMRequest(
            task="repair",
            messages=[
                {"role": "system", "content": "You are a JSON repair specialist. "
                 "Return only valid JSON. No markdown, no explanation."},
                {"role": "user", "content": prompt},
            ],
            stage="repair",
            max_output_tokens=4096,
            run_id=run_id,
        )

        response = await self._gateway.call(request)

        if response.degraded:
            logger.warning(
                "LLM repair degraded (enforcement?): %s",
                response.warnings,
            )
            return None

        content = response.content
        if not content:
            return None

        # Try to parse the repaired JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try extracting JSON from markdown code block
            import re
            json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            logger.warning("LLM repair produced unparseable output")
            return None


class LLMQueryGenerator:
    """Gateway-backed search query generator.

    Generates search queries from a research domain/topic. Uses
    stage='query_generation' for SmartRouter enforcement.
    """

    def __init__(self, gateway) -> None:
        from backend.pipeline.gateway.gateway import LLMGateway
        self._gateway: LLMGateway = gateway

    async def generate_queries(
        self,
        domain: str,
        topic: str,
        n_queries: int = 5,
        run_id: str = "",
    ) -> list[str]:
        """Generate search queries for a research topic.

        Returns list of query strings. Empty list on failure/degradation.
        """
        from backend.pipeline.gateway.gateway import LLMRequest

        request = LLMRequest(
            task="query_generation",
            messages=[
                {"role": "system", "content": (
                    "You are a research query generator. "
                    "Generate academic search queries. "
                    "Return ONLY a JSON array of strings, no other text."
                )},
                {"role": "user", "content": (
                    f"Domain: {domain}\n"
                    f"Topic: {topic}\n"
                    f"Generate {n_queries} search queries for finding relevant papers.\n"
                    "Return a JSON array of query strings."
                )},
            ],
            stage="query_generation",
            max_output_tokens=1024,
            run_id=run_id,
        )

        response = await self._gateway.call(request)

        if response.degraded:
            logger.warning(
                "Query generation degraded (enforcement?): %s",
                response.warnings,
            )
            return []

        content = response.content
        if not content:
            return []

        # Parse JSON array
        try:
            queries = json.loads(content)
            if isinstance(queries, list):
                return [str(q) for q in queries if isinstance(q, str)]
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                try:
                    queries = json.loads(json_match.group(0))
                    if isinstance(queries, list):
                        return [str(q) for q in queries if isinstance(q, str)]
                except json.JSONDecodeError:
                    pass

        logger.warning("Query generation produced unparseable output")
        return []

    async def generate_adaptive_queries(
        self,
        *,
        research_question: str,
        attempted_queries: list[str],
        papers: list[Any],
        n_queries: int = 3,
        run_id: str = "",
        max_papers: int = 20,
        abstract_chars: int = 600,
        dedup_similarity_threshold: float = 0.85,
    ) -> list[str]:
        """Generate evidence-aware follow-up search queries.

        Inspects the literature already retrieved and generates queries
        targeting uncovered aspects. Returns at most ``n_queries`` clean,
        non-duplicate query strings. Returns ``[]`` on any failure or
        when no further search is justified.

        The call goes through the gateway with stage='query_generation',
        inheriting the same routing and accounting as initial query
        generation. No direct provider call.

        Args:
            research_question: The run's research question or domain.
            attempted_queries: Queries already executed (for dedup).
            papers: Papers discovered so far (``Paper`` objects).
            n_queries: Maximum queries to return.
            run_id: Pipeline run ID for gateway accounting.
            max_papers: Maximum papers to include in the digest.
            abstract_chars: Maximum abstract characters per paper.
            dedup_similarity_threshold: SequenceMatcher ratio above
                which a candidate is considered a near-duplicate.
        """
        from backend.pipeline.gateway.gateway import LLMRequest
        from backend.pipeline.literature.adaptive_search import (
            filter_adaptive_queries,
        )

        # ── Build bounded evidence digest ────────────────────────────
        digest_papers = papers[:max_papers]
        digest_lines: list[str] = []

        digest_lines.append(f"RESEARCH QUESTION\n{research_question}\n")
        digest_lines.append("SEARCHES ALREADY EXECUTED")
        for i, q in enumerate(attempted_queries, 1):
            digest_lines.append(f"{i}. {q}")
        digest_lines.append("")
        digest_lines.append("CURRENTLY DISCOVERED LITERATURE")

        for i, p in enumerate(digest_papers, 1):
            abstract = (getattr(p, "abstract", None) or "")[:abstract_chars]
            digest_lines.append(
                f"\n[{i}]\n"
                f"Title: {getattr(p, 'title', '')}\n"
                f"Year: {getattr(p, 'year', '')}\n"
                f"Venue: {getattr(p, 'venue', '')}\n"
                f"Source: {getattr(p, 'source', '')}\n"
                f"Abstract: {abstract}"
            )

        user_content = "\n".join(digest_lines)

        system_content = (
            "You are an evidence-aware academic search planner.\n"
            "Given the research question, searches already executed, "
            "and literature discovered so far, identify aspects of the "
            "existing research landscape that remain insufficiently "
            "covered.\n\n"
            f"Return at most {n_queries} academic search queries "
            "targeting those missing coverage areas.\n\n"
            "Do not:\n"
            "- declare research gaps\n"
            "- propose research ideas\n"
            "- repeat or trivially paraphrase prior queries\n"
            "- explain your answer\n\n"
            "If no additional search is justified, return [].\n"
            "Return ONLY a JSON array of strings."
        )

        request = LLMRequest(
            task="query_generation",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            stage="query_generation",
            max_output_tokens=1024,
            run_id=run_id,
        )

        # ── Call gateway ─────────────────────────────────────────────
        try:
            response = await self._gateway.call(request)
        except Exception as e:  # noqa: BLE001
            logger.warning("Adaptive query planner exception: %s", e)
            return []

        if response.degraded:
            logger.warning(
                "Adaptive query planner degraded: %s",
                response.warnings,
            )
            return []

        content = response.content
        if not content:
            return []

        # ── Parse JSON array ─────────────────────────────────────────
        raw_queries: list[str] = []
        try:
            parsed = json.loads(content)
            if isinstance(parsed, list):
                raw_queries = [str(q) for q in parsed if isinstance(q, str)]
        except json.JSONDecodeError:
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(0))
                    if isinstance(parsed, list):
                        raw_queries = [
                            str(q) for q in parsed if isinstance(q, str)
                        ]
                except json.JSONDecodeError:
                    pass

        if not raw_queries:
            logger.debug(
                "Adaptive query planner produced no parseable queries"
            )
            return []

        # ── Filter through query hygiene ─────────────────────────────
        return filter_adaptive_queries(
            raw_queries,
            attempted_queries,
            max_queries=n_queries,
            similarity_threshold=dedup_similarity_threshold,
        )
