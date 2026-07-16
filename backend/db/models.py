"""SQLAlchemy ORM models for metadata storage."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import event

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

    # Tree-of-thought parent references (BATCH-63)
    parent_idea_ids: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Link to the pipeline run that generated this idea
    pipeline_run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("pipeline_runs.id"), nullable=True
    )

    proposal: Mapped["Proposal | None"] = relationship(back_populates="idea")
    pipeline_run: Mapped["PipelineRun | None"] = relationship(back_populates="ideas")
    paper_links: Mapped[list["IdeaPaperLink"]] = relationship(back_populates="idea", cascade="all, delete-orphan")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class IdeaPaperLink(Base):
    """Junction table linking ideas to supporting/cited papers.

    Provides explicit many-to-many provenance: which papers were used to
    generate or are cited by a given idea.  The ``role`` field distinguishes
    between papers selected by the pipeline as supporting evidence and
    references that appear in the final proposal text.
    """

    __tablename__ = "idea_paper_links"
    __table_args__ = (
        UniqueConstraint("idea_id", "paper_id", "role", name="uq_idea_paper_role"),
        Index("ix_idea_paper_links_idea_id", "idea_id"),
        Index("ix_idea_paper_links_paper_id", "paper_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    idea_id: Mapped[int] = mapped_column(Integer, ForeignKey("ideas.id"), nullable=False)
    paper_id: Mapped[int] = mapped_column(Integer, ForeignKey("papers.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="supporting")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    idea: Mapped["Idea"] = relationship(back_populates="paper_links")
    paper: Mapped["Paper"] = relationship()


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
        # P0.2.7: provenance vocabulary
        CheckConstraint(
            "provenance_version IN ('pre_provenance', 'provenance_v1')",
            name="ck_pipeline_runs_provenance_version",
        ),
        # P0.2.7: version/reason consistency
        CheckConstraint(
            "("
            "  provenance_version = 'pre_provenance' "
            "  AND legacy_provenance_reason IN ("
            "    'pre_gating_run', 'legacy_checkpoint', "
            "    'explicit_legacy_mode', 'imported_legacy_run'"
            "  )"
            ") OR ("
            "  provenance_version = 'provenance_v1' "
            "  AND legacy_provenance_reason IS NULL"
            ")",
            name="ck_pipeline_runs_provenance_legacy_reason",
        ),
        # P0.3.1: domain scope consistency
        CheckConstraint(
            "("
            "  domain_scope_key IS NULL AND domain_scope_version IS NULL"
            ") OR ("
            "  domain_scope_key IS NOT NULL"
            "  AND domain_scope_version = 'domain_scope_v1'"
            ")",
            name="ck_pipeline_runs_domain_scope",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id_str: Mapped[str | None] = mapped_column(
        String(50), unique=True, index=True, nullable=True,
        comment="String run ID (e.g. run_20260611_153000) for URL-safe lookups",
    )
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

    # Stage observability report (BATCH-173)
    stage_report_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Cluster report (BATCH-38)
    cluster_report_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Tree search visualization data (BATCH-63)
    tree_data_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    ideas: Mapped[list["Idea"]] = relationship(back_populates="pipeline_run")
    gaps: Mapped[list["ResearchGapDB"]] = relationship(back_populates="pipeline_run")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # BATCH-74: watchdog tracking

    # P0.1/P0.2.7: Provenance contract — immutable after creation.
    # NO default: callers must explicitly choose governed or legacy.
    # 'pre_provenance' = outside the enforced provenance contract
    # 'provenance_v1' = must satisfy the complete governed P0.1–P0.2 contract
    provenance_version: Mapped[str] = mapped_column(
        String(20), nullable=False,
    )
    # P0.2.7: Legacy reason — required for pre_provenance, NULL for provenance_v1.
    legacy_provenance_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # P0.3.1: Stable domain identity for same-domain-prior-runs scope
    domain_scope_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    domain_scope_version: Mapped[str | None] = mapped_column(String(20), nullable=True)


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


class NotificationDB(Base):
    """Notification for the notification center (BATCH-49)."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_id", "user_id"),
        Index("ix_notifications_read", "read"),
        Index("ix_notifications_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
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

    # Deduplication (BATCH-42)
    canonical_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    pipeline_run: Mapped["PipelineRun | None"] = relationship(back_populates="gaps")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class ResearchClaim(Base):
    """Structured claim extracted from research papers (BATCH-122)."""
    __tablename__ = "research_claims"
    __table_args__ = (
        Index("ix_research_claims_paper_id", "source_paper_id"),
        Index("ix_research_claims_type", "claim_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_paper_id: Mapped[str] = mapped_column(String(256), nullable=False)
    source_section: Mapped[str] = mapped_column(String(50), default="abstract")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)

    # METHOD-specific
    method_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    method_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # RESULT-specific
    dataset: Mapped[str | None] = mapped_column(String(200), nullable=True)
    metric: Mapped[str | None] = mapped_column(String(100), nullable=True)
    value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    baseline_method: Mapped[str | None] = mapped_column(String(200), nullable=True)
    baseline_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # LIMITATION-specific
    limitation_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    acknowledged: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # FUTURE_WORK-specific
    feasibility: Mapped[str | None] = mapped_column(String(20), nullable=True)
    potential_impact: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # COMPARISON-specific
    compared_to: Mapped[str | None] = mapped_column(String(200), nullable=True)
    relationship: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Extra JSON (constraints, etc.)
    extra_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class ExperimentResult(Base):
    """Stores experiment execution results for ideas (BATCH-66)."""
    __tablename__ = "experiment_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    idea_id: Mapped[int] = mapped_column(Integer, ForeignKey("ideas.id"), nullable=False)
    code_md: Mapped[str] = mapped_column(Text, nullable=False)
    stdout: Mapped[str] = mapped_column(Text, default="")
    stderr: Mapped[str] = mapped_column(Text, default="")
    exit_code: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    execution_time_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class RunEvent(Base):
    """Append-only event outbox for SSE/WS progress streaming.

    Replaces process-local ``_progress_queues``. Events are durable:
    a reconnecting SSE client can replay from ``Last-Event-ID``.
    """

    __tablename__ = "run_events"
    __table_args__ = (
        Index("uq_run_events_run_id_seq", "run_id", "seq", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pipeline_runs.id"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False, comment="Per-run monotonic sequence")
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class RunCancellation(Base):
    """Durable cancellation request.

    Replaces process-local ``_cancel_events``. A cancellation survives
    process restart so a cancelled run stays cancelled.
    """

    __tablename__ = "run_cancellations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pipeline_runs.id"), nullable=False, index=True
    )
    run_id_str: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class RunWorker(Base):
    """Durable worker lease tracking.

    Replaces process-local ``_background_tasks``. A run becomes running
    only if no active owner exists. Stale heartbeat marks the worker
    orphaned so the run can resume from checkpoint.
    """

    __tablename__ = "run_workers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pipeline_runs.id"), nullable=False, index=True
    )
    run_id_str: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    worker_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|orphaned|completed
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_heartbeat: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ProposalSectionRevision(Base):
    """Append-only revision history for proposal section text.

    Every change to a proposal section — pipeline origin, user-triggered
    refinement, or rollback — creates a new row. Rows are never updated
    or deleted. Includes SHA-256 content hashes for optimistic concurrency.
    """

    __tablename__ = "proposal_section_revisions"
    __table_args__ = (
        Index("ix_psr_proposal_section_created", "proposal_id", "section_key", "created_at"),
        Index("ix_psr_proposal_created", "proposal_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proposal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("proposals.id"), nullable=False,
    )
    section_key: Mapped[str] = mapped_column(String(50), nullable=False)
    section_text: Mapped[str] = mapped_column(Text, nullable=False)
    section_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    trigger: Mapped[str] = mapped_column(String(30), nullable=False)
    trigger_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_receipt_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_checks_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )


