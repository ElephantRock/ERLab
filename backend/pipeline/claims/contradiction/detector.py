"""ContradictionDetector — LLM-grounded cross-paper claim contradiction detection.

AIV v5.3 — BATCH-125 (original) → BATCH-132 (LLM deepening)
HB-01: Returns [] on failure. HB-02: Only RESULT claims with same dataset+metric.
Authority: LLM judgment authoritative when available; numeric heuristic as fallback.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

from backend.pipeline.claims.models import Claim, ClaimType
from backend.pipeline.claims.contradiction.models import ContradictionCandidate

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "verification.md"


class ContradictionDetector:
    """Find contradictory claims across papers by comparing RESULT claims.

    Uses LLM-based verification when provider is available.
    Falls back to numeric >10% heuristic on LLM failure.
    """

    def __init__(self, claim_store=None, provider=None) -> None:
        self._claim_store = claim_store
        self._provider = provider
        self._prompt_template = self._load_prompt()

    @staticmethod
    def _load_prompt() -> str:
        if _PROMPT_PATH.exists():
            return _PROMPT_PATH.read_text(encoding="utf-8")
        return "Compare these claims and determine if they contradict. Return JSON with is_genuine_contradiction, category, reasoning.\n\n{claim_a_info}\n\n{claim_b_info}"

    def find_contradictions(
        self, claims: list[Claim]
    ) -> list[ContradictionCandidate]:
        """Find contradictions among claims.

        Returns [] on empty input or failure (HB-01).
        Only considers RESULT claims with same dataset + metric (HB-02).
        """
        try:
            candidates = self._find_candidates(claims)
            if self._provider is not None:
                import asyncio
                verified = []
                for c in candidates:
                    verified.append(asyncio.run(self._verify_contradiction(c)))
                return verified
            else:
                # Fallback: numeric heuristic
                return [self._verify_numeric(c) for c in candidates]
        except Exception as e:
            logger.warning("ContradictionDetector failed: %s", e)
            return []  # HB-01

    def _find_candidates(
        self, claims: list[Claim]
    ) -> list[ContradictionCandidate]:
        """Pair RESULT claims with same dataset + metric but different values."""
        result_claims = [c for c in claims if c.claim_type == ClaimType.RESULT]

        groups: dict[tuple[str, str], list[Claim]] = defaultdict(list)
        for claim in result_claims:
            if claim.dataset and claim.metric:
                key = (claim.dataset.lower().strip(), claim.metric.lower().strip())
                groups[key].append(claim)

        candidates: list[ContradictionCandidate] = []
        for (dataset, metric), group in groups.items():
            for i, claim_a in enumerate(group):
                for claim_b in group[i + 1:]:
                    if claim_a.source_paper_id == claim_b.source_paper_id:
                        continue
                    val_a = (claim_a.value or "").strip()
                    val_b = (claim_b.value or "").strip()
                    if val_a and val_b and val_a != val_b:
                        candidates.append(ContradictionCandidate(
                            claim_a=claim_a,
                            claim_b=claim_b,
                            metric=metric,
                            dataset=dataset,
                            value_a=val_a,
                            value_b=val_b,
                        ))

        return candidates

    async def _verify_contradiction(
        self, candidate: ContradictionCandidate
    ) -> ContradictionCandidate:
        """Use LLM to verify if a contradiction is genuine.

        Returns the candidate with is_genuine, explanation set.
        Falls back to numeric heuristic on LLM failure.
        """
        try:
            prompt = self._prompt_template
            prompt = prompt.replace("{paper_a}", candidate.claim_a.source_paper_id)
            prompt = prompt.replace("{dataset_a}", candidate.claim_a.dataset or "")
            prompt = prompt.replace("{metric_a}", candidate.claim_a.metric or "")
            prompt = prompt.replace("{value_a}", candidate.value_a)
            prompt = prompt.replace("{method_a}", candidate.claim_a.method_name or "Unknown")
            prompt = prompt.replace("{paper_b}", candidate.claim_b.source_paper_id)
            prompt = prompt.replace("{dataset_b}", candidate.claim_b.dataset or "")
            prompt = prompt.replace("{metric_b}", candidate.claim_b.metric or "")
            prompt = prompt.replace("{value_b}", candidate.value_b)
            prompt = prompt.replace("{method_b}", candidate.claim_b.method_name or "Unknown")

            messages = [{"role": "user", "content": prompt}]
            response = await self._provider.complete(messages, temperature=0.1, max_tokens=256)

            # Parse JSON from response
            response_text = response.strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            result = json.loads(response_text)

            is_genuine = result.get("is_genuine_contradiction", False)
            category = result.get("category", "incomparable")
            reasoning = result.get("reasoning", "")

            candidate.is_genuine = is_genuine
            if is_genuine:
                candidate.explanation = f"[LLM: {category}] {reasoning}"
            else:
                candidate.explanation = f"[LLM: {category}] {reasoning}"

            return candidate

        except Exception as e:
            logger.warning("LLM contradiction verification failed, falling back to numeric: %s", e)
            return self._verify_numeric(candidate)

    @staticmethod
    def _verify_numeric(candidate: ContradictionCandidate) -> ContradictionCandidate:
        """Numeric heuristic fallback: >10% difference = genuine."""
        try:
            val_a = float(candidate.value_a.replace("%", "").replace("BLEU", "").strip())
            val_b = float(candidate.value_b.replace("%", "").replace("BLEU", "").strip())
            diff_pct = abs(val_a - val_b) / max(abs(val_a), abs(val_b), 0.001)
            if diff_pct > 0.1:
                candidate.is_genuine = True
                candidate.explanation = f"[Numeric] Values differ by {diff_pct:.1%}: {candidate.value_a} vs {candidate.value_b}"
            else:
                candidate.is_genuine = False
                candidate.explanation = f"[Numeric] Values differ by only {diff_pct:.1%}: likely variation"
        except (ValueError, ZeroDivisionError):
            candidate.is_genuine = None
            candidate.explanation = "[Numeric] Could not determine: non-numeric values"
        return candidate
