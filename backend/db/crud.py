"""CRUD operations for the metadata database."""

import json
from collections.abc import Sequence

from sqlalchemy import select, func, case, desc, asc
from sqlalchemy.orm import Session

from backend.db.models import Idea, Paper, PipelineRun, Proposal, ResearchGapDB

# --- Papers ---


def add_paper(session: Session, **kwargs) -> Paper:
    """Add a paper to the current transaction WITHOUT committing.

    P0.1: Used by persist_search_results to keep the governed boundary
    in a single uncommitted transaction until the final commit.

    The field mapping is identical to create_paper — this is the
    non-committing primitive that create_paper delegates to.
    """
    paper = Paper(**kwargs)
    session.add(paper)
    session.flush()
    return paper


def create_paper(session: Session, **kwargs) -> Paper:
    """Legacy convenience API with commit behavior.

    Delegates to add_paper then commits. Existing callers that expect
    auto-commit behavior are unaffected.
    """
    paper = add_paper(session, **kwargs)
    session.commit()
    session.refresh(paper)
    return paper


def get_paper(session: Session, paper_id: int) -> Paper | None:
    return session.get(Paper, paper_id)


def get_paper_by_source_id(session: Session, source_id: str) -> Paper | None:
    return session.execute(select(Paper).where(Paper.source_id == source_id)).scalar_one_or_none()


def list_papers(session: Session, limit: int = 50, offset: int = 0) -> Sequence[Paper]:
    return (
        session.execute(select(Paper).order_by(Paper.id.desc()).limit(limit).offset(offset))
        .scalars()
        .all()
    )


# --- Ideas ---


def create_idea(session: Session, **kwargs) -> Idea:
    idea = Idea(**kwargs)
    session.add(idea)
    session.commit()
    session.refresh(idea)
    return idea


def get_idea(session: Session, idea_id: int) -> Idea | None:
    return session.get(Idea, idea_id)


def count_ideas(
    session: Session,
    domain: str | None = None,
    min_score: float | None = None,
    search: str | None = None,
) -> int:
    stmt = select(func.count()).select_from(Idea)
    if domain is not None:
        stmt = stmt.where(Idea.domain == domain)
    if min_score is not None:
        stmt = stmt.where(Idea.overall_score >= min_score)
    if search is not None:
        stmt = stmt.where(Idea.title.ilike(f"%{search}%"))
    return session.execute(stmt).scalar_one()


VALID_SORT_COLUMNS = {
    "score": Idea.overall_score,
    "novelty": Idea.novelty_score,
    "feasibility": Idea.feasibility_score,
    "date": Idea.created_at,
}


def list_ideas(
    session: Session,
    limit: int = 50,
    offset: int = 0,
    domain: str | None = None,
    min_score: float | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "desc",
) -> Sequence[Idea]:
    stmt = select(Idea)

    # Filters
    if domain is not None:
        stmt = stmt.where(Idea.domain == domain)
    if min_score is not None:
        stmt = stmt.where(Idea.overall_score >= min_score)
    if search is not None:
        stmt = stmt.where(Idea.title.ilike(f"%{search}%"))

    # Sorting
    sort_col = VALID_SORT_COLUMNS.get(sort_by) if sort_by else None
    if sort_col is not None:
        # Nulls last: use CASE to push NULLs to the end
        nulls_last_expr = case((sort_col.is_(None), 1), else_=0)
        direction = desc if sort_order == "desc" else asc
        stmt = stmt.order_by(nulls_last_expr, direction(sort_col))
    else:
        stmt = stmt.order_by(Idea.id.desc())

    stmt = stmt.limit(limit).offset(offset)
    return session.execute(stmt).scalars().all()


def get_ideas_for_run(session: Session, run_id: int) -> Sequence[Idea]:
    """Return all ideas linked to a pipeline run via pipeline_run_id FK."""
    return (
        session.execute(
            select(Idea).where(Idea.pipeline_run_id == run_id).order_by(Idea.id.asc())
        )
        .scalars()
        .all()
    )


def count_ideas_for_run(session: Session, run_id: int) -> int:
    """Return the total count of ideas linked to a pipeline run."""
    return session.execute(
        select(func.count())
        .select_from(Idea)
        .where(Idea.pipeline_run_id == run_id)
    ).scalar_one()


def update_idea_scores(
    session: Session,
    idea_id: int,
    novelty_score: float | None = None,
    feasibility_score: float | None = None,
    novelty_report: str | None = None,
    feasibility_report: str | None = None,
) -> Idea | None:
    idea = session.get(Idea, idea_id)
    if not idea:
        return None
    if novelty_score is not None:
        idea.novelty_score = novelty_score
    if feasibility_score is not None:
        idea.feasibility_score = feasibility_score
    if novelty_report is not None:
        idea.novelty_report = novelty_report
    if feasibility_report is not None:
        idea.feasibility_report = feasibility_report
    if idea.novelty_score is not None and idea.feasibility_score is not None:
        normalized_feasibility = idea.feasibility_score / 10.0
        idea.overall_score = (idea.novelty_score + normalized_feasibility) / 2
    session.commit()
    session.refresh(idea)
    return idea


