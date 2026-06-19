"""Provenance backfill — populate IdeaPaperLink from resolved references.

This module bridges the gap between proposal references (raw text in
``references_json``) and structured provenance (``IdeaPaperLink`` rows).

During normal pipeline execution, ``supporting`` links are created by
``persistence._persist_idea_paper_links()`` from ``idea.supporting_papers``.
However, ``cited`` links — which represent the papers actually cited *in*
the proposal text — must be resolved from the proposal's reference list
using the ``reference_resolver``.

This service can be called:
  - Automatically after proposal synthesis (future)
  - Via the API ``POST /api/v1/ideas/{id}/backfill-citations``
  - Manually for existing proposals (one-time backfill)

The operation is idempotent: the ``(idea_id, paper_id, role)`` unique
constraint on ``IdeaPaperLink`` prevents duplicates.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import IdeaPaperLink, Proposal
from backend.pipeline.provenance.reference_resolver import resolve_references

logger = logging.getLogger(__name__)


@dataclass
class BackfillResult:
    """Summary of a citation backfill operation."""

    idea_id: int
    total_refs: int
    resolved: int
    new_links: int
    skipped_existing: int
    unresolved: int


def backfill_cited_links_for_idea(
    session: Session,
    idea_id: int,
) -> BackfillResult:
    """Resolve proposal references and persist as ``cited`` IdeaPaperLinks.

    Args:
        session: SQLAlchemy session (caller manages transaction).
        idea_id: The idea whose proposal references to backfill.

    Returns:
        BackfillResult with counts of resolved/skipped/unresolved refs.
    """
    # Fetch the proposal
    proposal = session.execute(
        select(Proposal).where(Proposal.idea_id == idea_id)
    ).scalar_one_or_none()

    if not proposal or not proposal.references_json:
        return BackfillResult(
            idea_id=idea_id,
            total_refs=0,
            resolved=0,
            new_links=0,
            skipped_existing=0,
            unresolved=0,
        )

    # Parse the raw references
    refs_raw = proposal.references_json
    if isinstance(refs_raw, str):
        # references_json may be a JSON-encoded string
        if refs_raw.startswith('"'):
            try:
                refs_raw = json.loads(refs_raw)
            except json.JSONDecodeError:
                pass

    # Resolve against Paper table
    resolved_refs = resolve_references(refs_raw, session)
    matched = [r for r in resolved_refs if r.resolved and r.paper]

    new_links = 0
    skipped = 0

    for ref in matched:
        paper_id = ref.paper["id"]

        # Check for existing link (idempotent)
        existing = session.execute(
            select(IdeaPaperLink).where(
                IdeaPaperLink.idea_id == idea_id,
                IdeaPaperLink.paper_id == paper_id,
                IdeaPaperLink.role == "cited",
            )
        ).scalar_one_or_none()

        if existing:
            skipped += 1
            continue

        session.add(IdeaPaperLink(
            idea_id=idea_id,
            paper_id=paper_id,
            role="cited",
        ))
        new_links += 1

    if new_links > 0:
        session.commit()

    unresolved = len(resolved_refs) - len(matched)

    logger.info(
        "Backfill idea #%d: %d refs, %d resolved (%d new, %d existing), %d unresolved",
        idea_id,
        len(resolved_refs),
        len(matched),
        new_links,
        skipped,
        unresolved,
    )

    return BackfillResult(
        idea_id=idea_id,
        total_refs=len(resolved_refs),
        resolved=len(matched),
        new_links=new_links,
        skipped_existing=skipped,
        unresolved=unresolved,
    )


def backfill_cited_links_for_all_ideas(
    session: Session,
) -> list[BackfillResult]:
    """Backfill cited links for all ideas that have proposals.

    Args:
        session: SQLAlchemy session.

    Returns:
        List of BackfillResult, one per idea with a proposal.
    """
    from backend.db.models import Idea

    ideas_with_proposals = session.execute(
        select(Idea.id).where(Idea.proposal.has()).order_by(Idea.id)
    ).scalars().all()

    results: list[BackfillResult] = []
    for idea_id in ideas_with_proposals:
        result = backfill_cited_links_for_idea(session, idea_id)
        results.append(result)

    return results