class GovernanceDecision(Base):
    """Append-only governance decision per idea.

    Every human review decision (approved / denied / needs_changes)
    creates a new row. Rows are never updated or deleted.
    """

    __tablename__ = "governance_decisions"
    __table_args__ = (
        Index("ix_governance_decisions_idea_id", "idea_id"),
        Index("ix_governance_decisions_created_at", "created_at"),
        Index("ix_governance_decisions_idea_created", "idea_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    idea_id: Mapped[int] = mapped_column(Integer, ForeignKey("ideas.id"), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    reviewer: Mapped[str] = mapped_column(String(128), nullable=False, default="anonymous")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )


# STOPGAP: this quarantine routes around the absence of an ownership contract
# on proposal.sections (multiple writers across synthesis/adversarial/deepening,
# multiple readers across API/export/QC/refine). It does not establish that
# contract. When the contract lands, this side-channel should be revisited —
# the right fix is preventing fabrication at synthesis, not redacting it at read.
class QuarantinedCitation(Base):
    """Append-only record of a fabricated citation found by citation_audit.

    One row per (proposal, section, ref_index) per audit run. Rows are never
    updated or deleted — they form the historical audit trail. A citation
    quarantined in run N and re-audited in run N+1 produces a new row, not an
    update. Render-time substitution (render_quarantined_view) applies rows
    only where the [SOURCE-N] marker still exists in the current section text
    — so a human refine that removes the citation makes the row inert without
    invalidating the audit record.
    """

    __tablename__ = "quarantined_citations"
    __table_args__ = (
        Index("ix_qc_proposal_section", "proposal_id", "section_key"),
        Index("ix_qc_audit_run", "audit_run_id"),
        Index("ix_qc_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proposal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("proposals.id"), nullable=False,
    )
    section_key: Mapped[str] = mapped_column(String(50), nullable=False)
    ref_index: Mapped[int] = mapped_column(Integer, nullable=False)
    audit_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )


# ═════════════════════════════════════════════════════════════════
# P0.1: Corpus Provenance — run-scoped paper ownership
#
# Three tables establishing an auditable relational boundary around each
# new pipeline run's corpus:
#
#   SearchQuery     — logical queries executed during literature search
#   RunPaper        — membership of a paper in a run's working corpus
#   PaperDiscovery  — every distinct route through which a paper was found
#
# Design principles:
#   - Canonical papers (the `papers` table) remain globally reusable
#   - Corpus membership is explicitly run-scoped via the join table
#   - Discovery provenance survives both deduplication layers
#   - Legacy runs are marked 'pre_provenance' with no fabricated membership
#   - Deletion: CASCADE from PipelineRun (run-owned), RESTRICT to Paper/SearchQuery
# ═════════════════════════════════════════════════════════════════


class SearchQuery(Base):
    """A logical search query executed during a pipeline run's literature search.

    One row per logical query (not per source execution). Source-specific
    execution details (backend-translated form, status, result count) are
    deferred to P0.2's search_query_executions child table.

    query_key is a deterministic hash of normalized query text, enabling
    idempotent replay across retries and resume without inflating the ledger.
    """

    __tablename__ = "search_queries"
    __table_args__ = (
        UniqueConstraint("run_id", "query_key", name="uq_search_queries_run_key"),
        Index("ix_search_queries_run_id", "run_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False,
    )
    query_key: Mapped[str] = mapped_column(String(32), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    query_type: Mapped[str] = mapped_column(String(30), nullable=False, default="template")
    generation_origin: Mapped[str] = mapped_column(String(30), nullable=False, default="base")
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Source execution fields — all NULL in P0.1 (deferred to P0.2 child table)
    source_target: Mapped[str | None] = mapped_column(String(50), nullable=True)
    executed_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="persisted")
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )


class RunPaper(Base):
    """Membership of a paper in a pipeline run's working corpus.

    This is the run-scoped ownership boundary. A paper may belong to many
    runs — each membership is an independent row. Upsertable via the
    UNIQUE(run_id, paper_id) constraint.
    """

    __tablename__ = "run_papers"
    __table_args__ = (
        UniqueConstraint("run_id", "paper_id", name="uq_run_papers_run_paper"),
        Index("ix_run_papers_run_id", "run_id"),
        Index("ix_run_papers_paper_id", "paper_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False,
    )
    paper_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("papers.id", ondelete="RESTRICT"), nullable=False,
    )
    inclusion_origin: Mapped[str] = mapped_column(
        String(30), nullable=False, default="remote_search",
    )
    inclusion_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="candidate",
    )
    first_discovered_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )
    selected_for_downstream: Mapped[bool] = mapped_column(Boolean, default=False)
    selection_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    exclusion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance_schema_version: Mapped[str] = mapped_column(
        String(20), nullable=False, default="provenance_v1",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class PaperDiscovery(Base):
    """Every distinct route through which a paper entered or re-entered consideration.

    A paper found through two queries across four sources produces four
    discovery rows (one per source/query pair). The same paper has one
    RunPaper membership row.

    discovery_key is a deterministic hash enabling idempotent replay.
    Two records from the same source+query with no source_record_id collapse
    into one discovery event — documented as acceptable.
    """

    __tablename__ = "paper_discoveries"
    __table_args__ = (
        UniqueConstraint("run_id", "discovery_key", name="uq_paper_discoveries_run_key"),
        Index("ix_paper_discoveries_run_paper", "run_id", "paper_id"),
        Index("ix_paper_discoveries_query", "search_query_id"),
        Index("ix_paper_discoveries_execution_id", "execution_id"),
        Index("ix_paper_discoveries_source_result_key", "source_result_key"),
        # Null-bypass: a non-null execution_id MUST carry a search_query_id.
        CheckConstraint(
            "execution_id IS NULL OR search_query_id IS NOT NULL",
            name="ck_paper_discoveries_execution_requires_query",
        ),
        # P0.2.5: governed linkage requires all four identity fields
        CheckConstraint(
            "linkage_schema_version IS NULL "
            "OR ("
            "  linkage_schema_version = 'linkage_v1' "
            "  AND execution_id IS NOT NULL "
            "  AND search_query_id IS NOT NULL "
            "  AND source_result_key IS NOT NULL "
            "  AND discovery_origin = 'remote_search'"
            ")",
            name="ck_paper_discoveries_linkage_governed",
        ),
        # P0.2.5: replay-safe one-to-one: one source-unique result per execution
        UniqueConstraint(
            "execution_id", "source_result_key",
            name="uq_paper_discoveries_execution_result_key",
        ),
        # P0.2.5: triple composite FK enforces execution+query+source consistency
        ForeignKeyConstraint(
            ["execution_id", "search_query_id", "source"],
            ["search_query_executions.id",
             "search_query_executions.search_query_id",
             "search_query_executions.source"],
            name="fk_paper_discoveries_execution_query_source",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False,
    )
    paper_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("papers.id", ondelete="RESTRICT"), nullable=False,
    )
    search_query_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("search_queries.id", ondelete="RESTRICT"), nullable=True,
    )
    # P0.2.1: links this discovery to the specific source-adapter execution
    # that found the paper. Nullable — legacy P0.1 rows keep this NULL.
    # The composite FK in __table_args__ enforces same-query consistency.
    execution_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    # P0.2.5: stable SHA-256 identity of the source-unique result that produced
    # this discovery. Uses the exact P0.2.4 dedup identity function.
    source_result_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # P0.2.5: linkage contract marker. NULL for legacy/non-query discoveries.
    linkage_schema_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_record_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discovery_origin: Mapped[str] = mapped_column(
        String(30), nullable=False, default="remote_search",
    )
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )
    raw_identifier: Mapped[str | None] = mapped_column(Text, nullable=True)
    deduplication_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unique",
    )
    canonicalization_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    discovery_key: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )


