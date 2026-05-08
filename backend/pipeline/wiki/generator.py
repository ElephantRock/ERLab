"""WikiGenerator — LLM-based structured wiki generation from research papers.

AIV v5.3 — BATCH-123 TASK-01
HB-01: Returns empty WikiEntry on failure, never crashes.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from backend.pipeline.wiki.models import WikiEntry

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "wiki_generation.md"

_WIKI_SCHEMA = {
    "type": "object",
    "properties": {
        "one_line_summary": {"type": "string"},
        "problem_statement": {"type": "string"},
        "proposed_method": {"type": "string"},
        "key_insights": {"type": "array", "items": {"type": "string"}},
        "method_details": {"type": "object"},
        "experiments": {"type": "array", "items": {"type": "object"}},
        "limitations": {"type": "array", "items": {"type": "string"}},
        "future_work": {"type": "array", "items": {"type": "string"}},
        "connections": {"type": "array", "items": {"type": "string"}},
        "code_and_resources": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
        "novelty_assessment": {"type": "string"},
        "contribution_type": {"type": "string"},
        "domain": {"type": "string"},
        "subdomain": {"type": "string"},
        "related_methods": {"type": "array", "items": {"type": "string"}},
        "potential_applications": {"type": "array", "items": {"type": "string"}},
        "reproducibility_notes": {"type": "string"},
    },
}


class WikiGenerator:
    """Generate structured wiki entries from research paper text."""

    def __init__(self, provider) -> None:
        if provider is None:
            raise TypeError("WikiGenerator requires a non-None LLM provider")
        self._provider = provider
        self._prompt_template = self._load_prompt()

    @staticmethod
    def _load_prompt() -> str:
        if _PROMPT_PATH.exists():
            return _PROMPT_PATH.read_text(encoding="utf-8")
        return "Generate a structured wiki from this paper:\n\n{paper_text}"

    async def generate(self, paper_text: str, paper_id: str = "") -> WikiEntry:
        """Generate a wiki entry from paper text.

        Returns empty WikiEntry on failure (HB-01).
        """
        try:
            prompt = self._prompt_template.replace("{paper_text}", paper_text)
            messages = [{"role": "user", "content": prompt}]
            result = await self._provider.structured_output(
                messages, _WIKI_SCHEMA, temperature=0.2
            )
            return self._parse_wiki(result, paper_id)
        except Exception as e:
            logger.warning("WikiGenerator failed for paper_id=%s: %s", paper_id, e)
            return WikiEntry(paper_id=paper_id)  # HB-01

    @staticmethod
    def _parse_wiki(raw: dict, paper_id: str) -> WikiEntry:
        if not isinstance(raw, dict):
            return WikiEntry(paper_id=paper_id)

        return WikiEntry(
            paper_id=paper_id,
            one_line_summary=raw.get("one_line_summary", ""),
            problem_statement=raw.get("problem_statement", ""),
            proposed_method=raw.get("proposed_method", ""),
            key_insights=raw.get("key_insights", []),
            method_details=raw.get("method_details", {}),
            experiments=raw.get("experiments", []),
            limitations=raw.get("limitations", []),
            future_work=raw.get("future_work", []),
            connections=raw.get("connections", []),
            code_and_resources=raw.get("code_and_resources", []),
            tags=raw.get("tags", []),
            novelty_assessment=raw.get("novelty_assessment", ""),
            contribution_type=raw.get("contribution_type", ""),
            domain=raw.get("domain", ""),
            subdomain=raw.get("subdomain", ""),
            related_methods=raw.get("related_methods", []),
            potential_applications=raw.get("potential_applications", []),
            reproducibility_notes=raw.get("reproducibility_notes", ""),
        )
