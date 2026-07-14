"""STOPGAP: side-channel quarantine, render-at-read-time.

This module routes around the absence of an ownership contract on
``proposal.sections``. It does NOT mutate ``sections`` — that substrate is read
by post-audit generation stages (ProposalDeepeningStage feeds section prose to
an LLM, and any inline editorial marker is a gap a generation model may fill
back in). Instead, fabricated citations are recorded as structured data and
substituted with a display marker only at read time, by this function.

Why not mutate sections (the decision this module exists because of):
  - ProposalDeepeningStage reads ``sections["introduction"]`` as prose and
    passes it to an LLM. An inline marker (however inert to every regex) is an
    editorial gap that a generation model may "helpfully" reconstruct into a
    real-looking citation. That risk is not fixable by marker syntax — it's an
    LLM-behavior problem, not a regex problem.
  - The section-refine endpoint computes a content hash against ``sections``
    for optimistic concurrency. Mutating sections under quarantine would cause
    spurious 409s for any reviewer whose tab predates the audit.
  - compute_quality_checks / remediation hints read ``sections``; mutation
    could silently shift word counts and structural findings mid-review.

The quarantine records live in the ``QuarantinedCitation`` table (append-only,
matching the pattern of ProposalSectionRevision and GovernanceDecision). This
function accepts either ORM rows or plain dicts so it's testable without a DB.

Idempotent and pure: same inputs → same output, every time, and the input
dict is never mutated (a fresh dict is returned). Where a citation no longer
exists in the current text (e.g. removed by a human refine since the audit
ran), the record becomes a no-op — the audit finding remains historically
accurate, the render reflects current text.
"""

from __future__ import annotations

import re
from typing import Any

_SOURCE_PATTERN = re.compile(r"\[SOURCE-(\d+)\]")

DEFAULT_DISPLAY_MARKER = "[removed: fabricated reference]"


def render_quarantined_view(
    sections: dict[str, Any],
    quarantined: list,
    display_marker: str = DEFAULT_DISPLAY_MARKER,
) -> dict[str, Any]:
    """Substitute fabricated citations with a display marker.

    Args:
        sections: the raw ``sections_json`` dict (or ``proposal.sections``).
            Never mutated; a fresh dict is returned.
        quarantined: list of QuarantinedCitation ORM rows OR plain dicts,
            each with at least ``section_key`` and ``ref_index``. Other keys
            (proposal_id, audit_run_id, created_at) are ignored.
        display_marker: the text to substitute for each fabricated citation.
            Defaults to ``"[removed: fabricated reference]"``.

    Returns:
        A new dict of the same shape as ``sections``, with fabricated
        ``[SOURCE-N]`` markers replaced by ``display_marker``. Valid
        citations and non-string values are passed through unchanged.

    The substitution is by pattern match against the *current* section text at
    render time, not by stored character offset. If a human refine has removed
    the citation since the audit ran, the marker is gone, the pattern doesn't
    match, nothing is substituted — the quarantine record is inert. This means
    the render always reflects the current text; the append-only record is the
    historical truth.
    """
    if not quarantined:
        return dict(sections)

    by_section: dict[str, set[int]] = {}
    for record in quarantined:
        section_key = _get(record, "section_key")
        ref_index = _get(record, "ref_index")
        if section_key is None or ref_index is None:
            continue
        by_section.setdefault(section_key, set()).add(int(ref_index))

    rendered = dict(sections)
    for section_name, fabricated_indices in by_section.items():
        text = rendered.get(section_name)
        if not isinstance(text, str):
            continue

        def _sub(match: re.Match, _fabricated=fabricated_indices) -> str:
            idx = int(match.group(1))
            return display_marker if idx in _fabricated else match.group(0)

        rendered[section_name] = _SOURCE_PATTERN.sub(_sub, text)

    return rendered


def _get(record: Any, key: str) -> Any:
    """Read a key from an ORM row or a plain dict, uniformly."""
    if isinstance(record, dict):
        return record.get(key)
    return getattr(record, key, None)