class SearchQueryExecution(Base):
    """One logical source-adapter invocation for one logical search query.

    A SearchQuery (logical intent) fans out across N sources; each source
    attempt is a distinct execution. Transport retries, pagination, and
    multi-call adapter behavior are internal to this one row — there is
    exactly one execution per (query, source) pair, enforced by UNIQUE.

    Run ownership is obtained via the indexed join to search_queries.run_id;
    there is intentionally NO run_id column here, eliminating cross-run
    ownership inconsistency.

    Lifecycle (documented; the DB enforces only the CHECK constraints):
        pending   row exists, no source contact begun
        running   at least one outbound attempt started
        success   source invocation completed successfully
        partial   usable results exist, but part of the invocation failed
        failed    no usable completion (non-timeout failure)
        timeout   invocation exceeded its time limit
        skipped   intentionally never began

    attempt_count includes the first outbound attempt:
        pending/skipped = 0, first contact = 1, one retry = 2.

    translated_query stores the sanitized source-level query representation:
    no credentials, no secret-bearing URLs, not per-transport-request.

    Count columns are NULL until P0.2.4 reconciliation. accounting_status
    is 'incomplete' (this migration's default) and must not be set to
    'reconciled' until P0.2.4 populates and verifies all four counts.

    source is stored canonical (lowercase, trimmed) — the CHECK constraint
    rejects non-canonical input so casing/whitespace cannot bypass the
    replay-uniqueness constraint.
    """

    __tablename__ = "search_query_executions"
    __table_args__ = (
        UniqueConstraint(
            "search_query_id", "source",
            name="uq_search_query_executions_query_source",
        ),
        UniqueConstraint(
            "id", "search_query_id",
            name="uq_search_query_executions_id_query",
        ),
        # P0.2.5: triple uniqueness for the discovery FK
        UniqueConstraint(
            "id", "search_query_id", "source",
            name="uq_search_query_executions_id_query_source",
        ),
        Index("ix_search_query_executions_query_id", "search_query_id"),
        Index(
            "ix_search_query_executions_status_category",
            "status", "failure_category",
        ),
        CheckConstraint(
            "source = lower(trim(source)) AND length(trim(source)) > 0",
            name="ck_search_query_executions_source_canonical",
        ),
        CheckConstraint(
            "status IN ('pending','running','success','partial',"
            "'failed','timeout','skipped')",
            name="ck_search_query_executions_status",
        ),
        CheckConstraint(
            "accounting_status IN ('incomplete','reconciled')",
            name="ck_search_query_executions_accounting_status",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_search_query_executions_attempt_count_nonnegative",
        ),
        CheckConstraint(
            "raw_result_count IS NULL OR raw_result_count >= 0",
            name="ck_search_query_executions_raw_count_nonnegative",
        ),
        CheckConstraint(
            "normalized_result_count IS NULL OR normalized_result_count >= 0",
            name="ck_search_query_executions_normalized_count_nonnegative",
        ),
        CheckConstraint(
            "rejected_result_count IS NULL OR rejected_result_count >= 0",
            name="ck_search_query_executions_rejected_count_nonnegative",
        ),
        CheckConstraint(
            "source_unique_count IS NULL OR source_unique_count >= 0",
            name="ck_search_query_executions_source_unique_count_nonnegative",
        ),
        # ── P0.2.3: execution metadata constraints ──
        CheckConstraint(
            "execution_metadata_version IS NULL "
            "OR execution_metadata_version = 'execution_v1'",
            name="ck_search_query_executions_metadata_version",
        ),
        CheckConstraint(
            "failure_category IS NULL OR failure_category IN ("
            "'source_unavailable','query_translation','authentication',"
            "'authorization','rate_limit','timeout','transport',"
            "'provider_rejection','provider_internal','response_parse',"
            "'adapter_contract','configuration','internal')",
            name="ck_search_query_executions_failure_category",
        ),
        CheckConstraint(
            "failure_code IS NULL "
            "OR (failure_code = lower(trim(failure_code)) "
            "AND length(trim(failure_code)) BETWEEN 1 AND 80)",
            name="ck_search_query_executions_failure_code",
        ),
        CheckConstraint(
            "execution_metadata_version IS NULL "
            "OR (status IN ('pending','running') "
            "    AND failure_category IS NULL "
            "    AND failure_code IS NULL "
            "    AND error_detail IS NULL) "
            "OR (status = 'success' "
            "    AND failure_category IS NULL "
            "    AND failure_code IS NULL "
            "    AND error_detail IS NULL "
            "    AND completed_at IS NOT NULL) "
            "OR (status IN ('partial','failed','timeout','skipped') "
            "    AND failure_category IS NOT NULL "
            "    AND failure_code IS NOT NULL "
            "    AND error_detail IS NOT NULL "
            "    AND completed_at IS NOT NULL)",
            name="ck_search_query_executions_metadata_completeness",
        ),
        CheckConstraint(
            "execution_metadata_version IS NULL "
            "OR status != 'timeout' "
            "OR failure_category = 'timeout'",
            name="ck_search_query_executions_timeout_category",
        ),
        CheckConstraint(
            "execution_metadata_version IS NULL "
            "OR attempt_count = 0 "
            "OR translated_query IS NOT NULL",
            name="ck_search_query_executions_attempted_has_plan",
        ),
        CheckConstraint(
            "translated_query IS NULL OR length(translated_query) <= 4096",
            name="ck_search_query_executions_translated_query_size",
        ),
        CheckConstraint(
            "execution_metadata_version IS NULL "
            "OR status != 'skipped' "
            "OR (attempt_count = 0 AND attempted_at IS NULL)",
            name="ck_search_query_executions_skipped_no_attempts",
        ),
        # ── P0.2.4: accounting reconciliation constraints ──
        CheckConstraint(
            "accounting_schema_version IS NULL "
            "OR accounting_schema_version = 'accounting_v1'",
            name="ck_search_query_executions_accounting_schema_version",
        ),
        CheckConstraint(
            "("
            "  accounting_status = 'incomplete' "
            "  AND accounting_schema_version IS NULL "
            "  AND raw_result_count IS NULL "
            "  AND normalized_result_count IS NULL "
            "  AND rejected_result_count IS NULL "
            "  AND source_unique_count IS NULL "
            ") OR ("
            "  accounting_status = 'reconciled' "
            "  AND accounting_schema_version = 'accounting_v1' "
            "  AND raw_result_count IS NOT NULL "
            "  AND normalized_result_count IS NOT NULL "
            "  AND rejected_result_count IS NOT NULL "
            "  AND source_unique_count IS NOT NULL "
            "  AND raw_result_count = "
            "      normalized_result_count + rejected_result_count "
            "  AND source_unique_count <= normalized_result_count "
            ")",
            name="ck_search_query_executions_accounting_reconciled",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    search_query_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("search_queries.id", ondelete="CASCADE"), nullable=False,
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    translated_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    raw_result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    normalized_result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rejected_result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_unique_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    accounting_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="incomplete",
    )
    # P0.2.3: structured failure metadata + version marker.
    # NULL for legacy P0.2.2 rows (no fabricated classifications).
    failure_category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    execution_metadata_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # P0.2.4: accounting schema version marker. NULL for legacy/incomplete,
    # 'accounting_v1' when all four counts follow the reconciliation contract.
    accounting_schema_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ExecutionDiscoveryLinkage(Base):
    """Linkage ledger: one row per execution tracking discovery-linkage state.

    Created atomically with terminal accounting. An execution that finishes
    successfully gets a 'pending' row (expected to be linked to discoveries
    by the governed corpus persistence). An incomplete execution gets
    'not_applicable'. This prevents ambiguous states where
    source_unique_count > 0 but no PaperDiscovery rows exist.
    """

    __tablename__ = "execution_discovery_linkages"
    __table_args__ = (
        CheckConstraint(
            "linkage_schema_version = 'linkage_v1'",
            name="ck_edl_linkage_schema_version",
        ),
        CheckConstraint(
            "status IN ('pending','linked','failed','not_applicable')",
            name="ck_edl_status",
        ),
        CheckConstraint(
            "linkage_attempt_count >= 0",
            name="ck_edl_attempt_count_nonnegative",
        ),
        CheckConstraint(
            "expected_discovery_count IS NULL OR expected_discovery_count >= 0",
            name="ck_edl_expected_count_nonnegative",
        ),
        CheckConstraint(
            "linked_discovery_count IS NULL OR linked_discovery_count >= 0",
            name="ck_edl_linked_count_nonnegative",
        ),
        CheckConstraint(
            "("
            "  status = 'pending' "
            "  AND expected_discovery_count IS NOT NULL "
            "  AND linked_discovery_count IS NULL "
            "  AND completed_at IS NULL "
            ") OR ("
            "  status = 'linked' "
            "  AND expected_discovery_count IS NOT NULL "
            "  AND linked_discovery_count = expected_discovery_count "
            "  AND completed_at IS NOT NULL "
            ") OR ("
            "  status = 'failed' "
            "  AND expected_discovery_count IS NOT NULL "
            "  AND linked_discovery_count IS NULL "
            "  AND last_error_detail IS NOT NULL "
            "  AND completed_at IS NOT NULL "
            ") OR ("
            "  status = 'not_applicable' "
            "  AND expected_discovery_count IS NULL "
            "  AND linked_discovery_count IS NULL "
            "  AND completed_at IS NOT NULL "
            ")",
            name="ck_edl_state_consistency",
        ),
    )

    execution_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("search_query_executions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    linkage_schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    expected_discovery_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    linked_discovery_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    linkage_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class SearchQueryExecutionScope(Base):
    """Durable snapshot of the intended source set for a logical query.

    P0.2.6: Allows run-level reconciliation to verify that the actual
    execution set exactly matches the intended set — no missing or
    extra executions. Created atomically with the pending execution rows.
    """

    __tablename__ = "search_query_execution_scopes"
    __table_args__ = (
        CheckConstraint(
            "scope_schema_version = 'execution_scope_v1'",
            name="ck_sqes_scope_schema_version",
        ),
        CheckConstraint(
            "intended_source_count >= 0",
            name="ck_sqes_source_count_nonnegative",
        ),
    )

    search_query_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("search_queries.id", ondelete="CASCADE"),
        primary_key=True,
    )
    scope_schema_version: Mapped[str] = mapped_column(String(30), nullable=False)
    intended_sources_json: Mapped[str] = mapped_column(Text, nullable=False)
    intended_source_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_set_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )


