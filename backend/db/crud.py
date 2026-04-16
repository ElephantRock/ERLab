"""CRUD operations for the metadata database."""

import json
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import Idea, Paper, PipelineRun, Proposal


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
    return session.execute(select(Paper).order_by(Paper.id.desc()).limit(limit).offset(offset)).scalars().all()


# --- Ideas ---

def create_idea(session: Session, **kwargs) -> Idea:
    idea = Idea(**kwargs)
    session.add(idea)
    session.commit()
    session.refresh(idea)
    return idea


def get_idea(session: Session, idea_id: int) -> Idea | None:
    return session.get(Idea, idea_id)


def list_ideas(session: Session, limit: int = 50, offset: int = 0) -> Sequence[Idea]:
    return session.execute(select(Idea).order_by(Idea.id.desc()).limit(limit).offset(offset)).scalars().all()


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
        idea.overall_score = (idea.novelty_score + idea.feasibility_score) / 2
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
    from datetime import datetime
    if status == "completed":
        run.completed_at = datetime.utcnow()
    session.commit()
    session.refresh(run)
    return run
