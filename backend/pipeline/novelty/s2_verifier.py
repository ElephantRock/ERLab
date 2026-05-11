"""S2 Novelty Verifier: uses Semantic Scholar to verify idea novelty via web search (B163).

Complements the local vector-store NoveltyChecker with live web verification.
For each idea, searches S2 for similar work and asks LLM to judge overlap.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class S2NoveltyResult:
    """Result of S2 novelty verification for a single idea."""
    idea_title: str
    s2_papers_found: int = 0
    prior_art_titles: list[str] = field(default_factory=list)
    llm_verdict: str = "unknown"  # "novel", "partially_novel", "not_novel"
    novelty_score: float = 0.5    # 0.0=exact match, 1.0=nothing similar
    justification: str = ""


class S2NoveltyVerifier:
    """Verify idea novelty using Semantic Scholar web search.

    Usage:
        verifier = S2NoveltyVerifier(s2_source, llm_provider)
        result = await verifier.verify(idea_title, idea_description)
    """

    def __init__(
        self,
        s2_source: Any = None,
        llm_provider: Any = None,
        max_search_rounds: int = 3,
        cooldown: float = 1.0,
    ) -> None:
        self._s2 = s2_source
        self._provider = llm_provider
        self._max_rounds = max_search_rounds
        self._cooldown = cooldown

    async def verify(
        self,
        idea_title: str,
        idea_description: str = "",
    ) -> S2NoveltyResult:
        """Search S2 for prior art and LLM-judge novelty."""
        result = S2NoveltyResult(idea_title=idea_title)

        if not self._s2:
            result.llm_verdict = "unknown"
            result.justification = "S2 source not available"
            return result

        # Search S2 with idea title keywords
        search_query = idea_title[:200]
        try:
            papers = await self._s2.search(search_query, limit=10)
            result.s2_papers_found = len(papers)
            result.prior_art_titles = [p.title for p in papers[:5] if p.title]
        except Exception as e:
            logger.warning("S2 novelty search failed: %s", e)
            result.justification = f"S2 search error: {e}"
            return result

        await asyncio.sleep(self._cooldown)

        if not papers:
            result.llm_verdict = "novel"
            result.novelty_score = 1.0
            result.justification = "No similar papers found on S2"
            return result

        # LLM judgment
        if self._provider:
            try:
                prior_art_text = "\n".join(f"- {t}" for t in result.prior_art_titles[:5])
                prompt = (
                    f"## Idea to evaluate:\n{idea_title}\n\n"
                    f"{idea_description[:500]}\n\n"
                    f"## Similar papers found on Semantic Scholar:\n{prior_art_text}\n\n"
                    f"Judge: Is the idea novel compared to existing work?\n"
                    f"Reply with exactly one word (novel/partially_novel/not_novel) "
                    f"then a brief justification.\n"
                    f"Format: VERDICT: <word>\nJUSTIFICATION: <text>"
                )
                response = await self._provider.complete(prompt)
                result.llm_verdict = self._parse_verdict(response)
                result.justification = self._extract_justification(response)
                result.novelty_score = self._verdict_to_score(result.llm_verdict)
            except Exception as e:
                logger.warning("S2 novelty LLM judgment failed: %s", e)
                # Fallback: score based on paper count
                result.novelty_score = max(0.1, 1.0 - len(papers) * 0.1)
                result.justification = f"LLM failed; heuristic score based on {len(papers)} similar papers"
        else:
            # No LLM — heuristic score
            result.novelty_score = max(0.1, 1.0 - len(papers) * 0.1)
            result.justification = f"Heuristic: {len(papers)} similar papers found"

        return result

    @staticmethod
    def _parse_verdict(response: str) -> str:
        response_lower = response.lower()
        for word in ["not_novel", "partially_novel", "novel"]:
            if word in response_lower:
                return word
        return "unknown"

    @staticmethod
    def _extract_justification(response: str) -> str:
        for line in response.split("\n"):
            if "justification:" in line.lower():
                return line.split(":", 1)[-1].strip()
        return response[:200]

    @staticmethod
    def _verdict_to_score(verdict: str) -> float:
        return {"novel": 0.9, "partially_novel": 0.5, "not_novel": 0.1}.get(verdict, 0.5)
