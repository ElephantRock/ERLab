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
    text,
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
    # Phase 1 1C: persisted full-paper artifact. The PaperSynthesisStage
    # previously wrote the paper only to in-memory proposal.metadata and it was
    # lost on process exit. These columns give the paper a DB home on the
    # existing Proposal row (one paper per proposal). paper_meta_json carries
    # the synthesis metadata (status, word_count, venue, model, source_count,
    # synthesis_strategy, generated_at) so the API can expose state without
    # parsing the markdown.
    paper_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    paper_meta_json: Mapped[str | None] = mapped_column(Text, nullable=True)

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
        # Schema-version literal must match EMBEDDING_PROFILE_V1 in
        # backend/pipeline/vector_contracts.py (kept as SQL text here to
        # avoid a layering inversion: db/models.py is the lowest layer and
        # must not import transport contracts).
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
        Index("ix_vir_capability_binding", "capability_binding_id"),
        CheckConstraint("vector_store = 'chroma'", name="ck_vir_vector_store"),
        # P0.4A2: index_schema_version now allows both v1 and v2.
        # Literal strings mirror VECTOR_INDEX_V1/V2 in vector_contracts.py.
        CheckConstraint(
            "index_schema_version IN ('vector_index_v1', 'vector_index_v2')",
            name="ck_vir_index_schema",
        ),
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
        # P0.4A2: capability contract — v1+v0 with NULL capability fields,
        # or v2+v1 with binding set and check set on indexed completion.
        # The generation check is NULL during pending/indexing (it is
        # populated atomically when the indexed status is published) and
        # NOT NULL once indexed. Binding is set at creation time.
        CheckConstraint(
            "(index_schema_version = 'vector_index_v1' "
            "AND embedding_contract_version = 'pre_capability_v0' "
            "AND capability_binding_id IS NULL "
            "AND generation_capability_check_id IS NULL) "
            "OR (index_schema_version = 'vector_index_v2' "
            "AND embedding_contract_version = 'capability_v1' "
            "AND capability_binding_id IS NOT NULL "
            "AND (index_status != 'indexed' OR generation_capability_check_id IS NOT NULL))",
            name="ck_vir_capability_contract",
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
    # P0.4A2: capability evidence (NULL on v1 rows, NOT NULL on v2 rows)
    embedding_contract_version: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pre_capability_v0",
    )
    capability_binding_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generation_capability_check_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class VectorRetrievalEvent(Base):
    """Immutable retrieval audit event (P0.3.3).

    One row per governed vector retrieval. Snapshots the scope, eligible
    records, and ranked results so P0.3.6 can prove which scope influenced
    a stage.
    """

    __tablename__ = "vector_retrieval_events"
    __table_args__ = (
        UniqueConstraint("run_id", "stage_name", "retrieval_key", name="uq_vre_run_stage_key"),
        Index("ix_vre_run_id", "run_id"),
        Index("ix_vre_status", "status"),
        CheckConstraint("requested_top_k > 0", name="ck_vre_top_k_positive"),
        CheckConstraint("attempt_count >= 0", name="ck_vre_attempt_count_nonnegative"),
        CheckConstraint("status IN ('pending','running','success','failed')", name="ck_vre_status"),
        CheckConstraint(
            "coverage_status IN ('empty_scope','complete','partial','none')",
            name="ck_vre_coverage_status",
        ),
        CheckConstraint(
            "unindexed_paper_count = allowed_paper_count - indexed_paper_count",
            name="ck_vre_unindexed_equation",
        ),
        CheckConstraint("indexed_paper_count <= allowed_paper_count", name="ck_vre_indexed_le_allowed"),
        CheckConstraint(
            "failure_category IS NULL OR failure_category IN "
            "('scope_resolution','query_validation','index_coverage',"
            "'backend','result_validation','contract','internal')",
            name="ck_vre_failure_category",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False,
    )
    stage_name: Mapped[str] = mapped_column(String(100), nullable=False)
    retrieval_key: Mapped[str] = mapped_column(String(160), nullable=False)
    request_schema_version: Mapped[str] = mapped_column(String(30), nullable=False)
    scope_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    scope_schema_version: Mapped[str] = mapped_column(String(30), nullable=False)
    scope_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_profile_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("embedding_profiles.profile_id", ondelete="RESTRICT"), nullable=False,
    )
    profile_verification_status_snapshot: Mapped[str] = mapped_column(String(20), nullable=False, default="unverified")
    query_vector_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    allow_partial_index_coverage: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allowed_paper_count: Mapped[int] = mapped_column(Integer, nullable=False)
    indexed_paper_count: Mapped[int] = mapped_column(Integer, nullable=False)
    unindexed_paper_count: Mapped[int] = mapped_column(Integer, nullable=False)
    eligible_vector_record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    coverage_status: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    backend_batch_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    returned_result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # P0.4A2: capability evidence for query embedding and vector eligibility.
    # Historical rows default to pre_capability_v0. Capability-v1 queries
    # record their binding/check; vector_eligibility_contract stays v0
    # until the profile's binding is activated.
    query_embedding_contract_version: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pre_capability_v0",
    )
    vector_eligibility_contract_version: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pre_capability_v0",
    )
    query_capability_binding_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    query_capability_check_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    binding_activation_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class VectorRetrievalScopePaper(Base):
    """Allowed-paper snapshot for a retrieval event."""

    __tablename__ = "vector_retrieval_scope_papers"

    retrieval_event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vector_retrieval_events.id", ondelete="CASCADE"), primary_key=True,
    )
    paper_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("papers.id", ondelete="RESTRICT"), primary_key=True,
    )
    is_indexed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class VectorRetrievalEligibleRecord(Base):
    """Exact eligible backend candidate snapshot for a retrieval event."""

    __tablename__ = "vector_retrieval_eligible_records"

    retrieval_event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vector_retrieval_events.id", ondelete="CASCADE"), primary_key=True,
    )
    vector_record_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("vector_index_records.vector_record_id", ondelete="RESTRICT"),
        primary_key=True,
    )


