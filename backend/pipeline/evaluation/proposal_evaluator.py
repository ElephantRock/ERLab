"""Multi-dimensional proposal evaluation.

Scores proposals on 5 dimensions: Novelty, Feasibility, Completeness,
Rigor, Clarity. Each dimension gets a 0-1 score with written justification.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "evaluation.md"

DIMENSIONS = ["novelty", "feasibility", "completeness", "rigor", "clarity", "baseline_adequacy", "compute_realism"]


@dataclass
class DimensionScore:
    """Score and justification for a single evaluation dimension."""
    score: float = 0.0
    justification: str = ""

    def __post_init__(self):
        self.score = max(0.0, min(1.0, self.score))


@dataclass
class ProposalEvaluation:
    """Full 7-dimension evaluation of a research proposal."""
    novelty: DimensionScore = field(default_factory=DimensionScore)
    feasibility: DimensionScore = field(default_factory=DimensionScore)
    completeness: DimensionScore = field(default_factory=DimensionScore)
    rigor: DimensionScore = field(default_factory=DimensionScore)
    clarity: DimensionScore = field(default_factory=DimensionScore)
    baseline_adequacy: DimensionScore = field(default_factory=DimensionScore)
    compute_realism: DimensionScore = field(default_factory=DimensionScore)
    overall: float = 0.0

    def to_dict(self) -> dict:
        return {
            "novelty": {"score": self.novelty.score, "justification": self.novelty.justification},
            "feasibility": {"score": self.feasibility.score, "justification": self.feasibility.justification},
            "completeness": {"score": self.completeness.score, "justification": self.completeness.justification},
            "rigor": {"score": self.rigor.score, "justification": self.rigor.justification},
            "clarity": {"score": self.clarity.score, "justification": self.clarity.justification},
            "baseline_adequacy": {"score": self.baseline_adequacy.score, "justification": self.baseline_adequacy.justification},
            "compute_realism": {"score": self.compute_realism.score, "justification": self.compute_realism.justification},
            "overall": self.overall,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProposalEvaluation:
        def _ds(d):
            if isinstance(d, dict):
                return DimensionScore(score=d.get("score", 0.0), justification=d.get("justification", ""))
            return DimensionScore()
        return cls(
            novelty=_ds(data.get("novelty", {})),
            feasibility=_ds(data.get("feasibility", {})),
            completeness=_ds(data.get("completeness", {})),
            rigor=_ds(data.get("rigor", {})),
            clarity=_ds(data.get("clarity", {})),
            baseline_adequacy=_ds(data.get("baseline_adequacy", {})),
            compute_realism=_ds(data.get("compute_realism", {})),
            overall=data.get("overall", 0.0),
        )


class ProposalEvaluator:
    """Evaluates research proposals on 5 dimensions using LLM."""

    def __init__(self, provider: Any = None) -> None:
        self._provider = provider
        self._system_prompt = self._load_prompt()

    @staticmethod
    def _load_prompt() -> str:
        if _PROMPT_PATH.exists():
            return _PROMPT_PATH.read_text(encoding="utf-8")
        return "Evaluate the proposal on 5 dimensions: Novelty, Feasibility, Completeness, Rigor, Clarity."

    async def evaluate(self, proposal_text: str) -> ProposalEvaluation:
        """Evaluate a proposal on 5 dimensions.

        Returns:
            ProposalEvaluation with scores and justifications.
            Returns default evaluation if provider is unavailable.
        """
        if self._provider is None or not proposal_text:
            return ProposalEvaluation()

        user_prompt = f"Evaluate the following research proposal:\n\n{proposal_text[:8000]}"

        try:
            response = await self._provider.complete(
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=1500,
            )
        except TimeoutError:
            logger.warning("LLM timeout during proposal evaluation — returning default scores")
            return ProposalEvaluation()
        except Exception as e:
            logger.warning("LLM error during proposal evaluation: %s — returning default", e)
            return ProposalEvaluation()

        return self._parse_response(response)

    @staticmethod
    def _parse_response(text: str) -> ProposalEvaluation:
        """Parse structured 5-dimension evaluation from LLM response."""
        scores = {}
        justifications = {}

        for dim in DIMENSIONS:
            score_match = re.search(
                rf"{dim}_SCORE:\s*([\d.]+)", text, re.IGNORECASE
            )
            if score_match:
                try:
                    scores[dim] = float(score_match.group(1))
                except ValueError:
                    scores[dim] = 0.0

            just_match = re.search(
                rf"{dim}_JUSTIFICATION:\s*(.+?)(?=\w+_SCORE:|\w+_JUSTIFICATION:|OVERALL_SCORE:|$)",
                text, re.IGNORECASE | re.DOTALL,
            )
            if just_match:
                justifications[dim] = just_match.group(1).strip()

        overall = 0.0
        overall_match = re.search(r"OVERALL_SCORE:\s*([\d.]+)", text, re.IGNORECASE)
        if overall_match:
            try:
                overall = float(overall_match.group(1))
            except ValueError:
                overall = 0.0

        if not overall and scores:
            overall = sum(scores.values()) / len(scores) if scores else 0.0

        return ProposalEvaluation(
            novelty=DimensionScore(score=scores.get("novelty", 0.0), justification=justifications.get("novelty", "")),
            feasibility=DimensionScore(score=scores.get("feasibility", 0.0), justification=justifications.get("feasibility", "")),
            completeness=DimensionScore(score=scores.get("completeness", 0.0), justification=justifications.get("completeness", "")),
            rigor=DimensionScore(score=scores.get("rigor", 0.0), justification=justifications.get("rigor", "")),
            clarity=DimensionScore(score=scores.get("clarity", 0.0), justification=justifications.get("clarity", "")),
            baseline_adequacy=DimensionScore(score=scores.get("baseline_adequacy", 0.0), justification=justifications.get("baseline_adequacy", "")),
            compute_realism=DimensionScore(score=scores.get("compute_realism", 0.0), justification=justifications.get("compute_realism", "")),
            overall=overall,
        )
