"""Phase 4 / WP-4F — conclusion-overreach detection.

Deterministic conclusion-support checker used by the paper-evaluation gate.
Reviews the central claims in the abstract + conclusion against whether the
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

4F repair (2026-07-28): the checker now:
  * scans abstract AND conclusion (already concatenated, but the calling code
    sometimes failed to extract the abstract);
  * excludes attributed demonstrations ("[SOURCE-N] demonstrates") so cited
    papers' results are not flagged as the paper's own claims;
  * distinguishes "expected results" / "results indicate" (speculation) from
    actual reported results (measurements, tables, accuracy scores);
  * detects empirical-assertion phrases like "experimental results indicate"
    and "experimental validation demonstrates" as overreach when no actual
    empirical methods are reported.
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


# Phrases that assert empirical demonstration by the PAPER ITSELF.
# These are stronger than individual words — they assert completed empirical work.
# Patterns are matched AFTER stripping attributed claims and hedging context.
_SELF_EMPIRICAL_ASSERTION_PATTERNS = [
    (r"\bwe\s+demonstrate\b", "self-claim: 'we demonstrate'"),
    (r"\bdemonstrates?\s+that\b", "claims demonstration"),
    (r"\bdemonstrate\s+that\b", "claims demonstration"),
    (r"\bexperimental\s+results?\b.{0,40}\b(show|indicate|demonstrate|reveal|suggest)\b", "claims experimental results"),
    (r"\bexperimental\s+validation\b.{0,40}\b(demonstrates?|shows?|confirms?)\b", "claims experimental validation"),
    (r"\bwe\s+show\s+that\b", "self-claim: 'we show that'"),
    (r"\bresults?\s+(show|indicate|demonstrate|confirm|reveal)\s+that\b", "claims results demonstrate"),
    (r"\bsignificantly\s+(improves?|outperforms?)\b", "claims significant improvement/outperformance"),
    (r"\bsignificantly\s+reduces?\s+(overhead|cost|error|latency|time|convergence|gap)\b", "claims significant reduction in performance metric"),
    (r"\bwe\s+confirm(ed)?\b", "self-claim: 'we confirm'"),
    (r"\bvalidation\s+(demonstrates?|shows?|confirms?)\b", "claims validation"),
]

# Individual strong-claim verbs (fallback for less common phrasings).
_STRONG_CLAIM_VERBS = [
    (r"\bproves?\b", "claims proof"),
    (r"\bprove\b", "claims proof"),
    (r"\boutperforms?\b", "claims outperformance"),
    (r"\bverified\b", "claims verification"),
    (r"\bbeen\s+verified\b", "claims verification"),
]

# Causal-claim markers used without empirical support.
_CAUSAL_PATTERNS = [
    (r"\bcauses?\b", "claims causation"),
    (r"\bresults?\s+in\b", "claims causal effect"),
    (r"\bleads?\s+to\b", "claims causal effect"),
]

# Empirical-evidence markers that indicate ACTUAL reported results (not
# speculation about expected results). These are specific enough to distinguish
# "we report 92% accuracy on benchmark X" from "we expect results to improve."
_ACTUAL_RESULTS_MARKERS = [
    r"\baccuracy\s+(of|was|is|=)\s*\d",      # accuracy of 92%
    r"\b\d{1,3}\.\d+\s*%\b",                  # 92.3%
    r"\b\d{1,3}\s*%\s*(accuracy|precision|recall|f1|improvement)\b",
    r"\bp\s*[<=]\s*0\.\d",                    # p < 0.05
    r"\btable\s*\d",                          # Table 1
    r"\bfigure\s*\d",                         # Figure 3
    r"\bmean\s+(accuracy|score|precision)\b",
    r"\bstd\s*dev\b",
    r"\bconfidence\s+interval\b",
    r"\bablation\s+(study|result)\b",
    r"\bwe\s+(trained|fine-tuned|evaluated)\b",  # we trained/evaluated
    r"\bon\s+(the\s+)?(test|validation)\s+set\b",
    r"\bbaseline\s+(achieved|scored|reached)\b",
]

# Phrases that HEDGE claims (speculation, not assertion).
_HEDGE_PATTERNS = [
    r"\bexpected\s+results?\b",
    r"\bwe\s+(expect|anticipate|hypothesize|envision|believe)\b",
    r"\bpotentially\b",
    r"\bpromises?\b",
    r"\bcould\s+(achieve|improve|reduce)\b",
    r"\bmay\s+(achieve|improve|reduce)\b",
    r"\bfuture\s+work\b",
    r"\bif\s+successful\b",
]


def _has_actual_results(text: str) -> bool:
    """Check for ACTUAL reported results (not speculation).

    Distinguishes "we report 92% accuracy" from "we expect results to improve."
    """
    if not text:
        return False
    lower = text.lower()
    return any(re.search(p, lower) for p in _ACTUAL_RESULTS_MARKERS)


def _strip_attributed_claims(text: str) -> str:
    """Remove sentences where a SOURCE is the subject of 'demonstrate'.

    "[SOURCE-3] demonstrates X" is the cited paper's claim, not this paper's.
    We remove these so the checker doesn't flag them as the paper's own assertions.
    """
    # Remove sentences starting with [SOURCE-N] + demonstrate/show/validate
    text = re.sub(
        r'\[SOURCE-\d+\]\s+(demonstrates?|shows?|validates?|confirms?|proves?)\b[^.]*\.',
        '',
        text,
    )
    # Remove "As [SOURCE-N] demonstrates..."
    text = re.sub(
        r'[Aa]s\s+\[SOURCE-\d+\]\s+(demonstrates?|shows?|validates?)\b[^.]*\.',
        '',
        text,
    )
    # Remove author-year attributions: "Smith et al. (2024) demonstrate..."
    text = re.sub(
        r'\b[A-Z]\w+\s+et\s+al\.\s*\(\d{4}\)\s+(demonstrates?|shows?|validates?|proves?)\b[^.]*\.',
        '',
        text,
    )
    return text


def _strip_hedged_demonstrations(text: str) -> str:
    """Remove hedged demonstration claims so they don't fire the self-claim patterns.

    "We expect to demonstrate that..." is properly hedged and should NOT be
    flagged as an overstatement. We remove the "demonstrate that" from these
    hedged contexts before pattern matching.
    """
    # "expect to demonstrate", "hope to demonstrate", "aim to demonstrate"
    text = re.sub(
        r'\b(expect|hope|aim|plan|intend)\s+to\s+(demonstrate|show|validate|confirm)\b',
        r'\\1 to \\2',
        text,
        flags=re.IGNORECASE,
    )
    # "expected results demonstrate" → "expected results indicate" (hedged)
    text = re.sub(
        r'\bexpected\s+results?\s+(demonstrate|show|confirm)\b',
        'expected results indicate',
        text,
        flags=re.IGNORECASE,
    )
    # "potentially demonstrates" / "could demonstrate"
    text = re.sub(
        r'\b(potentially|could|may|might)\s+(demonstrate|show|validate|confirm)\b',
        r'\\1 suggest',
        text,
        flags=re.IGNORECASE,
    )
    return text


def _is_hedged(text: str) -> bool:
    """Check whether the text uses hedging language for its claims."""
    if not text:
        return False
    lower = text.lower()
    return bool(re.search("|".join(_HEDGE_PATTERNS), lower))


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

    The checker scans BOTH abstract and conclusion. It distinguishes:
      * self-claims ("we demonstrate") from attributed claims ("[SOURCE-N]
        demonstrates") — only self-claims are flagged;
      * actual reported results (accuracy scores, tables) from speculative
        results ("expected results", "we hypothesize") — only actual results
        justify empirical assertions.
    """
    raw_text = f"{abstract or ''}\n{conclusion or ''}"
    if not raw_text.strip():
        return ConclusionSupportResult(
            classification="unavailable",
            reason="No abstract or conclusion text to assess.",
            indicators=[],
        )

    # Strip attributed claims so cited papers' demonstrations aren't flagged.
    text = _strip_attributed_claims(raw_text)
    # Strip hedged demonstrations so "expect to demonstrate" isn't flagged.
    text = _strip_hedged_demonstrations(text)

    # Determine empirical-results presence.
    if has_empirical_results is None:
        empirical = _has_actual_results(raw_text)
    else:
        empirical = bool(has_empirical_results)

    # Detect self-claims and strong verbs in the (stripped) text.
    fired: list[str] = []
    for pattern, label in _SELF_EMPIRICAL_ASSERTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            fired.append(label)
    for pattern, label in _STRONG_CLAIM_VERBS:
        if re.search(pattern, text, re.IGNORECASE):
            fired.append(label)
    for pattern, label in _CAUSAL_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            fired.append(label)

    # Overstated: self-claim empirical language without actual results.
    if fired and not empirical:
        return ConclusionSupportResult(
            classification="overstated",
            reason=(
                "Abstract/conclusion uses empirical/causal claim language ("
                + "; ".join(sorted(set(fired)))
                + ") but the paper reports no empirical results."
            ),
            indicators=fired,
        )

    if fired and empirical:
        return ConclusionSupportResult(
            classification="supported_by_paper",
            reason=(
                "Claims are consistent with reported empirical results "
                f"(indicators: {'; '.join(sorted(set(fired)))})."
            ),
            indicators=fired,
        )

    # No strong-claim language — conservatively supported by the paper's design.
    return ConclusionSupportResult(
        classification="supported_by_paper",
        reason="No overreach indicators; abstract/conclusion does not assert empirical demonstration.",
        indicators=[],
    )