def update_idea_feedback(
    session: Session,
    idea_id: int,
    rating: int,
    notes: str | None = None,
) -> Idea | None:
    idea = session.get(Idea, idea_id)
    if not idea:
        return None
    idea.user_rating = rating
    idea.user_notes = notes
    session.commit()
    session.refresh(idea)
    return idea


# --- Proposals ---


def create_proposal(session: Session, idea_id: int, content_md: str, **kwargs) -> Proposal:
    proposal = Proposal(idea_id=idea_id, content_md=content_md, **kwargs)
    session.add(proposal)
    session.commit()
    session.refresh(proposal)
    return proposal


def get_proposal_by_idea(session: Session, idea_id: int) -> Proposal | None:
    return session.execute(select(Proposal).where(Proposal.idea_id == idea_id)).scalar_one_or_none()


# --- Pipeline Runs ---


def count_pipeline_runs(
    session: Session,
    session_id: str | None = None,
) -> int:
    stmt = select(func.count()).select_from(PipelineRun)
    if session_id is not None:
        stmt = stmt.where(PipelineRun.session_id == session_id)
    return session.execute(stmt).scalar_one()


def list_pipeline_runs(
    session: Session,
    limit: int = 20,
    offset: int = 0,
    session_id: str | None = None,
) -> Sequence[PipelineRun]:
    from sqlalchemy.orm import selectinload
    stmt = select(PipelineRun).options(selectinload(PipelineRun.ideas))
    if session_id is not None:
        stmt = stmt.where(PipelineRun.session_id == session_id)
    stmt = stmt.order_by(PipelineRun.id.desc()).limit(limit).offset(offset)
    return session.execute(stmt).scalars().all()


def list_session_ids(session: Session) -> list[dict]:
    """Return unique session_id values with run count and latest run timestamp.

    Returns list of dicts: [{session_id, run_count, latest_run_at}].
    Only includes runs where session_id is not NULL.
    """
    stmt = (
        select(
            PipelineRun.session_id,
            func.count().label("run_count"),
            func.max(PipelineRun.created_at).label("latest_run_at"),
        )
        .where(PipelineRun.session_id.isnot(None))
        .group_by(PipelineRun.session_id)
        .order_by(func.max(PipelineRun.created_at).desc())
    )
    rows = session.execute(stmt).all()
    return [
        {
            "session_id": row.session_id,
            "run_count": row.run_count,
            "latest_run_at": str(row.latest_run_at),
        }
        for row in rows
    ]


def create_pipeline_run(session: Session, **kwargs) -> PipelineRun:
    # P0.2.7: provenance_version is required (no default). Callers must
    # provide it explicitly, or use create_governed_run_record / create_legacy_run_record.
    if "provenance_version" not in kwargs:
        kwargs["provenance_version"] = "provenance_v1"
        kwargs.setdefault("legacy_provenance_reason", None)
    run = PipelineRun(**kwargs)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def get_pipeline_run(session: Session, run_id: int) -> PipelineRun | None:
    return session.get(PipelineRun, run_id)


def update_pipeline_run(
    session: Session,
    run_id: int,
    status: str | None = None,
    current_stage: str | None = None,
    error_message: str | None = None,
) -> PipelineRun | None:
    run = session.get(PipelineRun, run_id)
    if not run:
        return None
    if status is not None:
        run.status = status
    if current_stage is not None:
        run.current_stage = current_stage
        completed = json.loads(run.stages_completed)
        if current_stage not in completed:
            completed.append(current_stage)
            run.stages_completed = json.dumps(completed)
    if error_message is not None:
        run.error_message = error_message
    from datetime import datetime, timezone

    if status in ("completed", "failed"):
        run.completed_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(run)
    return run


# --- Research Gaps ---


def create_gap(session: Session, **kwargs) -> ResearchGapDB:
    gap = ResearchGapDB(**kwargs)
    session.add(gap)
    session.commit()
    session.refresh(gap)
    return gap


def get_gap(session: Session, gap_id: int) -> ResearchGapDB | None:
    return session.get(ResearchGapDB, gap_id)


def list_gaps_by_run(session: Session, run_id: int) -> Sequence[ResearchGapDB]:
    return (
        session.execute(
            select(ResearchGapDB)
            .where(ResearchGapDB.pipeline_run_id == run_id)
            .order_by(ResearchGapDB.confidence.desc())
        )
        .scalars()
        .all()
    )


