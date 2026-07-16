"""Migration: run-level search reconciliation (P0.2.6).

Two new tables:
  search_query_execution_scopes — durable intended query/source matrix
  run_search_reconciliations   — one row per run with aggregate reconciliation

No scope or reconciliation rows are fabricated for existing runs. Historical
runs remain without reconciliation claims.

Revision ID: 019
Revises: 018
"""

from alembic import op
import sqlalchemy as sa

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    # ── 1. search_query_execution_scopes ──────────────────────────
    if not inspector.has_table("search_query_execution_scopes"):
        op.create_table(
            "search_query_execution_scopes",
            sa.Column(
                "search_query_id",
                sa.Integer(),
                sa.ForeignKey("search_queries.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("scope_schema_version", sa.String(30), nullable=False),
            sa.Column("intended_sources_json", sa.Text(), nullable=False),
            sa.Column("intended_source_count", sa.Integer(), nullable=False),
            sa.Column("source_set_hash", sa.String(64), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.current_timestamp(),
            ),
            sa.CheckConstraint(
                "scope_schema_version = 'execution_scope_v1'",
                name="ck_sqes_scope_schema_version",
            ),
            sa.CheckConstraint(
                "intended_source_count >= 0",
                name="ck_sqes_source_count_nonnegative",
            ),
        )

    # ── 2. run_search_reconciliations ─────────────────────────────
    if not inspector.has_table("run_search_reconciliations"):
        op.create_table(
            "run_search_reconciliations",
            sa.Column(
                "run_id",
                sa.Integer(),
                sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("reconciliation_schema_version", sa.String(30), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("execution_posture", sa.String(30), nullable=True),
            sa.Column("reconciliation_attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("input_fingerprint", sa.String(64), nullable=True),
            sa.Column("issue_code", sa.String(60), nullable=True),
            sa.Column("issue_detail", sa.Text(), nullable=True),
            sa.Column("last_checked_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.current_timestamp(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.current_timestamp(),
            ),
            # ── Aggregate count columns (nullable until reconciled) ──
            sa.Column("logical_query_count", sa.Integer(), nullable=True),
            sa.Column("expected_execution_count", sa.Integer(), nullable=True),
            sa.Column("actual_execution_count", sa.Integer(), nullable=True),
            sa.Column("terminal_execution_count", sa.Integer(), nullable=True),
            sa.Column("success_execution_count", sa.Integer(), nullable=True),
            sa.Column("partial_execution_count", sa.Integer(), nullable=True),
            sa.Column("failed_execution_count", sa.Integer(), nullable=True),
            sa.Column("timeout_execution_count", sa.Integer(), nullable=True),
            sa.Column("skipped_execution_count", sa.Integer(), nullable=True),
            sa.Column("reconciled_accounting_execution_count", sa.Integer(), nullable=True),
            sa.Column("incomplete_accounting_execution_count", sa.Integer(), nullable=True),
            sa.Column("source_unique_result_count", sa.Integer(), nullable=True),
            sa.Column("linked_discovery_count", sa.Integer(), nullable=True),
            sa.Column("remote_canonical_paper_count", sa.Integer(), nullable=True),
            sa.Column("nonremote_canonical_paper_count", sa.Integer(), nullable=True),
            sa.Column("remote_only_paper_count", sa.Integer(), nullable=True),
            sa.Column("nonremote_only_paper_count", sa.Integer(), nullable=True),
            sa.Column("multi_origin_paper_count", sa.Integer(), nullable=True),
            sa.Column("run_paper_count", sa.Integer(), nullable=True),
            sa.Column("canonicalization_reduction_count", sa.Integer(), nullable=True),
            sa.Column("unexplained_membership_count", sa.Integer(), nullable=True),
            sa.Column("unowned_discovery_paper_count", sa.Integer(), nullable=True),
            # ── CHECK constraints ──
            sa.CheckConstraint(
                "reconciliation_schema_version = 'run_reconciliation_v1'",
                name="ck_rsr_schema_version",
            ),
            sa.CheckConstraint(
                "status IN ('pending','blocked','reconciled','failed')",
                name="ck_rsr_status",
            ),
            sa.CheckConstraint(
                "execution_posture IS NULL "
                "OR execution_posture IN ('healthy','degraded','no_usable_sources')",
                name="ck_rsr_execution_posture",
            ),
            sa.CheckConstraint(
                "reconciliation_attempt_count >= 0",
                name="ck_rsr_attempt_count_nonnegative",
            ),
            # Reconciled completeness: all counts + fingerprint + posture + completed_at
            sa.CheckConstraint(
                "status != 'reconciled' "
                "OR ("
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
                "  AND issue_detail IS NULL"
                ")",
                name="ck_rsr_reconciled_completeness",
            ),
            # Reconciled execution equations
            sa.CheckConstraint(
                "status != 'reconciled' "
                "OR expected_execution_count = actual_execution_count",
                name="ck_rsr_expected_equals_actual",
            ),
            sa.CheckConstraint(
                "status != 'reconciled' "
                "OR actual_execution_count = terminal_execution_count",
                name="ck_rsr_actual_equals_terminal",
            ),
            sa.CheckConstraint(
                "status != 'reconciled' "
                "OR terminal_execution_count = "
                "    success_execution_count + partial_execution_count "
                "    + failed_execution_count + timeout_execution_count "
                "    + skipped_execution_count",
                name="ck_rsr_terminal_decomposition",
            ),
            sa.CheckConstraint(
                "status != 'reconciled' "
                "OR actual_execution_count = "
                "    reconciled_accounting_execution_count "
                "    + incomplete_accounting_execution_count",
                name="ck_rsr_accounting_decomposition",
            ),
            # Reconciled source-unique = linked discoveries
            sa.CheckConstraint(
                "status != 'reconciled' "
                "OR source_unique_result_count = linked_discovery_count",
                name="ck_rsr_source_unique_equals_linked",
            ),
            # Reconciled zero failures
            sa.CheckConstraint(
                "status != 'reconciled' "
                "OR unexplained_membership_count = 0",
                name="ck_rsr_no_unexplained_membership",
            ),
            sa.CheckConstraint(
                "status != 'reconciled' "
                "OR unowned_discovery_paper_count = 0",
                name="ck_rsr_no_unowned_discovery",
            ),
            # Reconciled set decomposition equations
            sa.CheckConstraint(
                "status != 'reconciled' "
                "OR canonicalization_reduction_count = "
                "    linked_discovery_count - remote_canonical_paper_count",
                name="ck_rsr_canonicalization_reduction",
            ),
            sa.CheckConstraint(
                "status != 'reconciled' "
                "OR remote_canonical_paper_count = "
                "    remote_only_paper_count + multi_origin_paper_count",
                name="ck_rsr_remote_decomposition",
            ),
            sa.CheckConstraint(
                "status != 'reconciled' "
                "OR nonremote_canonical_paper_count = "
                "    nonremote_only_paper_count + multi_origin_paper_count",
                name="ck_rsr_nonremote_decomposition",
            ),
            sa.CheckConstraint(
                "status != 'reconciled' "
                "OR run_paper_count = "
                "    remote_only_paper_count + nonremote_only_paper_count "
                "    + multi_origin_paper_count",
                name="ck_rsr_membership_decomposition",
            ),
            # Non-reconciled: blocked requires issue, failed requires issue+completed_at
            sa.CheckConstraint(
                "status != 'blocked' "
                "OR (issue_code IS NOT NULL AND issue_detail IS NOT NULL "
                "    AND completed_at IS NULL)",
                name="ck_rsr_blocked_has_issue",
            ),
            sa.CheckConstraint(
                "status != 'failed' "
                "OR (issue_code IS NOT NULL AND issue_detail IS NOT NULL "
                "    AND completed_at IS NOT NULL)",
                name="ck_rsr_failed_has_issue",
            ),
            # Non-reconciled: all counts NULL (no partial snapshots)
            sa.CheckConstraint(
                "status = 'reconciled' "
                "OR logical_query_count IS NULL",
                name="ck_rsr_nonreconciled_null_counts",
            ),
        )
        op.create_index(
            "ix_rsr_status", "run_search_reconciliations", ["status"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    if inspector.has_table("run_search_reconciliations"):
        try:
            op.drop_index("ix_rsr_status", table_name="run_search_reconciliations")
        except Exception:
            pass
        op.drop_table("run_search_reconciliations")

    if inspector.has_table("search_query_execution_scopes"):
        op.drop_table("search_query_execution_scopes")
