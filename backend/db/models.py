"""SQLAlchemy ORM models for metadata storage."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(50))  # semantic_scholar, arxiv, openalex
    title: Mapped[str] = mapped_column(Text)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    authors: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    venue: Mapped[str | None] = mapped_column(String(512), nullable=True)
    citation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    doi: Mapped[str | None] = mapped_column(String(256), nullable=True)
    arxiv_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    keywords: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    pdf_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    ingested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Idea(Base):
    __tablename__ = "ideas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text)
    problem_statement: Mapped[str] = mapped_column(Text)
    proposed_method: Mapped[str] = mapped_column(Text)
    expected_contributions: Mapped[str] = mapped_column(Text, default="")
    domain: Mapped[str] = mapped_column(String(100), default="AI/NLP")

    # Scores
    novelty_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    feasibility_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Novelty + feasibility details (JSON)
    novelty_report: Mapped[str | None] = mapped_column(Text, nullable=True)
    feasibility_report: Mapped[str | None] = mapped_column(Text, nullable=True)

    # User feedback
    user_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Gap→Idea traceability (JSON list of gap titles / identifiers)
    source_gap_ids: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Link to the pipeline run that generated this idea
    pipeline_run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("pipeline_runs.id"), nullable=True
    )

    proposal: Mapped["Proposal | None"] = relationship(back_populates="idea")
    pipeline_run: Mapped["PipelineRun | None"] = relationship(back_populates="ideas")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    idea_id: Mapped[int] = mapped_column(Integer, ForeignKey("ideas.id"), unique=True)
    content_md: Mapped[str] = mapped_column(Text)
    content_latex: Mapped[str | None] = mapped_column(Text, nullable=True)
    references_json: Mapped[str] = mapped_column(Text, default="[]")
    sections_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    idea: Mapped["Idea"] = relationship(back_populates="proposal")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending, running, completed, failed
    domain: Mapped[str] = mapped_column(String(100), default="AI/NLP")
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Stage tracking
    current_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    stages_completed: Mapped[str] = mapped_column(Text, default="[]")  # JSON list

    ideas: Mapped[list["Idea"]] = relationship(back_populates="pipeline_run")
    gaps: Mapped[list["ResearchGapDB"]] = relationship(back_populates="pipeline_run")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ResearchGapDB(Base):
    __tablename__ = "research_gaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    gap_type: Mapped[str] = mapped_column(String(50), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    potential_impact: Mapped[str] = mapped_column(Text, default="")
    pipeline_run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("pipeline_runs.id"), nullable=True
    )

    pipeline_run: Mapped["PipelineRun | None"] = relationship(back_populates="gaps")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