def count_gaps_by_run(session: Session, run_id: int) -> int:
    return session.execute(
        select(func.count())
        .select_from(ResearchGapDB)
        .where(ResearchGapDB.pipeline_run_id == run_id)
    ).scalar_one()


# --- Research Gaps: Search / Filter / Sort (BATCH-39) ---

VALID_GAP_SORT_COLUMNS = {
    "confidence": ResearchGapDB.confidence,
    "date": ResearchGapDB.created_at,
    "type": ResearchGapDB.gap_type,
}

VALID_GAP_TYPES = {"methodological", "empirical", "theoretical", "cross-domain"}


def count_search_gaps(
    session: Session,
    run_id: int | None = None,
    search: str | None = None,
    gap_type: str | None = None,
    min_confidence: float | None = None,
) -> int:
    """Count gaps matching filter criteria (BATCH-39)."""
    stmt = select(func.count()).select_from(ResearchGapDB)
    if run_id is not None:
        stmt = stmt.where(ResearchGapDB.pipeline_run_id == run_id)
    if search is not None:
        stmt = stmt.where(
            (ResearchGapDB.title.ilike(f"%{search}%"))
            | (ResearchGapDB.description.ilike(f"%{search}%"))
        )
    if gap_type is not None and gap_type in VALID_GAP_TYPES:
        stmt = stmt.where(ResearchGapDB.gap_type == gap_type)
    if min_confidence is not None:
        stmt = stmt.where(ResearchGapDB.confidence >= min_confidence)
    return session.execute(stmt).scalar_one()


def search_gaps(
    session: Session,
    run_id: int | None = None,
    search: str | None = None,
    gap_type: str | None = None,
    min_confidence: float | None = None,
    sort_by: str | None = None,
    sort_order: str = "desc",
    limit: int = 20,
    offset: int = 0,
) -> Sequence[ResearchGapDB]:
    """Return gaps matching filter/sort criteria (BATCH-39).

    Args:
        session: SQLAlchemy session.
        run_id: Optional pipeline run ID filter.
        search: Case-insensitive substring match on title and description.
        gap_type: Exact match filter (validated against VALID_GAP_TYPES).
        min_confidence: Minimum confidence threshold.
        sort_by: Column to sort by (validated against VALID_GAP_SORT_COLUMNS).
        sort_order: "asc" or "desc" (default: "desc").
        limit: Max results.
        offset: Pagination offset.

    Returns:
        Sequence of matching ResearchGapDB objects.
    """
    stmt = select(ResearchGapDB)

    # Filters
    if run_id is not None:
        stmt = stmt.where(ResearchGapDB.pipeline_run_id == run_id)
    if search is not None:
        stmt = stmt.where(
            (ResearchGapDB.title.ilike(f"%{search}%"))
            | (ResearchGapDB.description.ilike(f"%{search}%"))
        )
    if gap_type is not None and gap_type in VALID_GAP_TYPES:
        stmt = stmt.where(ResearchGapDB.gap_type == gap_type)
    if min_confidence is not None:
        stmt = stmt.where(ResearchGapDB.confidence >= min_confidence)

    # Sorting (AR-01: whitelist — invalid values ignored)
    sort_col = VALID_GAP_SORT_COLUMNS.get(sort_by) if sort_by else None
    if sort_col is not None:
        direction = desc if sort_order == "desc" else asc
        stmt = stmt.order_by(direction(sort_col))
    else:
        stmt = stmt.order_by(ResearchGapDB.confidence.desc())

    stmt = stmt.limit(limit).offset(offset)
    return session.execute(stmt).scalars().all()


def count_ideas_for_gap(session: Session, gap_title: str) -> int:
    """Count ideas whose source_gap_ids JSON contains the given gap title.

    Uses parameterized LIKE query (HB-01) — the gap title is passed as a
    bound parameter, never interpolated into SQL.
    """
    stmt = (
        select(func.count())
        .select_from(Idea)
        .where(Idea.source_gap_ids.isnot(None))
        .where(Idea.source_gap_ids.ilike(f"%{gap_title}%"))
    )
    return session.execute(stmt).scalar_one()


def batch_count_ideas_for_gaps(session: Session, gap_titles: list[str]) -> dict[str, int]:
    """Batch count ideas for multiple gap titles in a single query.

    Returns {gap_title: count} for all titles. Avoids N+1 when listing gaps.
    """
    if not gap_titles:
        return {}
    # Get all ideas with source_gap_ids, then match in Python
    rows = session.execute(
        select(Idea.source_gap_ids)
        .where(Idea.source_gap_ids.isnot(None))
    ).scalars().all()
    counts: dict[str, int] = {t: 0 for t in gap_titles}
    for row in rows:
        for title in gap_titles:
            if title.lower() in (row or "").lower():
                counts[title] += 1
    return counts


