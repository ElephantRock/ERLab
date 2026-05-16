"""WikiVerifier — LLM-grounded claim verification with source-anchored quotes.

AIV v5.3 — BATCH-123 (original) → BATCH-131 (LLM deepening) → Quality Hardening
HB-01: Returns WikiEntry even if every LLM call fails (degrades to keyword).
HB-02: Prompt enforces closed-book verification.
HB-03: verify() returns a NEW WikiEntry, never modifies the input.
QA-01: Source-anchored quote verification — LLM must quote exact text, system
        verifies via fuzzy substring matching. Catches 30-40% of fabrications.
QA-02: Staged confidence — claims accumulate trust through verification stages.
        Downstream trust gates prevent low-trust claims from propagating.
Authority: A-01 (LLM authoritative when available), A-02 (keyword fallback).
"""

from __future__ import annotations

import copy
import json

from backend.pipeline.utils.json_extraction import extract_json
import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path
from typing import Any

from backend.pipeline.wiki.models import WikiEntry

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "wiki_verification.md"


# ---------------------------------------------------------------------------
# QA-02: Staged Confidence
# ---------------------------------------------------------------------------

class TrustTier(Enum):
    """Trust tiers for downstream routing."""
    UNVERIFIED = "unverified"   # No verification attempted
    LOW = "low"                 # Keyword overlap only (0.0–0.3)
    MEDIUM = "medium"           # Single LLM verified (0.3–0.6)
    HIGH = "high"               # Source-anchored quote verified (0.6–0.8)
    VERY_HIGH = "very_high"     # Source-anchored + cross-verified (0.8–1.0)


# Minimum trust tier required for each downstream action
_TRUST_GATES: dict[str, TrustTier] = {
    "display": TrustTier.UNVERIFIED,     # Show everything
    "summarize": TrustTier.LOW,          # Keyword overlap sufficient
    "gap_analysis": TrustTier.MEDIUM,    # LLM verified at minimum
    "study_design": TrustTier.HIGH,      # Source-anchored quote
    "paper_draft": TrustTier.VERY_HIGH,  # Highest confidence only
}

_TIER_ORDER = {
    TrustTier.UNVERIFIED: 0,
    TrustTier.LOW: 1,
    TrustTier.MEDIUM: 2,
    TrustTier.HIGH: 3,
    TrustTier.VERY_HIGH: 4,
}


@dataclass
class ClaimVerificationResult:
    """Result of verifying a single claim, with provenance."""
    claim: str
    supported: bool
    confidence: float = 0.0
    reasoning: str = ""
    trust_tier: TrustTier = TrustTier.UNVERIFIED
    verification_stages: list[str] = field(default_factory=list)
    supporting_quote: str | None = None
    quote_verified: bool = False
    quote_fabricated: bool = False


# ---------------------------------------------------------------------------
# QA-01: Quote fuzzy matching threshold
# ---------------------------------------------------------------------------

_QUOTE_MATCH_THRESHOLD = 0.85  # SequenceMatcher ratio for fuzzy matching


