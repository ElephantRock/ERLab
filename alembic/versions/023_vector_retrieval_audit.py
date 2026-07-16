"""Migration: vector retrieval audit ledger (P0.3.3).

Four tables for immutable retrieval auditing:
  vector_retrieval_events        — one row per governed retrieval
  vector_retrieval_scope_papers  — allowed-paper snapshot
  vector_retrieval_eligible_records — exact backend candidate population
  vector_retrieval_results       — ranked validated results

The composite FK from results → eligible_records database-enforces that
every persisted result belonged to the retrieval's frozen candidate set.

Revision ID: 023
Revises: 022
"""

from alembic import op
import sqlalchemy as sa

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    # ── 1. vector_retrieval_events ────────────────────────────────
    if not inspector.has_table("vector_retrieval_events"):
        op.create_table(
            "vector_retrieval_events",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("run_id", sa.Integer,
                      sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("stage_name", sa.String(100), nullable=False),
            sa.Column("retrieval_key", sa.String(160), nullable=False),
            sa.Column("request_schema_version", sa.String(30), nullable=False),
            # Scope identity
            sa.Column("scope_mode", sa.String(40), nullable=False),
            sa.Column("scope_schema_version", sa.String(30), nullable=False),
            sa.Column("scope_fingerprint", sa.String(64), nullable=False),
            sa.Column("embedding_profile_id", sa.String(64),
                      sa.ForeignKey("embedding_profiles.profile_id", ondelete="RESTRICT"),
                      nullable=False),
            sa.Column("profile_verification_status_snapshot", sa.String(20), nullable=False,
                      server_default="unverified"),
            sa.Column("query_vector_fingerprint", sa.String(64), nullable=False),
            sa.Column("input_fingerprint", sa.String(64), nullable=False),
            # Request params
            sa.Column("requested_top_k", sa.Integer, nullable=False),
            sa.Column("allow_partial_index_coverage", sa.Boolean, nullable=False, server_default="0"),
            # Coverage snapshot
            sa.Column("allowed_paper_count", sa.Integer, nullable=False),
            sa.Column("indexed_paper_count", sa.Integer, nullable=False),
            sa.Column("unindexed_paper_count", sa.Integer, nullable=False),
            sa.Column("eligible_vector_record_count", sa.Integer, nullable=False),
            sa.Column("coverage_status", sa.String(20), nullable=False),
            # Execution lifecycle
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("backend_batch_count", sa.Integer, nullable=True),
            sa.Column("returned_result_count", sa.Integer, nullable=True),
            sa.Column("failure_category", sa.String(40), nullable=True),
            sa.Column("failure_code", sa.String(80), nullable=True),
            sa.Column("failure_detail", sa.Text, nullable=True),
            sa.Column("started_at", sa.DateTime, nullable=True),
            sa.Column("completed_at", sa.DateTime, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
            # Constraints
            sa.UniqueConstraint("run_id", "stage_name", "retrieval_key",
                                name="uq_vre_run_stage_key"),
            sa.CheckConstraint("requested_top_k > 0", name="ck_vre_top_k_positive"),
            sa.CheckConstraint("attempt_count >= 0", name="ck_vre_attempt_count_nonnegative"),
            sa.CheckConstraint(
                "status IN ('pending','running','success','failed')",
                name="ck_vre_status",
            ),
            sa.CheckConstraint(
                "coverage_status IN ('empty_scope','complete','partial','none')",
                name="ck_vre_coverage_status",
            ),
            sa.CheckConstraint(
                "unindexed_paper_count = allowed_paper_count - indexed_paper_count",
                name="ck_vre_unindexed_equation",
            ),
            sa.CheckConstraint(
                "indexed_paper_count <= allowed_paper_count",
                name="ck_vre_indexed_le_allowed",
            ),
            sa.CheckConstraint(
                "failure_category IS NULL OR failure_category IN "
                "('scope_resolution','query_validation','index_coverage',"
                "'backend','result_validation','contract','internal')",
                name="ck_vre_failure_category",
            ),
        )
        op.create_index("ix_vre_run_id", "vector_retrieval_events", ["run_id"])
        op.create_index("ix_vre_status", "vector_retrieval_events", ["status"])

    # ── 2. vector_retrieval_scope_papers ──────────────────────────
    if not inspector.has_table("vector_retrieval_scope_papers"):
        op.create_table(
            "vector_retrieval_scope_papers",
            sa.Column("retrieval_event_id", sa.Integer,
                      sa.ForeignKey("vector_retrieval_events.id", ondelete="CASCADE"),
                      primary_key=True),
            sa.Column("paper_id", sa.Integer,
                      sa.ForeignKey("papers.id", ondelete="RESTRICT"),
                      primary_key=True),
            sa.Column("is_indexed", sa.Boolean, nullable=False, server_default="0"),
        )

    # ── 3. vector_retrieval_eligible_records ──────────────────────
    if not inspector.has_table("vector_retrieval_eligible_records"):
        op.create_table(
            "vector_retrieval_eligible_records",
            sa.Column("retrieval_event_id", sa.Integer,
                      sa.ForeignKey("vector_retrieval_events.id", ondelete="CASCADE"),
                      primary_key=True),
            sa.Column("vector_record_id", sa.String(64),
                      sa.ForeignKey("vector_index_records.vector_record_id", ondelete="RESTRICT"),
                      primary_key=True),
        )

    # ── 4. vector_retrieval_results ───────────────────────────────
    if not inspector.has_table("vector_retrieval_results"):
        op.create_table(
            "vector_retrieval_results",
            sa.Column("retrieval_event_id", sa.Integer,
                      sa.ForeignKey("vector_retrieval_events.id", ondelete="CASCADE"),
                      primary_key=True),
            sa.Column("rank", sa.Integer, primary_key=True),
            sa.Column("vector_record_id", sa.String(64), nullable=False),
            sa.Column("canonical_distance", sa.Float, nullable=False),
            # Composite FK: result must belong to eligible snapshot
            sa.ForeignKeyConstraint(
                ["retrieval_event_id", "vector_record_id"],
                ["vector_retrieval_eligible_records.retrieval_event_id",
                 "vector_retrieval_eligible_records.vector_record_id"],
                name="fk_vrr_eligible",
            ),
            sa.CheckConstraint("rank > 0", name="ck_vrr_rank_positive"),
            sa.UniqueConstraint("retrieval_event_id", "vector_record_id",
                                name="uq_vrr_no_dup_vector"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    for table in ("vector_retrieval_results", "vector_retrieval_eligible_records",
                  "vector_retrieval_scope_papers", "vector_retrieval_events"):
        if inspector.has_table(table):
            op.drop_table(table)
