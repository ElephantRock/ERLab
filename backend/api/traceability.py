"""Traceability resolution helpers.

Resolves loose references (gap titles, idempotency keys) into structured
traceability objects with explicit ``resolved: bool`` so callers never
silently lose a link.
"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import Idea as IdeaModel
from backend.db.models import ResearchGapDB


def _normalize_title(title: str) -> str:
    """Normalize a title for fuzzy matching.

    Lowercase, strip punctuation, collapse whitespace.
    """
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", title.lower())).strip()


def resolve_source_gaps(
    session: Session,
    raw_gap_ids: list[str],
    pipeline_run_id: int | None,
) -> list[dict[str, Any]]:
    """Resolve source_gap_ids entries to real gap records.

    Tries exact title match, then normalized title match. Entries that
    can't be resolved are returned as ``{raw: ..., resolved: false}`` so
    no traceability reference is silently dropped.

    Args:
        session: SQLAlchemy session.
        raw_gap_ids: List of gap identifiers from ``Idea.source_gap_ids``
            (may contain gap titles, idempotency hashes, or arbitrary strings).
        pipeline_run_id: The pipeline run to search within.

    Returns:
        List of trace objects:
        ``{id, title, gap_type, confidence, resolved: true}`` or
        ``{raw, resolved: false}``.
    """
    if not raw_gap_ids or not pipeline_run_id:
        return []

    # Fetch all gaps for this run once
    gaps = session.execute(
        select(ResearchGapDB).where(ResearchGapDB.pipeline_run_id == pipeline_run_id)
    ).scalars().all()

    # Build lookup indices
    by_exact_title: dict[str, ResearchGapDB] = {g.title: g for g in gaps}
    by_normalized: dict[str, ResearchGapDB] = {
        _normalize_title(g.title): g for g in gaps
    }
    by_content_hash: dict[str, ResearchGapDB] = {
        g.content_hash: g for g in gaps if g.content_hash
    }
    by_canonical_id: dict[str, ResearchGapDB] = {
        g.canonical_id: g for g in gaps if g.canonical_id
    }

    results: list[dict[str, Any]] = []
    for raw_id in raw_gap_ids:
        # Try exact match first
        gap = by_exact_title.get(raw_id)

        # Try normalized match
        if gap is None:
            normalized = _normalize_title(raw_id)
            gap = by_normalized.get(normalized)

        # Try content_hash match (for idempotency keys)
        if gap is None:
            gap = by_content_hash.get(raw_id)

        # Try canonical_id match
        if gap is None:
            gap = by_canonical_id.get(raw_id)

        if gap is not None:
            results.append({
                "id": gap.id,
                "title": gap.title,
                "gap_type": gap.gap_type,
                "confidence": gap.confidence,
                "resolved": True,
            })
        else:
            results.append({
                "raw": raw_id,
                "resolved": False,
            })

    # Fallback: if nothing resolved but the run has gaps, link to all run gaps
    # as inferred provenance. This handles ideas where source_gap_ids was
    # stored as an idempotency hash instead of gap titles.
    has_resolved = any(r.get("resolved") for r in results)
    if not has_resolved and gaps:
        results = [  # Replace unresolved entries with inferred gaps
            {
                "id": gap.id,
                "title": gap.title,
                "gap_type": gap.gap_type,
                "confidence": gap.confidence,
                "resolved": True,
                "inferred": True,
            }
            for gap in gaps
        ]

    return results


def find_related_ideas(
    session: Session,
    gap_title: str,
    pipeline_run_id: int | None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Find ideas whose source_gap_ids reference the given gap title.

    This is a heuristic match — source_gap_ids may contain the exact title,
    a normalized variant, or an idempotency key that doesn't match.

    Args:
        session: SQLAlchemy session.
        gap_title: The gap title to search for.
        pipeline_run_id: Restrict to this pipeline run if provided.
        limit: Maximum number of ideas to return.

    Returns:
        List of ``{id, title, overall_score}`` dicts.
    """
    query = select(IdeaModel)
    if pipeline_run_id:
        query = query.where(IdeaModel.pipeline_run_id == pipeline_run_id)
    ideas = session.execute(query).scalars().all()

    normalized_gap = _normalize_title(gap_title)
    results: list[dict[str, Any]] = []
    for idea in ideas:
        if not idea.source_gap_ids:
            continue
        try:
            gap_ids = json.loads(idea.source_gap_ids)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(gap_ids, list):
            continue
        # Check if any gap ID matches (exact or normalized)
        for gid in gap_ids:
            if not isinstance(gid, str):
                continue
            if gid == gap_title or _normalize_title(gid) == normalized_gap:
                results.append({
                    "id": idea.id,
                    "title": idea.title,
                    "overall_score": idea.overall_score,
                })
                break

    return results[:limit]


def extract_proposal_references(proposal: Any) -> list[dict[str, str]] | str | None:
    """Extract references from a proposal record.

    Parses ``references_json`` which may contain:
    - A JSON list of ``{"raw": "..."}`` dicts
    - A JSON string (raw text)
    - Empty/null

    Args:
        proposal: A Proposal model instance with ``references_json`` field.

    Returns:
        List of reference dicts, a raw string, or None if no references.
    """
    if not proposal or not proposal.references_json:
        return None

    try:
        refs = json.loads(proposal.references_json)
    except (json.JSONDecodeError, TypeError):
        return proposal.references_json  # Return raw text

    if isinstance(refs, list):
        return refs if refs else None
    if isinstance(refs, str) and refs.strip():
        return refs
    return None
