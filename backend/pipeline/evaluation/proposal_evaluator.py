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


class UnusableEvaluationResponseError(RuntimeError):
    """Raised when the model response cannot yield a usable evaluation.

    B-EVAL-01 (defect F-4): on v1.0.1 an empty or unparseable model response
    silently produced an all-zero / empty-justification ProposalEvaluation.
    Callers (pipeline stages) already wrap evaluate() in try/except and store
    an honest "Evaluation failed" label; raising here ensures that branch
    fires instead of persisting silent zeros.
    """

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
            msgs = [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            # B-COST-01: prefer the usage-enabled path so this provider call
            # reports token usage and cost through _report_cost. Falls back to
            # complete() for providers that do not implement complete_with_usage.
            if hasattr(self._provider, "complete_with_usage"):
                resp = await self._provider.complete_with_usage(
                    msgs, max_tokens=1500, stage="proposal_evaluation",
                )
                response = resp.content if hasattr(resp, "content") else str(resp)
            else:
                response = await self._provider.complete(msgs, max_tokens=1500)
        except TimeoutError:
            logger.warning("LLM timeout during proposal evaluation — returning default scores")
            return ProposalEvaluation()
        except Exception as e:
            logger.warning("LLM error during proposal evaluation: %s — returning default", e)
            return ProposalEvaluation()

        # B-EVAL-01: reject empty/whitespace-only responses explicitly rather
        # than silently persisting an all-zero evaluation. Captured GLM-4.6
        # behavior confirmed the model intermittently returns "" on some calls.
        if not response or not response.strip():
            raise UnusableEvaluationResponseError(
                "model returned an empty response; cannot produce a usable evaluation"
            )

        return self._parse_response(response)

    @staticmethod
    def _parse_response(text: str) -> ProposalEvaluation:
        """Parse structured 5-dimension evaluation from LLM response.

        Raises UnusableEvaluationResponseError when the response is non-empty
        but yields zero parseable dimensions (B-EVAL-01): a response that
        matches none of the DIM_SCORE patterns cannot produce a usable
        evaluation and must not silently persist as all-zeros.
        """
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

        # B-EVAL-01: a non-empty response that matched no dimension scores is
        # unusable. Raise rather than persist silent zeros. Partial parses
        # (some dimensions present) remain valid and return normally.
        if not scores:
            preview = (text or "").strip().replace("\n", " ")[:120]
            raise UnusableEvaluationResponseError(
                f"model response matched no dimension scores; cannot produce a "
                f"usable evaluation. response preview: {preview!r}"
            )

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