class VectorRetrievalResult(Base):
    """Ranked validated result for a retrieval event.

    The composite FK to eligible_records database-enforces that every
    result belonged to the frozen candidate snapshot.
    """

    __tablename__ = "vector_retrieval_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["retrieval_event_id", "vector_record_id"],
            ["vector_retrieval_eligible_records.retrieval_event_id",
             "vector_retrieval_eligible_records.vector_record_id"],
            name="fk_vrr_eligible",
        ),
        UniqueConstraint("retrieval_event_id", "vector_record_id", name="uq_vrr_no_dup_vector"),
        CheckConstraint("rank > 0", name="ck_vrr_rank_positive"),
    )

    retrieval_event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vector_retrieval_events.id", ondelete="CASCADE"), primary_key=True,
    )
    rank: Mapped[int] = mapped_column(Integer, primary_key=True)
    vector_record_id: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_distance: Mapped[float] = mapped_column(Float, nullable=False)


class LegacyVectorInventoryRun(Base):
    """Immutable legacy collection scan and reindex attempt (P0.3.5)."""

    __tablename__ = "legacy_vector_inventory_runs"
    __table_args__ = (
        CheckConstraint(
            "inventory_schema_version = 'legacy_vector_inventory_v1'",
            name="ck_lvir_schema_version",
        ),
        CheckConstraint(
            "status IN ('pending','scanning','scanned','reindexing','complete','failed')",
            name="ck_lvir_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inventory_schema_version: Mapped[str] = mapped_column(String(30), nullable=False)
    vector_store: Mapped[str] = mapped_column(String(40), nullable=False, default="chroma")
    collection_name: Mapped[str] = mapped_column(String(120), nullable=False)
    target_embedding_profile_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("embedding_profiles.profile_id", ondelete="RESTRICT"), nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    source_record_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mapped_record_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ambiguous_record_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unmapped_record_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    invalid_record_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    identity_conflict_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distinct_target_paper_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    newly_indexed_target_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    already_indexed_target_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duplicate_target_record_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_unavailable_target_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reindex_failed_target_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_snapshot_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class LegacyVectorInventoryRecord(Base):
    """One legacy Chroma record's mapping and disposition (P0.3.5)."""

    __tablename__ = "legacy_vector_inventory_records"
    __table_args__ = (
        Index("ix_lvirec_run_mapping", "inventory_run_id", "mapping_status"),
        CheckConstraint(
            "mapping_status IN ('mapped','ambiguous','unmapped','invalid','identity_conflict')",
            name="ck_lvirec_mapping_status",
        ),
        CheckConstraint(
            "mapping_method IS NULL OR mapping_method IN "
            "('paper_id_exact','doi_exact','source_identifier_exact',"
            "'title_author_year_exact','none')",
            name="ck_lvirec_mapping_method",
        ),
        CheckConstraint(
            "disposition IS NULL OR disposition IN "
            "('reindexed','already_indexed','duplicate_target',"
            "'quarantined_ambiguous','quarantined_unmapped',"
            "'quarantined_invalid','quarantined_identity_conflict',"
            "'content_unavailable','reindex_failed')",
            name="ck_lvirec_disposition",
        ),
    )

    inventory_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("legacy_vector_inventory_runs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    legacy_record_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    legacy_record_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    legacy_metadata_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    legacy_document_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    legacy_embedding_dimension: Mapped[int | None] = mapped_column(Integer, nullable=True)
    legacy_identity_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    mapping_schema_version: Mapped[str] = mapped_column(String(30), nullable=False)
    mapping_status: Mapped[str] = mapped_column(String(30), nullable=False)
    mapping_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    mapped_paper_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    candidate_match_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    identity_conflict_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    disposition: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_vector_record_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LegacyVectorReindexTarget(Base):
    """Authoritative target-level reindex lifecycle (P0.3.5B1).

    Several legacy records may map to one canonical paper/chunk/profile
    target. This table deduplicates them into one indexing operation.
    """

    __tablename__ = "legacy_vector_reindex_targets"
    __table_args__ = (
        UniqueConstraint(
            "inventory_run_id", "paper_id", "chunk_key", "embedding_profile_id",
            name="uq_lvrt_target_identity",
        ),
        Index("ix_lvrt_run_status", "inventory_run_id", "status"),
        CheckConstraint(
            "status IN ('planned','indexing','indexed','already_indexed',"
            "'content_unavailable','failed')",
            name="ck_lvrt_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_lvrt_attempt_count"),
        CheckConstraint("source_record_count >= 1", name="ck_lvrt_source_count"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inventory_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("legacy_vector_inventory_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    paper_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("papers.id", ondelete="RESTRICT"), nullable=False,
    )
    chunk_key: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_profile_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("embedding_profiles.profile_id", ondelete="RESTRICT"),
        nullable=False,
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    target_vector_record_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="planned")
    representative_legacy_record_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source_record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# ── P0.4A1: Capability ledger ────────────────────────────────────────


class EmbeddingCapabilityCheck(Base):
    """Timestamped runtime-health evidence for an embedding capability
    probe (P0.4A1).

    Check-first lifecycle: a pending check is created BEFORE any probe.
    The ``binding_id`` column is NULL while the check is pending, running,
    or failed, and is set ONLY when the probe passes and a binding is
    resolved. This enforces the frozen rule:

        A failed or incomplete probe may create check evidence, but it
        may never create a resolved capability binding.

    Lifecycle::

        pending → running → passed | failed | cancelled
                       ↓ (lease expiry)
                    abandoned

    ``passed``, ``failed``, ``cancelled``, and ``abandoned`` are all
    immutable terminals. Expiry is DERIVED at read time::

        operational_status = "expired"
        when check_status == "passed" AND now > expires_at

    The stored fact that a probe passed is never rewritten to "expired".
    """

    __tablename__ = "embedding_capability_checks"
    __table_args__ = (
        # Authority lookup index: find the latest completed check for a
        # given profile + runtime fingerprint + probe suite.
        Index(
            "ix_ecc_profile_fingerprint_suite",
            "embedding_profile_id",
            "runtime_config_fingerprint",
            "probe_suite_version",
        ),
        Index("ix_ecc_binding_id", "binding_id"),
        Index("ix_ecc_lease_expires_at", "lease_expires_at"),
        # ── Schema-version literal ──
        CheckConstraint(
            "check_schema_version = 'capability_check_v1'",
            name="ck_ecc_schema_version",
        ),
        # ── Status vocabulary ──
        CheckConstraint(
            "check_status IN ('pending','running','passed','failed',"
            "'cancelled','abandoned')",
            name="ck_ecc_check_status",
        ),
        CheckConstraint(
            "probe_kind IN ('document_probe','query_probe','dual_probe')",
            name="ck_ecc_probe_kind",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_ecc_attempt_count"),
        CheckConstraint(
            "provider_request_count >= 0", name="ck_ecc_provider_request_count"
        ),
        # ── Lifecycle completeness (DB-enforced) ──
        # passed → binding present, completed, expires, probed; no failure
        CheckConstraint(
            "check_status != 'passed' OR "
            "(binding_id IS NOT NULL AND completed_at IS NOT NULL "
            "AND expires_at IS NOT NULL AND probed_at IS NOT NULL "
            "AND failure_code IS NULL)",
            name="ck_ecc_passed_completeness",
        ),
        # failed → completed, failure code present, no binding, no expires
        CheckConstraint(
            "check_status != 'failed' OR "
            "(completed_at IS NOT NULL AND failure_code IS NOT NULL "
            "AND binding_id IS NULL AND expires_at IS NULL)",
            name="ck_ecc_failed_completeness",
        ),
        # cancelled → completed, no binding
        CheckConstraint(
            "check_status != 'cancelled' OR "
            "(completed_at IS NOT NULL AND binding_id IS NULL)",
            name="ck_ecc_cancelled_completeness",
        ),
        # abandoned → completed, no binding
        CheckConstraint(
            "check_status != 'abandoned' OR "
            "(completed_at IS NOT NULL AND binding_id IS NULL)",
            name="ck_ecc_abandoned_completeness",
        ),
        # running → claimed + lease; not completed
        CheckConstraint(
            "check_status != 'running' OR "
            "(claimed_at IS NOT NULL AND lease_expires_at IS NOT NULL "
            "AND completed_at IS NULL)",
            name="ck_ecc_running_completeness",
        ),
        # pending → not claimed
        CheckConstraint(
            "check_status != 'pending' OR claimed_at IS NULL",
            name="ck_ecc_pending_completeness",
        ),
        # ── Format checks ──
        CheckConstraint(
            "length(embedding_profile_id) = 64 "
            "AND embedding_profile_id = lower(embedding_profile_id)",
            name="ck_ecc_profile_id_format",
        ),
        CheckConstraint(
            "length(runtime_config_fingerprint) = 64 "
            "AND runtime_config_fingerprint = lower(runtime_config_fingerprint)",
            name="ck_ecc_fingerprint_format",
        ),
    )

    check_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    embedding_profile_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("embedding_profiles.profile_id", ondelete="RESTRICT"),
        nullable=False,
    )
    binding_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("embedding_capability_bindings.binding_id", ondelete="RESTRICT"),
        nullable=True,
    )
    runtime_config_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    probe_suite_version: Mapped[str] = mapped_column(String(30), nullable=False)
    check_status: Mapped[str] = mapped_column(String(20), nullable=False)
    probe_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    provider_request_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    probed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # ── Separate document/query observations ──
    observed_document_dimension: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    observed_query_dimension: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    observed_document_norm_min: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    observed_document_norm_max: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    observed_query_norm: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    observed_document_reported_model: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    observed_query_reported_model: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    observed_document_provider_revision: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    observed_query_provider_revision: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    observed_document_evidence_source: Mapped[str | None] = mapped_column(
        String(60), nullable=True
    )
    observed_query_evidence_source: Mapped[str | None] = mapped_column(
        String(60), nullable=True
    )

    # ── Failure evidence (NULL on pass) ──
    failure_category: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sanitized_error_detail: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    check_schema_version: Mapped[str] = mapped_column(
        String(30), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )


class EmbeddingCapabilityBinding(Base):
    """Stable resolved semantic-space identity (P0.4A1).

    A binding is created ONLY after a successful dual-probe proves the
    runtime matches the declared contract. It is immutable once created.

    The binding identity (``binding_id``) is a deterministic SHA-256 over
    ALL semantic-space-defining fields: profile, provider, model,
    revision, posture, tasks, dimension, normalization, post-processing,
    endpoint, deployment, contracts, and classifier version. Two runtimes
    that share a provider+model+dimension but differ in any other field
    produce distinct bindings.
    """

    __tablename__ = "embedding_capability_bindings"
    __table_args__ = (
        Index("ix_ecb_profile_id", "embedding_profile_id"),
        CheckConstraint(
            "binding_schema_version = 'capability_binding_v1'",
            name="ck_ecb_schema_version",
        ),
        CheckConstraint("resolved_dimension > 0", name="ck_ecb_dimension_positive"),
        CheckConstraint(
            "length(binding_id) = 64 AND binding_id = lower(binding_id)",
            name="ck_ecb_binding_id_format",
        ),
        CheckConstraint(
            "length(embedding_profile_id) = 64 "
            "AND embedding_profile_id = lower(embedding_profile_id)",
            name="ck_ecb_profile_id_format",
        ),
    )

    binding_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    embedding_profile_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("embedding_profiles.profile_id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    resolved_model: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_revision: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    model_resolution_posture: Mapped[str] = mapped_column(
        String(40), nullable=False
    )
    resolved_document_task: Mapped[str | None] = mapped_column(
        String(60), nullable=True
    )
    resolved_query_task: Mapped[str | None] = mapped_column(
        String(60), nullable=True
    )
    resolved_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    resolved_normalization: Mapped[str] = mapped_column(String(80), nullable=False)
    postprocessing_contract_version: Mapped[str] = mapped_column(
        String(60), nullable=False
    )
    resolved_endpoint_identity: Mapped[str] = mapped_column(
        String(512), nullable=False
    )
    resolved_deployment_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    profile_schema_version: Mapped[str] = mapped_column(
        String(30), nullable=False
    )
    provider_adapter_contract_version: Mapped[str] = mapped_column(
        String(60), nullable=False
    )
    governed_adapter_contract_version: Mapped[str] = mapped_column(
        String(60), nullable=False
    )
    resolution_classifier_version: Mapped[str] = mapped_column(
        String(60), nullable=False
    )
    binding_schema_version: Mapped[str] = mapped_column(
        String(30), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )


# ── P0.4A2: Binding activation, cutover, and write guards ────────────


class EmbeddingProfileBindingActivation(Base):
    """One governed activation attempt for a profile+binding (P0.4A2).

    At most one ``active`` activation per profile. A retired binding may
    become active again only through a new cutover → new candidate → new
    activation generation.

    Statuses: candidate → active | rejected; active → retired.
    ``retired`` and ``rejected`` are terminal.
    """

    __tablename__ = "embedding_profile_binding_activations"
    __table_args__ = (
        Index("ix_epba_profile_status", "embedding_profile_id", "status"),
        Index("ix_epba_binding_id", "capability_binding_id"),
        CheckConstraint(
            "status IN ('candidate','active','retired','rejected')",
            name="ck_epba_status",
        ),
        CheckConstraint(
            "activation_generation > 0", name="ck_epba_generation_positive"
        ),
        CheckConstraint(
            "embedding_purpose IN ('paper','knowledge_graph_entity','tool_description')",
            name="ck_epba_purpose",
        ),
        CheckConstraint(
            "status != 'active' OR (cutover_id IS NOT NULL AND activated_at IS NOT NULL)",
            name="ck_epba_active_requires_cutover",
        ),
        CheckConstraint(
            "status != 'retired' OR retired_at IS NOT NULL",
            name="ck_epba_retired_requires_timestamp",
        ),
        CheckConstraint(
            "status != 'rejected' OR rejected_at IS NOT NULL",
            name="ck_epba_rejected_requires_timestamp",
        ),
    )

    activation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    embedding_profile_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("embedding_profiles.profile_id", ondelete="RESTRICT"),
        nullable=False,
    )
    embedding_purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    capability_binding_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("embedding_capability_bindings.binding_id", ondelete="RESTRICT"),
        nullable=False,
    )
    cutover_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    activation_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EmbeddingBindingCutover(Base):
    """Generalized cutover ledger (P0.4A2).

    Supports paper, knowledge_graph_entity, and tool_description
    purposes. The semantic cache is disposable and does not need a
    durable cutover ledger.

    Statuses: pending → snapshotting → reindexing → verifying → ready
    → sealed → active. Also: failed, cancelled.
    """

    __tablename__ = "embedding_binding_cutovers"
    __table_args__ = (
        Index("ix_ebc_profile_status", "embedding_profile_id", "status"),
        Index("ix_ebc_target_binding", "target_binding_id"),
        CheckConstraint(
            "cutover_schema_version = 'cutover_v1'",
            name="ck_ebc_schema_version",
        ),
        CheckConstraint(
            "status IN ('pending','snapshotting','reindexing','verifying',"
            "'ready','sealed','active','failed','cancelled')",
            name="ck_ebc_status",
        ),
        CheckConstraint(
            "embedding_purpose IN ('paper','knowledge_graph_entity','tool_description')",
            name="ck_ebc_purpose",
        ),
        CheckConstraint("source_item_count >= 0", name="ck_ebc_source_count"),
        CheckConstraint("target_indexed_count >= 0", name="ck_ebc_indexed_count"),
        CheckConstraint("target_failed_count >= 0", name="ck_ebc_failed_count"),
    )

    cutover_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cutover_schema_version: Mapped[str] = mapped_column(String(30), nullable=False)
    embedding_profile_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("embedding_profiles.profile_id", ondelete="RESTRICT"),
        nullable=False,
    )
    embedding_purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    source_contract_version: Mapped[str] = mapped_column(String(30), nullable=False)
    source_binding_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_binding_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("embedding_capability_bindings.binding_id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_snapshot_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    source_snapshot_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    source_item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    target_indexed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    target_failed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    content_unavailable_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    verification_failure_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    write_guard_epoch: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    snapshot_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reindex_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sealed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sanitized_failure_detail: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )


class EmbeddingBindingCutoverItem(Base):
    """Per-item remediation tracking for a cutover (P0.4A2).

    The source snapshot is immutable. Retry attempts may update item
    execution state, but they must not replace the snapshotted identity
    or content hash.
    """

    __tablename__ = "embedding_binding_cutover_items"
    __table_args__ = (
        Index("ix_ebci_cutover_status", "cutover_id", "status"),
        CheckConstraint(
            "status IN ('pending','indexing','indexed','already_indexed',"
            "'content_unavailable','failed')",
            name="ck_ebci_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_ebci_attempt_count"),
    )

    item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cutover_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("embedding_binding_cutovers.cutover_id", ondelete="CASCADE"),
        nullable=False,
    )
    source_object_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_object_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_vector_record_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    paper_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    canonical_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_contract_version: Mapped[str] = mapped_column(String(30), nullable=False)
    target_vector_record_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    target_collection_name: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sanitized_failure_detail: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )


