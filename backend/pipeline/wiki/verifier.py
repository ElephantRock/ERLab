"""WikiVerifier — LLM-grounded claim verification against source text.

AIV v5.3 — BATCH-123 (original) → BATCH-131 (LLM deepening)
HB-01: Returns WikiEntry even if every LLM call fails (degrades to keyword).
HB-02: Prompt enforces closed-book verification.
HB-03: verify() returns a NEW WikiEntry, never modifies the input.
Authority: A-01 (LLM authoritative when available), A-02 (keyword fallback).
"""

from __future__ import annotations

import copy
import json
import logging
import re
from pathlib import Path

from backend.pipeline.wiki.models import WikiEntry

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "wiki_verification.md"


class WikiVerifier:
    """Verifies wiki entries against source paper text.

    Uses LLM-based claim verification when a provider is available.
    Falls back to keyword overlap when provider is None or on LLM failure.
    Does NOT modify the input wiki (HB-03).
    """

    def __init__(self, provider=None) -> None:
        self._provider = provider
        self._prompt_template = self._load_prompt()

    @staticmethod
    def _load_prompt() -> str:
        if _PROMPT_PATH.exists():
            return _PROMPT_PATH.read_text(encoding="utf-8")
        return "Verify if this CLAIM is supported by the SOURCE TEXT. Return JSON: {\"supported\": bool, \"reasoning\": str}\n\nCLAIM: {claim}\n\nSOURCE TEXT: {source_text}"

    async def verify(self, wiki: WikiEntry, source_text: str) -> WikiEntry:
        """Verify a wiki entry against source text.

        Returns a NEW WikiEntry with quality_score and unsupported_claims set.
        Original wiki is NOT modified (HB-03).
        """
        # Deep copy to avoid mutation (HB-03)
        result = copy.deepcopy(wiki)
        unsupported: list[str] = []

        if not source_text or not source_text.strip():
            result.quality_score = 0.1
            result.unsupported_claims = ["Empty source text — cannot verify"]
            return result

        # Collect all factual claims from the wiki
        claims = self._extract_claims(wiki)
        source_lower = source_text.lower()

        verified = 0
        for claim in claims:
            supported = False

            # Try LLM verification first (A-01)
            if self._provider is not None:
                llm_result = await self._verify_claim_with_llm(claim, source_text)
                if llm_result is not None:
                    if llm_result.get("supported") is True:
                        supported = True
                    elif llm_result.get("supported") is False:
                        supported = False
                        reasoning = llm_result.get("reasoning", "Not supported by LLM")
                        unsupported.append(f"{claim} [{reasoning}]")
                    else:
                        # LLM returned None/unclear — fall back to keyword
                        supported = self._claim_supported_keyword(claim, source_lower)
                        if not supported:
                            unsupported.append(claim)
                else:
                    # LLM failed entirely — fall back to keyword (HB-01)
                    supported = self._claim_supported_keyword(claim, source_lower)
                    if not supported:
                        unsupported.append(claim)
            else:
                # No provider — use keyword overlap (A-02)
                supported = self._claim_supported_keyword(claim, source_lower)
                if not supported:
                    unsupported.append(claim)

            if supported:
                verified += 1

        total = max(len(claims), 1)
        result.quality_score = verified / total
        result.unsupported_claims = unsupported
        return result

    async def _verify_claim_with_llm(self, claim: str, source_text: str) -> dict | None:
        """Use LLM to verify if a claim is supported by source text.

        Returns {"supported": bool, "reasoning": str} or None on failure.
        """
        try:
            prompt = self._prompt_template.replace("{claim}", claim).replace("{source_text}", source_text[:3000])
            messages = [{"role": "user", "content": prompt}]
            response = await self._provider.complete(messages, temperature=0.1, max_tokens=256)

            # Parse JSON from response string
            # LLM may return markdown-wrapped JSON or plain JSON
            response_text = response.strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            result = json.loads(response_text)
            if isinstance(result, dict) and "supported" in result:
                return result
            return None

        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
            logger.warning("WikiVerifier LLM parse failed: %s", e)
            return None
        except Exception as e:
            logger.warning("WikiVerifier LLM call failed: %s", e)
            return None

    @staticmethod
    def _extract_claims(wiki: WikiEntry) -> list[str]:
        """Extract verifiable claims from a wiki entry."""
        claims: list[str] = []

        if wiki.proposed_method:
            claims.append(wiki.proposed_method)
        for insight in wiki.key_insights:
            claims.append(insight)
        for exp in wiki.experiments:
            parts = []
            if isinstance(exp, dict):
                if "dataset" in exp:
                    parts.append(f"dataset: {exp['dataset']}")
                if "metric" in exp and "value" in exp:
                    parts.append(f"{exp['metric']}: {exp['value']}")
            if parts:
                claims.append("; ".join(parts))

        return claims

    @staticmethod
    def _claim_supported_keyword(claim: str, source_lower: str) -> bool:
        """Keyword overlap fallback (A-02).

        Returns True if >=40% of content words from the claim appear in source.
        """
        claim_lower = claim.lower()
        claim_words = {w for w in re.findall(r"[a-z0-9]+", claim_lower) if len(w) > 3}
        if not claim_words:
            return True

        found = sum(1 for w in claim_words if w in source_lower)
        ratio = found / len(claim_words)
        return ratio >= 0.4