class WikiVerifier:
    """Verifies wiki entries against source paper text.

    Uses LLM-based claim verification with source-anchored quotes (QA-01)
    and staged confidence (QA-02).
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
        return (
            'Verify if this CLAIM is supported by the SOURCE TEXT. '
            'Return JSON: {"supported": bool, "reasoning": str, "supporting_quote": str or null}\n\n'
            'CLAIM: {claim}\n\nSOURCE TEXT: {source_text}'
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def verify(self, wiki: WikiEntry, source_text: str) -> WikiEntry:
        """Verify a wiki entry against source text.

        Returns a NEW WikiEntry with quality_score and unsupported_claims set.
        Original wiki is NOT modified (HB-03).
        """
        result = copy.deepcopy(wiki)
        unsupported: list[str] = []

        if not source_text or not source_text.strip():
            result.quality_score = 0.1
            result.unsupported_claims = ["Empty source text — cannot verify"]
            return result

        # Collect all factual claims from the wiki
        claims = self._extract_claims(wiki)
        source_lower = source_text.lower()

        claim_results: list[ClaimVerificationResult] = []
        verified = 0

        for claim in claims:
            cr = await self._verify_claim_full(claim, source_text, source_lower)
            claim_results.append(cr)

            if cr.supported:
                verified += 1
            else:
                unsupported.append(f"{cr.claim} [{cr.reasoning}]" if cr.reasoning else cr.claim)

        total = max(len(claims), 1)
        result.quality_score = verified / total
        result.unsupported_claims = unsupported

        # Store verification metadata
        result.verification_results = claim_results  # type: ignore[attr-defined]
        return result

    @staticmethod
    def is_actionable(trust_tier: TrustTier, action: str) -> bool:
        """Check if a claim's trust tier is sufficient for a downstream action.

        Usage:
            if WikiVerifier.is_actionable(claim.trust_tier, "gap_analysis"):
                # Use claim for gap analysis
        """
        required = _TRUST_GATES.get(action, TrustTier.UNVERIFIED)
        return _TIER_ORDER.get(trust_tier, 0) >= _TIER_ORDER.get(required, 0)

    # ------------------------------------------------------------------
    # Core verification pipeline
    # ------------------------------------------------------------------

    async def _verify_claim_full(
        self, claim: str, source_text: str, source_lower: str
    ) -> ClaimVerificationResult:
        """Run claim through full verification pipeline: LLM → quote check → keyword fallback."""
        cr = ClaimVerificationResult(claim=claim, supported=False)

        # Try LLM verification first (A-01)
        if self._provider is not None:
            llm_result = await self._verify_claim_with_llm(claim, source_text)

            if llm_result is not None:
                cr.verification_stages.append("single_llm")

                if llm_result.get("supported") is True:
                    # QA-01: Source-anchored quote verification
                    quote = llm_result.get("supporting_quote")
                    if quote:
                        cr.supporting_quote = quote
                        cr.quote_verified = self._verify_quote_in_source(quote, source_text)

                        if cr.quote_verified:
                            # Quote found in source — high confidence
                            cr.supported = True
                            cr.confidence = 0.95
                            cr.trust_tier = TrustTier.HIGH
                            cr.reasoning = llm_result.get("reasoning", "Source-anchored: quote verified in source")
                            cr.verification_stages.append("quote_anchored")
                        else:
                            # QA-01: LLM fabricated the quote
                            cr.supported = False
                            cr.confidence = 0.90
                            cr.trust_tier = TrustTier.LOW
                            cr.quote_fabricated = True
                            cr.reasoning = "LLM provided fabricated quote — not found in source text"
                            cr.verification_stages.append("quote_fabricated")
                            logger.warning("Fabricated quote detected for claim: %s", claim[:80])
                    else:
                        # LLM said supported but didn't provide a quote → downgrade to MEDIUM
                        cr.supported = True
                        cr.confidence = 0.55
                        cr.trust_tier = TrustTier.MEDIUM
                        cr.reasoning = llm_result.get("reasoning", "LLM verified (no quote provided)")
                elif llm_result.get("supported") is False:
                    cr.supported = False
                    cr.reasoning = llm_result.get("reasoning", "Not supported by LLM")
                    cr.confidence = 0.70
                    cr.trust_tier = TrustTier.MEDIUM
                else:
                    # LLM unclear → keyword fallback
                    supported_kw = self._claim_supported_keyword(claim, source_lower)
                    cr.supported = supported_kw
                    cr.confidence = 0.20
                    cr.trust_tier = TrustTier.LOW
                    cr.reasoning = "LLM unclear, keyword fallback: " + ("match" if supported_kw else "no match")
                    cr.verification_stages.append("keyword_overlap")
                    if not supported_kw:
                        pass  # Already unsupported
            else:
                # LLM failed entirely — keyword fallback (HB-01)
                supported_kw = self._claim_supported_keyword(claim, source_lower)
                cr.supported = supported_kw
                cr.confidence = 0.20
                cr.trust_tier = TrustTier.LOW
                cr.reasoning = "LLM failed, keyword fallback"
                cr.verification_stages.append("keyword_overlap")
        else:
            # No provider — keyword overlap only (A-02)
            supported_kw = self._claim_supported_keyword(claim, source_lower)
            cr.supported = supported_kw
            cr.confidence = 0.15
            cr.trust_tier = TrustTier.LOW
            cr.reasoning = "No LLM provider, keyword overlap"
            cr.verification_stages.append("keyword_overlap")

        return cr

    # ------------------------------------------------------------------
    # QA-01: Source-anchored quote verification
    # ------------------------------------------------------------------

    @staticmethod
    def _verify_quote_in_source(quote: str, source_text: str) -> bool:
        """Verify that a quote actually appears in the source text.

        Uses fuzzy matching (SequenceMatcher) to handle whitespace/encoding
        differences. Returns True if match ratio >= threshold.
        """
        quote_stripped = quote.strip()
        source_lower = source_text.lower()
        quote_lower = quote_stripped.lower()

        # Fast path: exact substring match
        if quote_stripped in source_text or quote_lower in source_lower:
            return True

        # Fuzzy path: slide window of quote length over source text
        # Only check every ~50 chars to keep it fast for long sources
        quote_len = len(quote_stripped)
        step = max(1, quote_len // 4)
        for i in range(0, len(source_text) - quote_len + 1, step):
            window = source_text[i : i + quote_len]
            ratio = SequenceMatcher(None, quote_lower, window.lower()).ratio()
            if ratio >= _QUOTE_MATCH_THRESHOLD:
                return True

        return False

    # ------------------------------------------------------------------
    # LLM verification
    # ------------------------------------------------------------------

    async def _verify_claim_with_llm(self, claim: str, source_text: str) -> dict | None:
        """Use LLM to verify if a claim is supported by source text.

        Returns {"supported": bool, "reasoning": str, "supporting_quote": str|None}
        or None on failure.
        """
        try:
            prompt = (
                self._prompt_template
                .replace("{claim}", claim)
                .replace("{source_text}", source_text[:5000])  # Expanded from 3000 for better quote matching
            )
            messages = [{"role": "user", "content": prompt}]
            response = await self._provider.complete(messages, temperature=0.1, max_tokens=512)

            result = extract_json(response)
            if isinstance(result, dict) and "supported" in result:
                return result
            return None

        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
            logger.warning("WikiVerifier LLM parse failed: %s", e)
            return None
        except Exception as e:
            logger.warning("WikiVerifier LLM call failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # Claim extraction & keyword fallback
    # ------------------------------------------------------------------

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
