"""Phase 2 2B/2E/2F: Trust & Sources review API.

Exposes a normalized review contract for a paper's sources and automated
checks, plus human source-review decisions and review completion state.

Routes (mounted under /api/v1/ideas/{idea_id}/review):
  GET    /                  — normalized review payload (automated_checks +
                              sources + human_review)
  POST   /sources/decisions — record a per-source decision (append-only)
  GET    /decisions         — list all source-review decisions for the idea

Truth rules (WP-2B):
  - missing confidence is returned as unavailable, never fabricated
  - unknown source metadata is null, not invented
  - proposal and paper evaluations remain distinct (never collapsed)
  - automated checks are never labeled human-reviewed
  - a resolved citation does not imply scientific support
  - source-to-section mapping is derived only from persisted markers/references
  - empty/malformed review artifacts produce explicit unavailable/failed states
  - no aggregate trust score is introduced

Immutability rule (WP-2E): a review decision does NOT mutate the existing
paper. exclude_on_next_revision is a recorded instruction, not proof the
current paper no longer uses the source.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.api.errors import APIError, NotFoundError
# NOTE: get_session is imported lazily inside functions so tests can monkeypatch
# backend.db.database.get_session (the import-at-top pattern binds the original
# and bypasses the patch). Matches the paper_export.py convention.
from backend.db.models import Idea, Proposal, SourceReview

router = APIRouter()


# ── Decision semantics (WP-2E) ─────────────────────────────────────

VALID_DECISIONS = {"accepted", "flagged", "exclude_on_next_revision"}


class SourceReviewDecisionRequest(BaseModel):
    """Record a human decision on a single cited source."""
    source_ref_hash: str = Field(..., min_length=8, max_length=64, description="SHA-256 of the normalized raw reference string")
    source_ref_number: int | None = Field(default=None, description="Positional reference number at decision time (display aid only)")
    decision: str = Field(..., description="accepted | flagged | exclude_on_next_revision")
    note: str | None = Field(default=None, max_length=4000)
    reviewer: str = Field(default="anonymous", max_length=128)


# ── Helpers ─────────────────────────────────────────────────────────


def _source_ref_hash(raw: str) -> str:
    """Phase 2 2E: stable source identity. SHA-256 of the normalized raw
    reference string. 2A established references carry no enforced DOI/arXiv/
    title ID, so the raw cited text is the only stable handle."""
    normalized = re.sub(r"\s+", " ", (raw or "").strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _load_proposal_and_idea(idea_id: int):
    from backend.db.database import get_session
    with get_session() as session:
        idea = session.get(Idea, idea_id)
        if idea is None:
            raise NotFoundError("Idea not found")
        proposal = session.execute(
            select(Proposal).where(Proposal.idea_id == idea_id).limit(1)
        ).scalar_one_or_none()
        return proposal, idea


def _latest_source_reviews(idea_id: int) -> dict[str, SourceReview]:
    """Return the latest decision per source_ref_hash (append-only model)."""
    from backend.db.database import get_session
    with get_session() as session:
        rows = session.execute(
            select(SourceReview).where(SourceReview.idea_id == idea_id)
            .order_by(SourceReview.created_at.desc())
        ).scalars().all()
    latest: dict[str, SourceReview] = {}
    for r in rows:
        if r.source_ref_hash not in latest:
            latest[r.source_ref_hash] = r
    return latest


def _derive_sections_using_source(paper_md: str | None, ref_number: int | None) -> list[str]:
    """Phase 2 2B: derive which paper sections cite a reference. Derived ONLY
    from persisted markers in the paper markdown (truth rule: no semantic
    guessing). Returns section header names containing the [N] marker, or an
    empty list when the paper or number is unavailable."""
    if not paper_md or ref_number is None:
        return []
    marker = f"[{ref_number}]"
    sections: list[str] = []
    current_section: str | None = None
    for line in paper_md.splitlines():
        m = re.match(r"^(#{1,6})\s+(.+)$", line)
        if m:
            current_section = m.group(2).strip()
        elif marker in line and current_section and current_section not in sections:
            sections.append(current_section)
    return sections


def _compute_human_review_status(
    reviewable_count: int, reviewed_count: int, flagged_count: int
) -> str:
    """Phase 2 2F: review completion state, based ONLY on persisted human
    decisions (never inferred from automated scores)."""
    if reviewable_count == 0:
        return "not_started"
    if reviewed_count == 0:
        return "not_started"
    if reviewed_count < reviewable_count:
        return "in_progress"
    # all reviewable reviewed
    return "completed_with_flags" if flagged_count > 0 else "completed"


# ── Routes ──────────────────────────────────────────────────────────


@router.get("/{idea_id}/review", summary="Get normalized trust & sources review payload")
async def get_review(idea_id: int):
    """Return the normalized review contract: automated_checks, sources, and
    human_review summary. Sources are derived from persisted references and
    citation-audit artifacts (truth rule: no fabrication)."""
    proposal, idea = _load_proposal_and_idea(idea_id)
    if proposal is None:
        raise NotFoundError("No proposal for this idea")

    # Automated checks (reuse the existing read-time computations so we never
    # duplicate the producers — truth rule: use the repository's actual data).
    from backend.api.quality_checks import audit_citations, compute_quality_checks
    from backend.api.traceability import extract_proposal_references
    from backend.db.database import get_session
    from backend.pipeline.provenance.reference_resolver import resolve_references

    sections_json = json.loads(proposal.sections_json) if proposal.sections_json else {}
    refs_raw = extract_proposal_references(proposal)
    # resolve_references needs a DB session to match against Paper rows.
    with get_session() as session:
        # Re-attach the proposal/idea to this session so attribute access works.
        session.merge(proposal)
        resolved_refs = resolve_references(refs_raw, session)
    # Serialize ResolvedReference dataclasses to dicts (audit_citations expects
    # dicts; mirrors the ideas.py route's conversion). Keep both the dict list
    # (for audit_citations) and the dataclass list (for the source builder).
    proposal_references_dicts = [
        {
            "raw": r.raw,
            "number": r.number,
            "authors": r.authors,
            "year": r.year,
            "title": r.title,
            "venue": r.venue,
            "doi": r.doi,
            "resolved": r.resolved,
            "paper": r.paper if isinstance(r.paper, dict) else {},
            "match_method": r.match_method,
            "match_confidence": r.match_confidence,
        }
        for r in resolved_refs
    ]
    citation_audit = audit_citations(sections_json, proposal_references_dicts)
    quality_checks = compute_quality_checks(sections_json)

    # Paper evaluation (Phase 1 1D, scope=paper) and proposal evaluation
    # (Phase 2 2B). These MUST remain distinct (truth rule).
    paper_meta = json.loads(proposal.paper_meta_json) if proposal.paper_meta_json else {}
    paper_evaluation = paper_meta.get("paper_evaluation")
    proposal_evaluation = None
    if proposal.proposal_evaluation_json:
        try:
            proposal_evaluation = {
                "scope": "proposal",
                "dimensions": json.loads(proposal.proposal_evaluation_json),
            }
        except (json.JSONDecodeError, TypeError):
            proposal_evaluation = {"scope": "proposal", "status": "unavailable"}

    automated_checks = {
        "paper_evaluation": paper_evaluation if paper_evaluation else {"status": "unavailable", "scope": "paper"},
        "proposal_evaluation": proposal_evaluation if proposal_evaluation else {"status": "unavailable", "scope": "proposal"},
        "citation_audit": citation_audit,
        "quality_checks": quality_checks,
    }

    # Sources — derived from resolved references (the only source list with
    # match_method + confidence). Each source carries its stable hash so the
    # frontend can post decisions against it.
    human_decisions = _latest_source_reviews(idea_id)
    sources = []
    for i, ref in enumerate(resolved_refs, 1):
        raw = getattr(ref, "raw", "") or ""
        h = _source_ref_hash(raw)
        _paper = getattr(ref, "paper", None)
        paper_dict = _paper if isinstance(_paper, dict) else {}
        decision_row = human_decisions.get(h)
        sources.append({
            "source_ref_hash": h,
            "citation_marker": f"[{i}]" if getattr(ref, "number", None) or raw else None,
            "ref_number": getattr(ref, "number", None),
            "raw": raw,
            "title": getattr(ref, "title", None) or paper_dict.get("title"),
            "authors": getattr(ref, "authors", None) or paper_dict.get("authors"),
            "year": getattr(ref, "year", None) or paper_dict.get("year"),
            "venue": getattr(ref, "venue", None) or paper_dict.get("venue"),
            "url": paper_dict.get("url"),
            "doi": getattr(ref, "doi", None) or paper_dict.get("doi"),
            "resolution_status": "resolved" if getattr(ref, "resolved", False) else "unresolved",
            # Truth rule: missing confidence must remain unavailable, not
            # invented. An unresolved ref has no real match, so its confidence
            # is null even though the dataclass defaults to 0.0.
            "match_method": getattr(ref, "match_method", None) if getattr(ref, "resolved", False) else None,
            "confidence": (
                getattr(ref, "match_confidence", None)
                if getattr(ref, "resolved", False) and getattr(ref, "match_confidence", None)
                else None
            ),
            "sections_used": _derive_sections_using_source(
                getattr(proposal, "paper_md", None), getattr(ref, "number", None)
            ),
            "human_decision": {
                "decision": decision_row.decision,
                "note": decision_row.note,
                "reviewer": decision_row.reviewer,
                "reviewed_at": decision_row.created_at.isoformat() if decision_row.created_at else None,
            } if decision_row else None,
        })

    # Human review summary (WP-2F). reviewable = sources with a stable identity
    # (all have a hash); flagged = accepted+flagged+exclude decisions count as
    # reviewed; flagged_only counts flagged + exclude.
    reviewable = len(sources)
    reviewed_hashes = {h for h, d in human_decisions.items()
                       if any(s["source_ref_hash"] == h for s in sources)}
    reviewed = len(reviewed_hashes)
    flagged = sum(
        1 for h in reviewed_hashes
        if human_decisions[h].decision in {"flagged", "exclude_on_next_revision"}
    )
    accepted = sum(1 for d in human_decisions.values() if d.decision == "accepted")

    human_review = {
        "status": _compute_human_review_status(reviewable, reviewed, flagged),
        "reviewable_sources": reviewable,
        "reviewed_sources": reviewed,
        "accepted": accepted,
        "flagged_or_excluded": flagged,
        "decisions_total": len(human_decisions),
    }

    return {
        "idea_id": idea_id,
        "automated_checks": automated_checks,
        "sources": sources,
        # Phase 4 / WP-4C: the authoritative marker→source map from the
        # persisted citation map (paper_source_markers). This is the SAME
        # source list exports consume; the legacy `sources` field above is
        # retained for backward compatibility with human-review decisions
        # keyed on source_ref_hash. `citation_markers` is the source of truth
        # for which [SOURCE-N] markers exist and what they resolve to.
        "citation_markers": _load_citation_markers(proposal),
        "human_review": human_review,
        # Explicit note: no aggregate trust score (truth rule).
        "regeneration_available": False,  # WP-2E boundary: no exclusion-aware regen yet
    }


def _load_citation_markers(proposal) -> list[dict]:
    """Phase 4 / WP-4C — load the marker→source map for the review payload.

    Each entry exposes the marker, mapping_status, and (for mapped markers)
    the resolved bibliographic identity from the linked Paper row. Unmapped
    markers carry null identity fields — never guessed.
    """
    import json as _json

    proposal_id = getattr(proposal, "id", None)
    if proposal_id is None:
        return []
    from backend.db.database import get_session
    from backend.pipeline.provenance.citation_map import (
        load_citation_map,
        _author_list,
    )

    with get_session() as session:
        entries = load_citation_map(session, proposal_id)
    out: list[dict] = []
    for e in entries:
        p = e.source_paper
        if p is not None:
            out.append({
                "marker_index": e.marker_index,
                "marker": e.marker,
                "mapping_status": e.mapping_status,
                "source_paper_id": e.source_paper_id,
                "title": getattr(p, "title", None),
                "authors": _author_list(p) or None,
                "year": getattr(p, "year", None),
                "venue": getattr(p, "venue", None),
                "doi": getattr(p, "doi", None),
                "arxiv_id": getattr(p, "arxiv_id", None),
                "url": getattr(p, "url", None),
            })
        else:
            out.append({
                "marker_index": e.marker_index,
                "marker": e.marker,
                "mapping_status": e.mapping_status,
                "source_paper_id": None,
                "title": None,
                "authors": None,
                "year": None,
                "venue": None,
                "doi": None,
                "arxiv_id": None,
                "url": None,
            })
    return out


@router.post("/{idea_id}/review/sources/decisions", summary="Record a human source-review decision")
async def record_source_decision(idea_id: int, req: SourceReviewDecisionRequest):
    """Record an append-only human decision on a single cited source.

    Immutability rule (WP-2E): this does NOT mutate the existing paper.
    exclude_on_next_revision is a recorded instruction for a future revision,
    not proof the current paper no longer uses the source.
    """
    if req.decision not in VALID_DECISIONS:
        raise APIError(400, f"decision must be one of {sorted(VALID_DECISIONS)}")
    # Confirm the idea exists (404 otherwise).
    from backend.db.database import get_session
    with get_session() as session:
        idea = session.get(Idea, idea_id)
        if idea is None:
            raise NotFoundError("Idea not found")
        row = SourceReview(
            idea_id=idea_id,
            source_ref_hash=req.source_ref_hash,
            source_ref_number=req.source_ref_number,
            decision=req.decision,
            note=req.note,
            reviewer=req.reviewer or "anonymous",
            created_at=datetime.now(timezone.utc),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "idea_id": row.idea_id,
            "source_ref_hash": row.source_ref_hash,
            "source_ref_number": row.source_ref_number,
            "decision": row.decision,
            "note": row.note,
            "reviewer": row.reviewer,
            "reviewed_at": row.created_at.isoformat() if row.created_at else None,
        }


@router.get("/{idea_id}/review/decisions", summary="List all source-review decisions for an idea")
async def list_source_decisions(idea_id: int):
    """List all source-review decisions (append-only history; latest per
    source is the current decision)."""
    from backend.db.database import get_session
    with get_session() as session:
        rows = session.execute(
            select(SourceReview).where(SourceReview.idea_id == idea_id)
            .order_by(SourceReview.created_at.desc())
        ).scalars().all()
    return {
        "idea_id": idea_id,
        "decisions": [
            {
                "id": r.id,
                "source_ref_hash": r.source_ref_hash,
                "source_ref_number": r.source_ref_number,
                "decision": r.decision,
                "note": r.note,
                "reviewer": r.reviewer,
                "reviewed_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "total": len(rows),
    }
