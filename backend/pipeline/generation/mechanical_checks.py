"""Fast deterministic quality heuristics for idea candidates.

Runs before expensive LLM critique to catch problems at zero API cost.
Inspired by autonovel's dual evaluation (mechanical + LLM) pattern.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from backend.pipeline.generation.models import IdeaCandidate


class HeuristicResult(BaseModel):
    name: str
    passed: bool
    detail: str


class MechanicalQualityReport(BaseModel):
    heuristic_results: list[HeuristicResult]
    composite_score: float  # 0-1, fraction of heuristics passed
    flagged_issues: list[str]


_GENERIC_TITLE_WORDS = frozenset(
    {
        "novel",
        "new",
        "improved",
        "enhanced",
        "better",
        "efficient",
        "effective",
        "advanced",
        "innovative",
        "unique",
    }
)


def _is_generic_title(title: str) -> bool:
    """True if the title relies only on filler adjectives."""
    words = set(re.findall(r"[a-z]+", title.lower()))
    content_words = words - _GENERIC_TITLE_WORDS
    return len(content_words) < 3


def _jaccard(a: str, b: str) -> float:
    """Word-level Jaccard similarity between two strings."""
    wa = set(re.findall(r"[a-z]+", a.lower()))
    wb = set(re.findall(r"[a-z]+", b.lower()))
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def mechanical_quality_check(idea: IdeaCandidate) -> MechanicalQualityReport:
    """Run deterministic heuristics on an idea candidate.

    Returns a report with pass/fail per heuristic, a composite score,
    and a list of flagged issues to inject into the LLM prompt.
    """
    results: list[HeuristicResult] = []

    # 1. Title specificity — must be >20 chars and not purely generic
    title_ok = len(idea.title) > 20 and not _is_generic_title(idea.title)
    results.append(
        HeuristicResult(
            name="title_specificity",
            passed=title_ok,
            detail="Title is too short or generic" if not title_ok else "OK",
        )
    )

    # 2. Method description length — must be substantive (>50 chars)
    method_ok = len(idea.proposed_method.strip()) > 50
    results.append(
        HeuristicResult(
            name="method_specificity",
            passed=method_ok,
            detail="Method description is too short (<50 chars)" if not method_ok else "OK",
        )
    )

    # 3. Evaluation approach present — must be non-trivial (>20 chars)
    eval_ok = bool(idea.evaluation_approach) and len(idea.evaluation_approach.strip()) > 20
    results.append(
        HeuristicResult(
            name="evaluation_present",
            passed=eval_ok,
            detail="Evaluation approach is missing or trivial" if not eval_ok else "OK",
        )
    )

    # 4. Problem-method overlap — high overlap suggests circular reasoning
    overlap = _jaccard(idea.problem_statement, idea.proposed_method)
    circ_ok = overlap < 0.7
    results.append(
        HeuristicResult(
            name="non_circular",
            passed=circ_ok,
            detail=f"Problem/method overlap too high ({overlap:.0%})" if not circ_ok else "OK",
        )
    )

    # 5. Quantitative claims without metrics — looks for numbers in claims
    #    but no metrics in evaluation
    has_numbers = bool(re.search(r"\d+%|\d+x|\d+ times", idea.expected_contributions.lower()))
    eval_has_metrics = bool(
        idea.evaluation_approach
        and re.search(
            r"\d+%|accuracy|f1|precision|recall|bleu|rouge|score",
            idea.evaluation_approach.lower(),
        )
    )
    quant_ok = not has_numbers or eval_has_metrics
    results.append(
        HeuristicResult(
            name="quantitative_backed",
            passed=quant_ok,
            detail="Quantitative claims lack evaluation metrics" if not quant_ok else "OK",
        )
    )

    passed = sum(1 for r in results if r.passed)
    flagged = [r.detail for r in results if not r.passed]

    return MechanicalQualityReport(
        heuristic_results=results,
        composite_score=passed / len(results),
        flagged_issues=flagged,
    )
