"""Deterministic quality checks for persisted proposal sections.

Computes the same checks that ProposalSynthesizer._refine_sections runs
(word-count thresholds + pattern checklist), but at read time against the
persisted ``sections_json``.  This means every proposal — including ones
generated before this module existed — gets a quality report without
re-running the pipeline.

The thresholds and patterns are imported from the synthesizer so they
stay in sync automatically.

This module also provides:
- ``compute_remediation_hints()`` — actionable, deterministic suggestions
  for each failing quality check.
- ``audit_citations()`` — per-section citation health metrics including
  ``[Citation needed]`` detection and resolved/unresolved reference counts.
"""

from __future__ import annotations

import re
from typing import Any

from backend.pipeline.synthesis.proposal_synthesizer import MIN_WORDS, SECTION_CHECKLIST

# Sections that are prose and therefore subject to word-count checks.
# ``references``, ``title``, and ``ensemble_review`` are excluded.
_PROSE_SECTIONS = set(MIN_WORDS.keys())


def _word_count(value: Any) -> int:
    """Word count for a section value (str, list, or dict)."""
    if isinstance(value, str):
        return len(value.split())
    if isinstance(value, list):
        total = 0
        for item in value:
            if isinstance(item, str):
                total += len(item.split())
            elif isinstance(item, dict):
                total += sum(len(str(v).split()) for v in item.values())
        return total
    if isinstance(value, dict):
        return sum(len(str(v).split()) for v in value.values())
    return 0


def compute_quality_checks(
    sections: dict[str, Any] | None,
) -> list[dict[str, Any]] | None:
    """Run deterministic quality checks on persisted proposal sections.

    Args:
        sections: The ``sections_json`` dict from the Proposal model.

    Returns:
        A list of per-section check results, or ``None`` if *sections*
        is falsy.  Each entry has the shape::

            {
                "section": "proposed_method",
                "label": "Proposed Method",
                "present": True,
                "word_count": 850,
                "min_words": 600,
                "meets_word_count": True,
                "checks": [
                    {"name": "formal loss function", "passed": True},
                    ...
                ],
                "passed": True,          # all checks + word count
                "failures": ["word count 50 < 150"],
            }
    """
    if not sections or not isinstance(sections, dict):
        return None

    results: list[dict[str, Any]] = []

    for key, min_words in MIN_WORDS.items():
        value = sections.get(key)
        present = value is not None and (
            (isinstance(value, str) and value.strip() != "")
            or (isinstance(value, (list, dict)) and len(value) > 0)
        )
        wc = _word_count(value) if present else 0
        meets_wc = wc >= min_words

        check_results: list[dict[str, Any]] = []
        failures: list[str] = []

        # Word-count check
        if present and not meets_wc:
            failures.append(f"word count {wc} < {min_words}")

        # Pattern checklist (only for present string sections)
        for pattern, description in SECTION_CHECKLIST.get(key, []):
            text = value if isinstance(value, str) else str(value)
            passed = bool(re.search(pattern, text, re.IGNORECASE | re.DOTALL))
            check_results.append({"name": description, "passed": passed})
            if present and not passed:
                failures.append(f"missing {description}")

        all_passed = present and meets_wc and len(failures) == 0

        results.append({
            "section": key,
            "label": key.replace("_", " ").title(),
            "present": present,
            "word_count": wc,
            "min_words": min_words,
            "meets_word_count": meets_wc,
            "checks": check_results,
            "passed": all_passed,
            "failures": failures,
        })

    return results


# --------------------------------------------------------------------------- #
# Remediation hints — deterministic suggestions for failing checks
# --------------------------------------------------------------------------- #

# Maps (section_key, failure_substring) → specific suggestion.
# The failure_substring is matched case-insensitively against the
# ``failures`` list entry produced by ``compute_quality_checks``.
_HINTS: dict[str, dict[str, str]] = {
    "related_work": {
        "citation markers": (
            "Add inline references like [1], [SOURCE-N], or (Author, Year) "
            "to support claims about prior work."
        ),
    },
    "proposed_method": {
        "formal loss function": (
            "Add a display equation ($$...$$) defining the training objective "
            "or loss function."
        ),
        "training objective": (
            "Explicitly state the loss function or optimization objective "
            "(e.g., cross-entropy, contrastive loss)."
        ),
        "mathematical notation": (
            "Add inline math notation ($...$) for key variables, formulas, "
            "or model dimensions."
        ),
        "computational requirements": (
            "Estimate GPU type, count, or GPU-hours needed for training."
        ),
    },
    "introduction": {
        "contributions statement": (
            "Add a sentence starting with 'Our contributions' or 'We propose' "
            "to clearly state what this paper contributes."
        ),
    },
    "evaluation_plan": {
        "named baselines": (
            "Name at least one baseline model for comparison (e.g., vanilla "
            "transformer, linear probe)."
        ),
        "naive cross-domain": (
            "Include a naive cross-domain baseline (training without domain "
            "alignment) to show the value of your approach."
        ),
        "ablation": (
            "Add an ablation experiment that removes a key component to "
            "measure its contribution."
        ),
        "evaluation metrics": (
            "Specify evaluation metrics (e.g., accuracy, F1, BLEU) for "
            "quantitative comparison."
        ),
    },
    "timeline": {
        "compute budget": (
            "Include a compute budget or model size estimate (e.g., 8×A100, "
            "7B parameters) to justify feasibility."
        ),
    },
}

