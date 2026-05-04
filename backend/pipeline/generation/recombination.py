"""Idea Recombination Operator — synthesizes novel ideas from two parents.

Google's research (arXiv 2509.06503) showed that 44% of recombinations
beat both parent ideas.  This operator combines the strongest elements
of two parent IdeaCandidates into a single child with traceable lineage.
"""

from __future__ import annotations

import json
import logging
import re

from backend.pipeline.generation.models import IdeaCandidate
from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

_RECOMBINATION_SYSTEM = (
    "You are a research idea synthesis agent. "
    "You MUST respond with valid JSON only — no markdown fences."
)

_RECOMBINATION_PROMPT = """\
Combine these two research ideas into a single, novel idea that leverages \
the strongest elements of both parents.

IDEA A: {title_a}
Method: {method_a}
Contributions: {contribs_a}

IDEA B: {title_b}
Method: {method_b}
Contributions: {contribs_b}

Generate a SINGLE combined idea that:
1. Uses the best methodological elements from BOTH parents
2. Addresses a broader problem scope than either parent alone
3. Proposes novel contributions that neither parent individually achieves

Return a JSON object with exactly these keys:
  title, problem_statement, proposed_method, expected_contributions,
  novelty_rationale, evaluation_approach\
"""


class IdeaRecombinator:
    """Combines two parent ideas into a novel child idea.

    The LLM provider is injected via the constructor so the operator
    stays decoupled from any specific LLM backend (AC-02-03).
    """

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def recombine(
        self,
        parent_a: IdeaCandidate,
        parent_b: IdeaCandidate,
    ) -> IdeaCandidate:
        """Synthesize a novel idea combining the strongest elements of both parents.

        Returns exactly **1** ``IdeaCandidate`` (HB-02) whose
        ``parent_idea_ids`` field records both parent IDs for lineage
        tracking.
        """
        prompt = _RECOMBINATION_PROMPT.format(
            title_a=parent_a.title,
            method_a=parent_a.proposed_method,
            contribs_a=parent_a.expected_contributions,
            title_b=parent_b.title,
            method_b=parent_b.proposed_method,
            contribs_b=parent_b.expected_contributions,
        )

        raw = await self._provider.complete(
            messages=[
                {"role": "system", "content": _RECOMBINATION_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
        )

        parsed = self._parse_json(raw)

        child = IdeaCandidate(
            title=parsed.get("title", "Untitled recombination"),
            problem_statement=parsed.get("problem_statement", ""),
            proposed_method=parsed.get("proposed_method", ""),
            expected_contributions=parsed.get("expected_contributions", ""),
            novelty_rationale=parsed.get("novelty_rationale", ""),
            evaluation_approach=parsed.get("evaluation_approach", ""),
            parent_idea_ids=[parent_a.id, parent_b.id],
        )

        logger.info(
            "Recombined '%s' + '%s' → '%s'",
            parent_a.title[:40],
            parent_b.title[:40],
            child.title[:40],
        )

        return child

    @staticmethod
    def _parse_json(raw: str) -> dict:
        """Extract the first JSON object from a possibly messy LLM response."""
        # Strip markdown code fences if present
        text = re.sub(r"```(?:json)?\s*", "", raw).strip()
        # Remove trailing backticks
        text = text.rstrip("`").strip()

        try:
            return json.loads(text)  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            # Try to find the first { … } block
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())  # type: ignore[no-any-return]
                except json.JSONDecodeError:
                    pass
            logger.warning("Failed to parse recombination JSON, using empty dict")
            return {}