def update_gap_feedback(session: Session, gap_id: int, rating: int, notes: str | None = None) -> ResearchGapDB | None:
    """Update user rating and notes for a gap (BATCH-41)."""
    gap = session.get(ResearchGapDB, gap_id)
    if not gap:
        return None
    gap.user_rating = rating
    if notes is not None:
        gap.user_notes = notes
    session.commit()
    session.refresh(gap)
    return gap


def update_gap_status(session: Session, gap_id: int, new_status: str) -> ResearchGapDB | None:
    """Update gap lifecycle status with forward-only validation (BATCH-41)."""
    VALID_TRANSITIONS = {
        "identified": "investigating",
        "investigating": "addressed",
    }
    gap = session.get(ResearchGapDB, gap_id)
    if not gap:
        return None
    current = gap.status or "identified"
    if new_status == current:
        return gap  # No-op
    expected_next = VALID_TRANSITIONS.get(current)
    if expected_next != new_status:
        return None  # Invalid transition — caller returns 422
    gap.status = new_status
    session.commit()
    session.refresh(gap)
    return gap


def find_gap_by_hash(session: Session, content_hash: str) -> ResearchGapDB | None:
    """Find a gap by content_hash for deduplication (BATCH-42)."""
    return session.execute(
        select(ResearchGapDB).where(ResearchGapDB.content_hash == content_hash).limit(1)
    ).scalar_one_or_none()


def list_canonical_gaps(session: Session, limit: int = 100) -> list[ResearchGapDB]:
    """List deduplicated gaps (one per unique content_hash, BATCH-42)."""
    from sqlalchemy import distinct
    # Get unique hashes and pick the first gap for each
    subq = (
        select(ResearchGapDB.id, ResearchGapDB.content_hash)
        .where(ResearchGapDB.content_hash.isnot(None))
        .distinct(ResearchGapDB.content_hash)
        .order_by(ResearchGapDB.content_hash, ResearchGapDB.id)
        .subquery()
    )
    return session.execute(
        select(ResearchGapDB).join(subq, ResearchGapDB.id == subq.c.id)
        .order_by(ResearchGapDB.confidence.desc())
        .limit(limit)
    ).scalars().all()


# --- Quarantined citations (STOPGAP) ---
#
# These helpers make the "don't naively COUNT(*) quarantine rows" warning
# structurally enforceable. Use THESE instead of raw row counts.

def count_active_quarantined_citations(session: Session, proposal_id: int) -> int:
    """Count quarantine rows whose citation still exists in current sections text."""
    from backend.db.models import Proposal, QuarantinedCitation

    rows = session.execute(
        select(QuarantinedCitation).where(
            QuarantinedCitation.proposal_id == proposal_id
        )
    ).scalars().all()
    if not rows:
        return 0
    proposal = session.execute(
        select(Proposal).where(Proposal.id == proposal_id).limit(1)
    ).scalar_one_or_none()
    if not proposal or not proposal.sections_json:
        return 0
    try:
        sections = json.loads(proposal.sections_json)
    except (json.JSONDecodeError, TypeError):
        return 0
    active = 0
    for row in rows:
        text = sections.get(row.section_key)
        if isinstance(text, str) and f"[SOURCE-{row.ref_index}]" in text:
            active += 1
    return active


def count_all_quarantined_citations(session: Session, proposal_id: int) -> int:
    """Count ALL quarantine rows for a proposal, including render-inert ones."""
    from backend.db.models import QuarantinedCitation

    return session.execute(
        select(func.count()).select_from(QuarantinedCitation).where(
            QuarantinedCitation.proposal_id == proposal_id
        )
    ).scalar_one()


def aggregate_quarantine_counts(
    session: Session, proposal_ids: list[int]
) -> tuple[int, int]:
    """Batch-aggregate active and total quarantine counts across proposals."""
    if not proposal_ids:
        return 0, 0
    from backend.db.models import Proposal, QuarantinedCitation

    rows = session.execute(
        select(QuarantinedCitation).where(
            QuarantinedCitation.proposal_id.in_(proposal_ids)
        )
    ).scalars().all()
    if not rows:
        return 0, 0
    affected_ids = {r.proposal_id for r in rows}
    proposals = session.execute(
        select(Proposal.id, Proposal.sections_json).where(
            Proposal.id.in_(affected_ids)
        )
    ).all()
    sections_by_proposal: dict[int, dict] = {}
    for pid, sj in proposals:
        if sj:
            try:
                sections_by_proposal[pid] = json.loads(sj)
            except (json.JSONDecodeError, TypeError):
                pass
    active_total = 0
    for row in rows:
        sections = sections_by_proposal.get(row.proposal_id, {})
        text = sections.get(row.section_key)
        if isinstance(text, str) and f"[SOURCE-{row.ref_index}]" in text:
            active_total += 1
    return active_total, len(rows)
