"""LLM-backed JSON repair service — goes through the gateway for enforcement.

When mechanical JSON repair fails (backend.pipeline.utils.json_extraction),
this service attempts LLM-based repair. It uses stage="repair" so that
SmartRouter enforcement can gate it.
"""

from __future__ import annotations

import json
import logging
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
