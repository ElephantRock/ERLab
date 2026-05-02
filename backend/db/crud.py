"""CRUD operations for the metadata database."""

import json
from collections.abc import Sequence

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.db.models import Idea, Paper, PipelineRun, Proposal, ResearchGapDB

# --- Papers ---


def create_paper(session: Session, **kwargs) -> Paper:
    paper = Paper(**kwargs)
    session.add(paper)
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
) -> int:
    stmt = select(func.count()).select_from(Idea)
    if domain is not None:
        stmt = stmt.where(Idea.domain == domain)
    if min_score is not None:
        stmt = stmt.where(Idea.overall_score >= min_score)
    return session.execute(stmt).scalar_one()


def list_ideas(
    session: Session,
    limit: int = 50,
    offset: int = 0,
    domain: str | None = None,
    min_score: float | None = None,
) -> Sequence[Idea]:
    stmt = select(Idea).order_by(Idea.id.desc())
    if domain is not None:
        stmt = stmt.where(Idea.domain == domain)
    if min_score is not None:
        stmt = stmt.where(Idea.overall_score >= min_score)
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


def count_pipeline_runs(session: Session) -> int:
    return session.execute(select(func.count()).select_from(PipelineRun)).scalar_one()


def list_pipeline_runs(
    session: Session,
    limit: int = 20,
    offset: int = 0,
) -> Sequence[PipelineRun]:
    return (
        session.execute(
            select(PipelineRun).order_by(PipelineRun.id.desc()).limit(limit).offset(offset)
        )
        .scalars()
        .all()
    )


def create_pipeline_run(session: Session, **kwargs) -> PipelineRun:
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

    if status == "completed":
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
