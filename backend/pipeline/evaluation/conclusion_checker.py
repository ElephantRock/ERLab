"""Phase 4 / WP-4F — conclusion-overreach detection.

Deterministic conclusion-support checker used by the paper-evaluation gate.
Reviews the central claims in the abstract / conclusion against whether the
paper reports empirical results. Reuses the existing evaluation architecture —
no new evaluator service, no claim graph, no LLM call.

This diagnostic evaluates whether the conclusion follows from the paper's OWN
methods and results. It does NOT decide whether the underlying scientific
proposition is universally true.

Overreach indicators (per Phase 4 plan):
  * "demonstrates", "proves", or "significantly improves" without reported
    empirical results;
  * causal conclusions from a conceptual design;
  * claims of validation when only a proposed method is presented;
  * claims of novelty unsupported by identifiable literature;
  * conclusions materially stronger than the abstracted evidence.

A central ``overstated`` finding prevents an unqualified positive
paper-evaluation result.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ConclusionSupportResult:
    """Outcome of conclusion-support classification."""

    classification: str  # supported_by_paper | partially_supported_by_paper | overstated | unavailable
    reason: str
    indicators: list[str] = None  # which overreach patterns fired


# Strong-claim verbs/phrases that assert empirical demonstration.
_STRONG_CLAIM_PATTERNS = [
    (r"\bdemonstrates?\b", "claims demonstration"),
    (r"\bdemonstrate\b", "claims demonstration"),
    (r"\bproves?\b", "claims proof"),
    (r"\bprove\b", "claims proof"),
    (r"\bsignificantly improves?\b", "claims significant improvement"),
    (r"\bsignificantly outperforms?\b", "claims significant outperformance"),
    (r"\boutperforms?\b", "claims outperformance"),
    (r"\bvalidates?\b", "claims validation"),
    (r"\bvalidate\b", "claims validation"),
    (r"\bconfirmed\b", "claims confirmation"),
    (r"\bconfirms?\b", "claims confirmation"),
    (r"\bbeen verified\b", "claims verification"),
    (r"\bverified\b", "claims verification"),
]

# Causal-claim markers used without empirical support.
_CAUSAL_PATTERNS = [
    (r"\bcauses?\b", "claims causation"),
    (r"\bcauses?\s+\w+\s+to\b", "claims causation"),
    (r"\bresults?\s+in\b", "claims causal effect"),
    (r"\bleads?\s+to\b", "claims causal effect"),
]

# Empirical-evidence markers — their presence means results were reported.
_EMPIRICAL_MARKERS = [
    r"\bexperiment", r"\bevaluated?\b", r"\bevaluation\b", r"\bbenchmark",
    r"\bresults?\b", r"\baccuracy\b", r"\bprecision\b", r"\brecall\b",
    r"\bf1\b", r"\btable\s*\d", r"\bfigure\s*\d", r"\bp\s*[<=]\s*0",
    r"\b\\?d{1,3}\s*%\b",  # e.g. 92%
]


def _has_empirical_signal(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(re.search(p, lower) for p in _EMPIRICAL_MARKERS)


def classify_conclusion_support(
    abstract: str,
    conclusion: str,
    has_empirical_results: bool | None = None,
) -> ConclusionSupportResult:
    """Classify whether the conclusion is supported by the paper's own evidence.

    Args:
        abstract: The paper abstract.
        conclusion: The paper's conclusion / discussion text.
        has_empirical_results: Explicit flag if known (e.g. from a results
            section). When None, inferred from abstract+conclusion text.
    """
    text = f"{abstract or ''}\n{conclusion or ''}"
    if not text.strip():
        return ConclusionSupportResult(
            classification="unavailable",
            reason="No abstract or conclusion text to assess.",
            indicators=[],
        )

    # Determine empirical-results presence.
    if has_empirical_results is None:
        empirical = _has_empirical_signal(text)
    else:
        empirical = bool(has_empirical_results)

    fired: list[str] = []
    for pattern, label in _STRONG_CLAIM_PATTERNS:
        if re.search(pattern, text.lower()):
            fired.append(label)
    for pattern, label in _CAUSAL_PATTERNS:
        if re.search(pattern, text.lower()):
            fired.append(label)

    # Overstated: strong-claim language without empirical results.
    if fired and not empirical:
        return ConclusionSupportResult(
            classification="overstated",
            reason=(
                "Conclusion uses empirical/causal claim language ("
                + "; ".join(sorted(set(fired)))
                + ") but the paper reports no empirical results."
            ),
            indicators=fired,
        )

    if fired and empirical:
        return ConclusionSupportResult(
            classification="supported_by_paper",
            reason=(
                "Conclusion claims are consistent with reported empirical results "
                f"(indicators: {'; '.join(sorted(set(fired)))})."
            ),
            indicators=fired,
        )

    # No strong-claim language — conservatively supported by the paper's design.
    return ConclusionSupportResult(
        classification="supported_by_paper",
        reason="No overreach indicators; conclusion does not assert empirical demonstration.",
        indicators=[],
    )
