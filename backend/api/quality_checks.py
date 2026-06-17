"""Deterministic quality checks for persisted proposal sections.

Computes the same checks that ProposalSynthesizer._refine_sections runs
(word-count thresholds + pattern checklist), but at read time against the
persisted ``sections_json``.  This means every proposal — including ones
generated before this module existed — gets a quality report without
re-running the pipeline.

The thresholds and patterns are imported from the synthesizer so they
stay in sync automatically.
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