# Generic word-count suggestion per section type.
_WORD_COUNT_HINT = (
    "Expand this section — it has {actual} words but needs at least "
    "{minimum}. Add more detail, examples, or discussion."
)


def compute_remediation_hints(
    sections: dict[str, Any] | None,
    quality_checks: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]] | None:
    """Generate deterministic, actionable hints for failing quality checks.

    Each hint maps a specific failure to a concrete suggestion the user
    can act on.  No LLM involvement — hints are pure functions of the
    failure type and section key.

    Args:
        sections: The ``sections_json`` dict (used to compute checks if
            ``quality_checks`` is not provided).
        quality_checks: Pre-computed quality check results. If omitted,
            they are computed from ``sections``.

    Returns:
        List of hint dicts, or ``None`` if no sections exist. Shape::

            {
                "section": "related_work",
                "label": "Related Work",
                "issue_type": "missing_pattern",
                "severity": "warning",
                "message": "missing citation markers",
                "suggestion": "Add inline references like ...",
                "refinement_available": True,
            }
    """
    if quality_checks is None:
        quality_checks = compute_quality_checks(sections)
    if not quality_checks:
        return None

    hints: list[dict[str, Any]] = []

    for check in quality_checks:
        if check["passed"]:
            continue

        key = check["section"]
        label = check["label"]
        section_hints = _HINTS.get(key, {})

        if not check["present"]:
            # Missing entirely
            hints.append({
                "section": key,
                "label": label,
                "issue_type": "missing_section",
                "severity": "error",
                "message": "Section not present in proposal",
                "suggestion": (
                    f"The {label} section is missing entirely. "
                    "It should be generated as part of the proposal."
                ),
                "refinement_available": True,
            })
            continue

        for failure in check["failures"]:
            failure_lower = failure.lower()

            if failure_lower.startswith("word count"):
                hints.append({
                    "section": key,
                    "label": label,
                    "issue_type": "word_count",
                    "severity": "warning",
                    "message": failure,
                    "suggestion": _WORD_COUNT_HINT.format(
                        actual=check["word_count"],
                        minimum=check["min_words"],
                    ),
                    "refinement_available": True,
                })
                continue

            # Look for a specific hint for this failure
            matched = False
            for pattern_key, suggestion in section_hints.items():
                if pattern_key.lower() in failure_lower:
                    hints.append({
                        "section": key,
                        "label": label,
                        "issue_type": "missing_pattern",
                        "severity": "warning",
                        "message": failure,
                        "suggestion": suggestion,
                        "refinement_available": True,
                    })
                    matched = True
                    break

            if not matched:
                # Generic fallback for unmapped failures
                hints.append({
                    "section": key,
                    "label": label,
                    "issue_type": "missing_pattern",
                    "severity": "warning",
                    "message": failure,
                    "suggestion": (
                        f"Address the following issue in {label}: {failure}."
                    ),
                    "refinement_available": True,
                })

    return hints if hints else None


# --------------------------------------------------------------------------- #
# Citation audit — detect [Citation needed] markers and count valid citations
# --------------------------------------------------------------------------- #

# Patterns for valid citation markers
_VALID_CITATION_RE = re.compile(
    r"\[\d+\]"                  # [1] numbered
    r"|\[SOURCE-\d+\]"          # [SOURCE-N]
    r"|\([A-Z][a-z]+[^)]*?\d{4}\)",  # (Author, Year) or (Author et al., Year)
)

_CITATION_NEEDED_RE = re.compile(
    r"\[Citation needed[:\s][^\]]*\]",
    re.IGNORECASE,
)


def audit_citations(
    sections: dict[str, Any] | None,
    proposal_references: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]] | None:
    """Per-section citation health audit.

    Detects ``[Citation needed]`` markers and counts valid citation
    markers. When resolved reference data is available, also reports
    resolved/unresolved reference counts.

    Args:
        sections: The ``sections_json`` dict.
        proposal_references: Optional resolved references list from the
            reference resolver (each entry has ``resolved: bool``).

    Returns:
        List of per-section citation audit entries, or ``None`` if no
        sections exist. Shape::

            {
                "section": "related_work",
                "label": "Related Work",
                "citation_needed_count": 2,
                "valid_citation_count": 3,
                "has_citation_issues": True,
            }

        Plus a summary entry with ``section: "_summary"`` containing
        totals across all sections.
    """
    if not sections or not isinstance(sections, dict):
        return None

    results: list[dict[str, Any]] = []
    total_needed = 0
    total_valid = 0

    for key in MIN_WORDS:
        value = sections.get(key)
        if not isinstance(value, str):
            continue

        needed = len(_CITATION_NEEDED_RE.findall(value))
        valid = len(_VALID_CITATION_RE.findall(value))

        total_needed += needed
        total_valid += valid

        has_issues = needed > 0
        entry: dict[str, Any] = {
            "section": key,
            "label": key.replace("_", " ").title(),
            "citation_needed_count": needed,
            "valid_citation_count": valid,
            "has_citation_issues": has_issues,
        }

        # Add reference resolution info if available
        if key == "related_work" and proposal_references:
            resolved_count = sum(1 for r in proposal_references if r.get("resolved"))
            unresolved_count = len(proposal_references) - resolved_count
            entry["resolved_reference_count"] = resolved_count
            entry["unresolved_reference_count"] = unresolved_count

        results.append(entry)

    # Summary entry
    results.append({
        "section": "_summary",
        "label": "All Sections",
        "citation_needed_count": total_needed,
        "valid_citation_count": total_valid,
        "has_citation_issues": total_needed > 0,
    })

    return results
