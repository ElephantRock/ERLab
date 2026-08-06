"""Typed read-only views over the production PipelineResult for acceptance.

Acceptance code MUST NOT generate research content. These views only
*inspect* the production result (papers, evaluation, citations, source map,
stage reports, accounting) so the verdict layer can classify gates.

They mirror the dict/JSON-string metadata storage pattern used by the
production proposal metadata (see ProposalSynthesisStage._get_metadata).
"""

from __future__ import annotations

import json
import re
from typing import Any

# The seven canonical paper-evaluation dimensions (ProposalEvaluator).
SEVEN_DIMENSIONS = (
    "novelty", "feasibility", "completeness", "rigor",
    "clarity", "baseline_adequacy", "compute_realism",
)

_SOURCE_MARKER_RE = re.compile(r"\[SOURCE-(\d+)\]")


def load_metadata(proposal: Any) -> dict:
    """Read proposal metadata as a dict, handling JSON-string storage."""
    md = getattr(proposal, "metadata", None)
    if isinstance(md, str):
        try:
            return json.loads(md) or {}
        except (ValueError, TypeError):
            return {}
    if isinstance(md, dict):
        return md
    return {}


class PaperArtifactView:
    """Read-only view over proposal.metadata['full_paper']."""

    def __init__(self, proposal: Any):
        self._md = load_metadata(proposal)
        self._d = self._md.get("full_paper") or {}

    @property
    def exists(self) -> bool:
        return bool(self._d)

    @property
    def paper_markdown(self) -> str:
        return self._d.get("paper_markdown", "") or ""

    @property
    def word_count(self) -> int:
        return int(self._d.get("word_count", 0) or 0)

    @property
    def synthesis_state(self) -> str:
        # Lives at the top metadata level (PaperSynthesisStage sets it there).
        return self._md.get("synthesis_state", "") or self._d.get("synthesis_state", "") or ""

    @property
    def source_map(self) -> list[dict]:
        return list(self._d.get("source_map", []) or [])


class PaperEvaluationView:
    """Read-only view over proposal.metadata['paper_evaluation'].

    The paper-evaluation artifact stores its 7 dimensions under a
    ``dimensions`` sub-dict, plus scope, status, and gates.
    """

    def __init__(self, proposal: Any):
        md = load_metadata(proposal)
        self._d = md.get("paper_evaluation") or md.get("evaluation") or {}
        nested = self._d.get("dimensions")
        self._dims = nested if isinstance(nested, dict) else self._d

    @property
    def exists(self) -> bool:
        return bool(self._d)

    @property
    def scope(self) -> str:
        return self._d.get("scope", "") or ""

    @property
    def status(self) -> str:
        return self._d.get("status", "") or ""

    @property
    def blocking_reasons(self) -> list[str]:
        return list(self._d.get("blocking_reasons", []) or [])

    def dimension_score(self, name: str) -> float | None:
        v = self._dims.get(name)
        s = v.get("score") if isinstance(v, dict) else v
        if s is None:
            return None
        try:
            return float(s)
        except (TypeError, ValueError):
            return None

    def dimension_justification(self, name: str) -> str:
        v = self._dims.get(name)
        if isinstance(v, dict):
            return v.get("justification", "") or ""
        return ""

    def all_dimensions_present(self) -> bool:
        return all(self._dims.get(d) is not None for d in SEVEN_DIMENSIONS)

    def has_blocking_gate(self) -> bool:
        return bool(self.blocking_reasons) or self.status == "blocked"


class CitationAuditView:
    """Read-only view over proposal.metadata['citation_audit']."""

    def __init__(self, proposal: Any):
        self._d = load_metadata(proposal).get("citation_audit") or {}

    @property
    def exists(self) -> bool:
        return bool(self._d)

    @property
    def status(self) -> str:
        return self._d.get("status", "") or ""

    @property
    def total_citations(self) -> int:
        return int(self._d.get("total_citations", 0) or 0)

    @property
    def fabricated_citations(self) -> int:
        return int(self._d.get("fabricated_citations", 0) or 0)


def first_proposal(result: Any) -> Any | None:
    """Return the first proposal from a PipelineResult, or None."""
    proposals = getattr(result, "proposals", None)
    if proposals is None:
        return None
    if isinstance(proposals, dict):
        return next(iter(proposals.values()), None)
    if isinstance(proposals, (list, tuple)):
        return proposals[0] if proposals else None
    return None


def stage_statuses(result: Any) -> dict[str, str]:
    """Map stage name -> status from result.stage_report."""
    out: dict[str, str] = {}
    for rep in getattr(result, "stage_report", []) or []:
        name = getattr(rep, "name", None) or ""
        status = getattr(rep, "status", "") or ""
        if name:
            out[name] = status
    return out


def source_markers_in_paper(paper_markdown: str) -> set[int]:
    """Return the set of [SOURCE-N] indices appearing in the paper text."""
    return set(int(m) for m in _SOURCE_MARKER_RE.findall(paper_markdown or ""))


def mapped_source_indices(source_map: list[dict]) -> set[int]:
    """Indices the source map records as 'mapped'."""
    return set(
        int(e.get("marker_index", -1))
        for e in source_map
        if e.get("mapping_status") == "mapped"
    )


def unmapped_source_indices(source_map: list[dict]) -> set[int]:
    """Indices the source map records as 'unmapped' (out-of-range/fabricated)."""
    return set(
        int(e.get("marker_index", -1))
        for e in source_map
        if e.get("mapping_status") == "unmapped"
    )