class EmbeddingProfileEmbeddingWriteGuard(Base):
    """Write-guard contract per persistent embedding profile (P0.4A2).

    One guard row per profile + purpose. All persistent embedding writes
    must consult the guard before claiming work.

    States: open → frozen → open.
    """

    __tablename__ = "embedding_profile_embedding_write_guards"
    __table_args__ = (
        Index(
            "ix_epewg_profile_purpose",
            "embedding_profile_id",
            "embedding_purpose",
            unique=True,
        ),
        CheckConstraint("state IN ('open','frozen')", name="ck_epewg_state"),
        CheckConstraint(
            "embedding_purpose IN ('paper','knowledge_graph_entity','tool_description')",
            name="ck_epewg_purpose",
        ),
        CheckConstraint(
            "state != 'frozen' OR (cutover_id IS NOT NULL AND frozen_at IS NOT NULL)",
            name="ck_epewg_frozen_requires_cutover",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    embedding_profile_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("embedding_profiles.profile_id", ondelete="RESTRICT"),
        nullable=False,
    )
    embedding_purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="open", server_default="open"
    )
    guard_epoch: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    cutover_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


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


# ── P0.5B WP4: Durable configuration resolution evidence ────────────


class ConfigurationResolutionSnapshot(Base):
    """Immutable configuration resolution snapshot for one operation."""

    __tablename__ = "configuration_resolution_snapshots"
    __table_args__ = (
        Index("ix_crs_scope", "scope_kind", "scope_id"),
        CheckConstraint(
            "scope_kind IN ('search_execution', 'retrieval_event', 'generation', 'release', 'capability_verification')",
            name="ck_crs_scope_kind",
        ),
    )

    snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scope_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(255), nullable=False)
    registry_schema_version: Mapped[str] = mapped_column(String(30), nullable=False)
    precedence_policy_version: Mapped[str] = mapped_column(String(30), nullable=False)
    effective_configuration_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )


class ConfigurationResolutionItem(Base):
    """One resolved field within a configuration snapshot."""

    __tablename__ = "configuration_resolution_items"
    __table_args__ = (
        Index("ix_cri_snapshot", "snapshot_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("configuration_resolution_snapshots.snapshot_id", ondelete="CASCADE"),
        nullable=False,
    )
    field_id: Mapped[str] = mapped_column(String(120), nullable=False)
    effect_class: Mapped[str] = mapped_column(String(40), nullable=False)
    winning_semantic_tier: Mapped[str] = mapped_column(String(40), nullable=False)
    winning_physical_origin: Mapped[str] = mapped_column(String(40), nullable=False)
    default_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    normalization_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    value_representation: Mapped[str | None] = mapped_column(String(200), nullable=True)
    value_fingerprint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    shadowed_source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sensitivity: Mapped[str] = mapped_column(String(20), nullable=False, default="public")
