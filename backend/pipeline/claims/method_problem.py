"""Method-Problem Gap Detection — LLM-grounded applicability scoring.

AIV v5.3 — BATCH-126 (original) → BATCH-133 (LLM deepening)
Returns differentiated scores (0.1-0.9) instead of hardcoded 0.5.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from backend.pipeline.claims.models import Claim, ClaimType

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "applicability_scoring.md"


@dataclass
class MethodProblemGap:
    method_name: str
    method_paper_id: str
    problem_dataset: str
    applicability_score: float
    reasoning: str = ""


class MethodProblemDetector:
    """Find unexplored method-dataset combinations from claims.

    Uses LLM-based applicability scoring when provider is available.
    Falls back to uniform 0.5 on LLM failure.
    """

    def __init__(self, provider=None) -> None:
        self._provider = provider
        self._prompt_template = self._load_prompt()

    @staticmethod
    def _load_prompt() -> str:
        if _PROMPT_PATH.exists():
            return _PROMPT_PATH.read_text(encoding="utf-8")
        return "Score applicability of {method_name} to {dataset_name}. Return JSON: {\"applicability_score\": float, \"reasoning\": str, \"estimated_improvement\": str}"

    def find_gaps(self, claims: list[Claim]) -> list[MethodProblemGap]:
        """Sync wrapper — calls async implementation."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already inside an event loop — run synchronously without LLM
            return self._find_gaps_sync(claims)
        else:
            return asyncio.run(self._find_gaps_async(claims))

    async def _find_gaps_async(self, claims: list[Claim]) -> list[MethodProblemGap]:
        """Async implementation with LLM scoring."""
        if not claims:
            return []

        methods, datasets, known_pairs = self._extract_methods_datasets(claims)
        if not methods or not datasets:
            return []

        gaps: list[MethodProblemGap] = []
        for method_name, paper_id in methods:
            for dataset in datasets:
                pair = (method_name.lower(), dataset.lower())
                if pair not in known_pairs:
                    if self._provider is not None:
                        score = await self._score_gap_llm(method_name, dataset)
                    else:
                        score = 0.5
                    if score > 0:
                        gaps.append(MethodProblemGap(
                            method_name=method_name,
                            method_paper_id=paper_id,
                            problem_dataset=dataset,
                            applicability_score=score,
                            reasoning=f"{method_name} has not been applied to {dataset}",
                        ))

        return sorted(gaps, key=lambda g: g.applicability_score, reverse=True)

    def _find_gaps_sync(self, claims: list[Claim]) -> list[MethodProblemGap]:
        """Sync fallback when already inside an event loop."""
        methods, datasets, known_pairs = self._extract_methods_datasets(claims)
        if not methods or not datasets:
            return []

        gaps: list[MethodProblemGap] = []
        for method_name, paper_id in methods:
            for dataset in datasets:
                pair = (method_name.lower(), dataset.lower())
                if pair not in known_pairs:
                    gaps.append(MethodProblemGap(
                        method_name=method_name,
                        method_paper_id=paper_id,
                        problem_dataset=dataset,
                        applicability_score=0.5,
                        reasoning=f"{method_name} has not been applied to {dataset}",
                    ))
        return sorted(gaps, key=lambda g: g.applicability_score, reverse=True)

    @staticmethod
    def _extract_methods_datasets(claims: list[Claim]):
        """Extract methods, datasets, and known pairs from claims."""
        methods: list[tuple[str, str]] = []
        datasets: set[str] = set()
        known_pairs: set[tuple[str, str]] = set()

        for claim in claims:
            if claim.claim_type == ClaimType.METHOD and claim.method_name:
                methods.append((claim.method_name, claim.source_paper_id))
            elif claim.claim_type == ClaimType.RESULT and claim.dataset:
                datasets.add(claim.dataset)
                if claim.method_name:
                    known_pairs.add((claim.method_name.lower(), claim.dataset.lower()))

        return methods, datasets, known_pairs

    async def _score_gap_llm(self, method_name: str, dataset: str) -> float:
        """Use LLM to score applicability. Returns 0.5 on failure."""
        try:
            prompt = self._prompt_template.replace("{method_name}", method_name).replace("{dataset_name}", dataset)
            messages = [{"role": "user", "content": prompt}]
            response = await self._provider.complete(messages, temperature=0.1, max_tokens=256)

            response_text = response.strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            result = json.loads(response_text)
            score = float(result.get("applicability_score", 0.5))
            return max(0.0, min(1.0, score))

        except Exception as e:
            logger.warning("LLM applicability scoring failed: %s", e)
            return 0.5
