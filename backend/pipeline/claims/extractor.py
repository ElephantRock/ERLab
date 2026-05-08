"""ClaimExtractor — extracts structured claims from paper text via LLM.

Uses provider.structured_output to decompose paper abstracts + wiki entries
into typed Claim objects. Follows closed-book policy and hard boundaries:
  - HB-01: Extraction failure MUST NOT crash calling code.
  - HB-02: Every extracted claim MUST have source_paper_id.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from backend.providers.base import LLMProvider

from .models import Claim, ClaimType

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "claim_extraction.md"

# JSON schema for structured_output
_CLAIM_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_type": {
                        "type": "string",
                        "enum": ["METHOD", "RESULT", "LIMITATION", "FUTURE_WORK", "COMPARISON"],
                    },
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "source_section": {"type": "string"},
                    "confidence": {"type": "number"},
                    "method_name": {"type": ["string", "null"]},
                    "method_category": {"type": ["string", "null"]},
                    "constraints": {"type": ["object", "null"]},
                    "dataset": {"type": ["string", "null"]},
                    "metric": {"type": ["string", "null"]},
                    "value": {"type": ["string", "null"]},
                    "baseline_method": {"type": ["string", "null"]},
                    "baseline_value": {"type": ["string", "null"]},
                    "limitation_category": {"type": ["string", "null"]},
                    "acknowledged": {"type": ["boolean", "null"]},
                    "feasibility": {"type": ["string", "null"]},
                    "potential_impact": {"type": ["string", "null"]},
                    "compared_to": {"type": ["string", "null"]},
                    "relationship": {"type": ["string", "null"]},
                },
                "required": ["claim_type", "title", "description"],
            },
        }
    },
    "required": ["claims"],
}


def _load_prompt_template() -> str:
    """Load the claim extraction prompt template from disk."""
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_messages(paper_text: str, wiki: dict | None = None) -> list[dict]:
    """Build the LLM messages from paper text and optional wiki context."""
    template = _load_prompt_template()

    wiki_section = ""
    if wiki:
        wiki_section = f"### Wiki Context\n```json\n{json.dumps(wiki, indent=2)}\n```"

    user_content = template.format(
        paper_text=paper_text,
        wiki_section=wiki_section,
    )

    return [
        {
            "role": "system",
            "content": "You are a precise research claim extraction engine. Extract only explicitly stated claims.",
        },
        {"role": "user", "content": user_content},
    ]


def _parse_claim(raw: dict, source_paper_id: str) -> Claim:
    """Convert a raw LLM dict into a Claim dataclass."""
    claim_type_str = raw.get("claim_type", "METHOD")
    try:
        claim_type = ClaimType(claim_type_str)
    except ValueError:
        logger.warning("Unknown claim_type '%s', defaulting to METHOD", claim_type_str)
        claim_type = ClaimType.METHOD

    return Claim(
        claim_type=claim_type,
        title=raw.get("title", ""),
        description=raw.get("description", ""),
        source_paper_id=source_paper_id,  # HB-02: always set
        source_section=raw.get("source_section", "abstract"),
        confidence=raw.get("confidence", 0.5),
        method_name=raw.get("method_name"),
        method_category=raw.get("method_category"),
        constraints=raw.get("constraints"),
        dataset=raw.get("dataset"),
        metric=raw.get("metric"),
        value=raw.get("value"),
        baseline_method=raw.get("baseline_method"),
        baseline_value=raw.get("baseline_value"),
        limitation_category=raw.get("limitation_category"),
        acknowledged=raw.get("acknowledged"),
        feasibility=raw.get("feasibility"),
        potential_impact=raw.get("potential_impact"),
        compared_to=raw.get("compared_to"),
        relationship=raw.get("relationship"),
    )


class ClaimExtractor:
    """Extracts structured claims from paper text using an LLM provider.

    Usage:
        extractor = ClaimExtractor(provider)
        claims = await extractor.extract(paper_text, paper_id="2301.00001")
    """

    def __init__(self, provider: LLMProvider) -> None:
        if not isinstance(provider, LLMProvider):
            raise TypeError(
                f"ClaimExtractor requires an LLMProvider instance, got {type(provider).__name__}"
            )
        self._provider = provider

    async def extract(
        self,
        paper_text: str,
        paper_id: str = "",
        wiki: dict | None = None,
    ) -> list[Claim]:
        """Extract claims from paper text.

        Args:
            paper_text: The paper text (abstract, method, results, etc.).
            paper_id: The source paper identifier (arxiv_id or paper.id).
            wiki: Optional wiki context dictionary.

        Returns:
            List of Claim objects. Returns [] on any failure (HB-01).
        """
        try:
            messages = _build_messages(paper_text, wiki)
            raw = await self._provider.structured_output(
                messages, _CLAIM_SCHEMA, temperature=0.2
            )

            raw_claims = raw.get("claims", [])
            if not isinstance(raw_claims, list):
                logger.warning("LLM returned non-list 'claims': %s", type(raw_claims))
                return []

            claims = [_parse_claim(c, source_paper_id=paper_id) for c in raw_claims]

            # HB-02: enforce every claim has source_paper_id
            for claim in claims:
                if not claim.source_paper_id:
                    claim.source_paper_id = paper_id

            return claims

        except json.JSONDecodeError as exc:
            logger.warning("Claim extraction JSON decode error: %s", exc)
            return []
        except Exception as exc:  # noqa: BLE001 — HB-01: never crash
            logger.warning("Claim extraction failed: %s", exc)
            return []

    async def extract_batch(
        self,
        papers: list[dict],
    ) -> dict[str, list[Claim]]:
        """Extract claims from multiple papers.

        Args:
            papers: List of dicts with keys 'text', 'paper_id', and
                    optional 'wiki'.

        Returns:
            Mapping of paper_id → list[Claim].
        """
        results: dict[str, list[Claim]] = {}
        for paper in papers:
            pid = paper.get("paper_id", "")
            text = paper.get("text", "")
            wiki = paper.get("wiki")
            claims = await self.extract(text, paper_id=pid, wiki=wiki)
            results[pid] = claims
        return results
