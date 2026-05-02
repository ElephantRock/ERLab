"""SQLAlchemy ORM models for metadata storage."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base


class User(Base):
    """User account for JWT authentication (BATCH-28)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(20), default="user")  # admin | user
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


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
    __table_args__ = (
        Index("ix_ideas_pipeline_run_id", "pipeline_run_id"),
        Index("ix_ideas_domain", "domain"),
        Index("ix_ideas_overall_score", "overall_score"),
    )

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
    __table_args__ = (
        Index("ix_pipeline_runs_status", "status"),
        Index("ix_pipeline_runs_session_id", "session_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending, running, completed, failed
    domain: Mapped[str] = mapped_column(String(100), default="AI/NLP")
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Session grouping (simple string field, not a FK — HB-01)
    session_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Stage tracking
    current_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    stages_completed: Mapped[str] = mapped_column(Text, default="[]")  # JSON list

    # Cluster report (BATCH-38)
    cluster_report_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    ideas: Mapped[list["Idea"]] = relationship(back_populates="pipeline_run")
    gaps: Mapped[list["ResearchGapDB"]] = relationship(back_populates="pipeline_run")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Comment(Base):
    """Comment thread on a research idea (BATCH-34)."""

    __tablename__ = "comments"
    __table_args__ = (
        Index("ix_comments_idea_id", "idea_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    idea_id: Mapped[int] = mapped_column(Integer, ForeignKey("ideas.id"))
    author: Mapped[str] = mapped_column(String(128), default="anonymous")
    content: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("comments.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class SharedIdea(Base):
    """Shareable link for a research idea (BATCH-34)."""

    __tablename__ = "shared_ideas"
    __table_args__ = (
        Index("ix_shared_ideas_idea_id", "idea_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    idea_id: Mapped[int] = mapped_column(Integer, ForeignKey("ideas.id"))
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class ResearchGapDB(Base):
    __tablename__ = "research_gaps"
    __table_args__ = (
        Index("ix_research_gaps_pipeline_run_id", "pipeline_run_id"),
        Index("ix_research_gaps_confidence", "confidence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    gap_type: Mapped[str] = mapped_column(String(50), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    potential_impact: Mapped[str] = mapped_column(Text, default="")
    pipeline_run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("pipeline_runs.id"), nullable=True
    )

    # Truth value fields (BATCH-38)
    truth_frequency: Mapped[float] = mapped_column(Float, default=0.5)
    truth_confidence: Mapped[float] = mapped_column(Float, default=0.5)
    truth_evidence_count: Mapped[int] = mapped_column(Integer, default=0)

    # Related cluster IDs (BATCH-38)
    related_clusters: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Feedback & lifecycle (BATCH-41)
    status: Mapped[str] = mapped_column(String(20), default="identified")
    user_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    pipeline_run: Mapped["PipelineRun | None"] = relationship(back_populates="gaps")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