class RunSearchReconciliation(Base):
    """Run-level search reconciliation ledger (P0.2.6).

    One row per PipelineRun. Proves internal completeness from logical
    query intent through final run-corpus membership. Aggregate counts
    are NULL until status='reconciled'.
    """

    __tablename__ = "run_search_reconciliations"
    __table_args__ = (
        Index("ix_rsr_status", "status"),
        CheckConstraint(
            "reconciliation_schema_version = 'run_reconciliation_v1'",
            name="ck_rsr_schema_version",
        ),
        CheckConstraint(
            "status IN ('pending','blocked','reconciled','failed')",
            name="ck_rsr_status",
        ),
        CheckConstraint(
            "execution_posture IS NULL "
            "OR execution_posture IN ('healthy','degraded','no_usable_sources')",
            name="ck_rsr_execution_posture",
        ),
        CheckConstraint(
            "reconciliation_attempt_count >= 0",
            name="ck_rsr_attempt_count_nonnegative",
        ),
        CheckConstraint(
            "status != 'reconciled' OR ("
            "  logical_query_count IS NOT NULL"
            "  AND expected_execution_count IS NOT NULL"
            "  AND actual_execution_count IS NOT NULL"
            "  AND terminal_execution_count IS NOT NULL"
            "  AND success_execution_count IS NOT NULL"
            "  AND partial_execution_count IS NOT NULL"
            "  AND failed_execution_count IS NOT NULL"
            "  AND timeout_execution_count IS NOT NULL"
            "  AND skipped_execution_count IS NOT NULL"
            "  AND reconciled_accounting_execution_count IS NOT NULL"
            "  AND incomplete_accounting_execution_count IS NOT NULL"
            "  AND source_unique_result_count IS NOT NULL"
            "  AND linked_discovery_count IS NOT NULL"
            "  AND remote_canonical_paper_count IS NOT NULL"
            "  AND nonremote_canonical_paper_count IS NOT NULL"
            "  AND remote_only_paper_count IS NOT NULL"
            "  AND nonremote_only_paper_count IS NOT NULL"
            "  AND multi_origin_paper_count IS NOT NULL"
            "  AND run_paper_count IS NOT NULL"
            "  AND canonicalization_reduction_count IS NOT NULL"
            "  AND unexplained_membership_count IS NOT NULL"
            "  AND unowned_discovery_paper_count IS NOT NULL"
            "  AND input_fingerprint IS NOT NULL"
            "  AND execution_posture IS NOT NULL"
            "  AND completed_at IS NOT NULL"
            "  AND issue_code IS NULL"
            "  AND issue_detail IS NULL)",
            name="ck_rsr_reconciled_completeness",
        ),
        CheckConstraint(
            "status != 'reconciled' OR expected_execution_count = actual_execution_count",
            name="ck_rsr_expected_equals_actual",
        ),
        CheckConstraint(
            "status != 'reconciled' OR actual_execution_count = terminal_execution_count",
            name="ck_rsr_actual_equals_terminal",
        ),
        CheckConstraint(
            "status != 'reconciled' OR terminal_execution_count = "
            "success_execution_count + partial_execution_count "
            "+ failed_execution_count + timeout_execution_count + skipped_execution_count",
            name="ck_rsr_terminal_decomposition",
        ),
        CheckConstraint(
            "status != 'reconciled' OR actual_execution_count = "
            "reconciled_accounting_execution_count + incomplete_accounting_execution_count",
            name="ck_rsr_accounting_decomposition",
        ),
        CheckConstraint(
            "status != 'reconciled' OR source_unique_result_count = linked_discovery_count",
            name="ck_rsr_source_unique_equals_linked",
        ),
        CheckConstraint(
            "status != 'reconciled' OR unexplained_membership_count = 0",
            name="ck_rsr_no_unexplained_membership",
        ),
        CheckConstraint(
            "status != 'reconciled' OR unowned_discovery_paper_count = 0",
            name="ck_rsr_no_unowned_discovery",
        ),
        CheckConstraint(
            "status != 'reconciled' OR canonicalization_reduction_count = "
            "linked_discovery_count - remote_canonical_paper_count",
            name="ck_rsr_canonicalization_reduction",
        ),
        CheckConstraint(
            "status != 'reconciled' OR remote_canonical_paper_count = "
            "remote_only_paper_count + multi_origin_paper_count",
            name="ck_rsr_remote_decomposition",
        ),
        CheckConstraint(
            "status != 'reconciled' OR nonremote_canonical_paper_count = "
            "nonremote_only_paper_count + multi_origin_paper_count",
            name="ck_rsr_nonremote_decomposition",
        ),
        CheckConstraint(
            "status != 'reconciled' OR run_paper_count = "
            "remote_only_paper_count + nonremote_only_paper_count + multi_origin_paper_count",
            name="ck_rsr_membership_decomposition",
        ),
        CheckConstraint(
            "status != 'blocked' OR (issue_code IS NOT NULL AND issue_detail IS NOT NULL "
            "AND completed_at IS NULL)",
            name="ck_rsr_blocked_has_issue",
        ),
        CheckConstraint(
            "status != 'failed' OR (issue_code IS NOT NULL AND issue_detail IS NOT NULL "
            "AND completed_at IS NOT NULL)",
            name="ck_rsr_failed_has_issue",
        ),
        CheckConstraint(
            "status = 'reconciled' OR logical_query_count IS NULL",
            name="ck_rsr_nonreconciled_null_counts",
        ),
    )

    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    reconciliation_schema_version: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    execution_posture: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reconciliation_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    issue_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    issue_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Aggregate counts (nullable until reconciled)
    logical_query_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_execution_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_execution_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    terminal_execution_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success_execution_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    partial_execution_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failed_execution_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timeout_execution_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    skipped_execution_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reconciled_accounting_execution_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    incomplete_accounting_execution_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_unique_result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    linked_discovery_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remote_canonical_paper_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nonremote_canonical_paper_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remote_only_paper_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nonremote_only_paper_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    multi_origin_paper_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    run_paper_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    canonicalization_reduction_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unexplained_membership_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unowned_discovery_paper_count: Mapped[int | None] = mapped_column(Integer, nullable=True)


class GlobalLibraryMembership(Base):
    """Explicit global-library paper membership (P0.3.1).

    No paper becomes a global-library member merely because it exists in
    ``papers`` or the vector collection. Membership must be explicit.
    """

    __tablename__ = "global_library_memberships"
    __table_args__ = (
        CheckConstraint(
            "membership_schema_version = 'global_library_v1'",
            name="ck_glm_schema_version",
        ),
        CheckConstraint(
            "status IN ('active', 'removed')",
            name="ck_glm_status",
        ),
        CheckConstraint(
            "membership_origin IS NULL OR membership_origin IN "
            "('user_curated', 'admin_import', 'verified_migration')",
            name="ck_glm_origin",
        ),
        CheckConstraint(
            "status != 'active' OR removed_at IS NULL",
            name="ck_glm_active_no_removed_at",
        ),
        CheckConstraint(
            "status != 'removed' OR removed_at IS NOT NULL",
            name="ck_glm_removed_has_removed_at",
        ),
    )

    paper_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("papers.id", ondelete="CASCADE"),
        primary_key=True,
    )
    membership_schema_version: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    membership_origin: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EmbeddingProfile(Base):
    """Durable embedding-profile declaration (P0.3.2).

    P0.3.2 supports only ``unverified`` — the profile is declarative.
    P0.4 will expand the verification lifecycle.
    """

    __tablename__ = "embedding_profiles"
    __table_args__ = (
        CheckConstraint("profile_schema_version = 'embedding_profile_v1'", name="ck_ep_schema_version"),
        CheckConstraint("verification_status = 'unverified'", name="ck_ep_verification_status"),
        CheckConstraint("dimension > 0", name="ck_ep_dimension_positive"),
        UniqueConstraint("collection_name", name="uq_ep_collection_name"),
    )

    profile_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    profile_schema_version: Mapped[str] = mapped_column(String(30), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    normalization_policy: Mapped[str] = mapped_column(String(80), nullable=False)
    chunking_schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    collection_name: Mapped[str] = mapped_column(String(120), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )


class VectorIndexRecord(Base):
    """Canonical vector lifecycle record (P0.3.2).

    A vector may participate in governed retrieval only when
    ``index_status = 'indexed'`` and the backend has been verified.
    """

    __tablename__ = "vector_index_records"
    __table_args__ = (
        UniqueConstraint("vector_record_id", name="uq_vir_vector_record_id"),
        UniqueConstraint(
            "paper_id", "chunk_key", "content_hash", "embedding_profile_id",
            name="uq_vir_chunk_identity",
        ),
        Index("ix_vir_paper_id", "paper_id"),
        Index("ix_vir_profile_status", "embedding_profile_id", "index_status"),
        CheckConstraint("vector_store = 'chroma'", name="ck_vir_vector_store"),
        CheckConstraint("index_schema_version = 'vector_index_v1'", name="ck_vir_index_schema"),
        CheckConstraint(
            "content_kind IN ('title_abstract', 'abstract', 'full_text_chunk', 'metadata')",
            name="ck_vir_content_kind",
        ),
        CheckConstraint(
            "index_status IN ('pending','indexing','indexed','failed','stale','deleting','deleted')",
            name="ck_vir_index_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_vir_attempt_count_nonnegative"),
        CheckConstraint(
            "length(vector_record_id) = 64 AND vector_record_id = lower(vector_record_id)",
            name="ck_vir_vector_record_id_format",
        ),
        CheckConstraint(
            "length(content_hash) = 64 AND content_hash = lower(content_hash)",
            name="ck_vir_content_hash_format",
        ),
        CheckConstraint(
            "length(embedding_profile_id) = 64 AND embedding_profile_id = lower(embedding_profile_id)",
            name="ck_vir_embedding_profile_id_format",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vector_record_id: Mapped[str] = mapped_column(String(64), nullable=False)
    paper_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("papers.id", ondelete="RESTRICT"), nullable=False,
    )
    chunk_key: Mapped[str] = mapped_column(String(255), nullable=False)
    content_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_profile_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("embedding_profiles.profile_id", ondelete="RESTRICT"),
        nullable=False,
    )
    vector_store: Mapped[str] = mapped_column(String(40), nullable=False, default="chroma")
    collection_name: Mapped[str] = mapped_column(String(120), nullable=False)
    index_schema_version: Mapped[str] = mapped_column(String(30), nullable=False, default="vector_index_v1")
    index_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    indexing_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    backend_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    stale_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleting_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# ── P0.2.7: Provenance immutability enforcement ─────────────────────


class ProvenanceContractMutationError(Exception):
    """Raised when an attempt is made to mutate provenance_version or
    legacy_provenance_reason after run creation."""


@event.listens_for(PipelineRun, "before_update")
def _prevent_provenance_contract_mutation(mapper, connection, target):
    """ORM-level guard: provenance_version and legacy_provenance_reason are
    immutable after insertion. A no-op assignment (same value) is allowed."""
    from sqlalchemy import inspect as sa_inspect

    state = sa_inspect(target)
    for attr_name in ("provenance_version", "legacy_provenance_reason"):
        history = state.attrs[attr_name].history
        if history.has_changes():
            raise ProvenanceContractMutationError(
                f"{attr_name} is immutable after run creation "
                f"(run_id={target.id}). Create a new run with the desired "
                f"provenance contract instead."
            )
