"""Migration: search query executions — execution identity for P0.2.1.

Establishes a database-enforced identity for each logical source-adapter
invocation against one logical search query. One ``SearchQuery`` (logical
intent) fans out to N ``SearchQueryExecution`` rows (one per source). Future
``PaperDiscovery`` rows link to the specific execution that found them, with
a composite FK that proves the execution belongs to the same query.

Run ownership is obtained via the indexed join to ``search_queries.run_id``;
there is intentionally NO redundant ``run_id`` on this table, eliminating a
class of cross-run-ownership-inconsistent states.

Schema enforcement (not just ORM defaults):
  - ``source`` is CHECK-constrained to canonical form (lowercase, trimmed,
    non-empty) so casing/whitespace cannot bypass replay uniqueness.
  - ``status`` and ``accounting_status`` are CHECK-constrained to their
    documented vocabularies.
  - All count columns are CHECK-constrained non-negative.
  - ``attempt_count`` includes the first outbound attempt (pending/skipped = 0,
    first contact = 1, one retry = 2).

Legacy policy: existing ``paper_discoveries`` rows keep ``execution_id = NULL``
(no backfill). The ``accounting_status`` default is ``'incomplete'``; no row
is ever ``'reconciled'`` by this migration (that is P0.2.4's responsibility,
gated on all four counts being populated).

Revision ID: 015
Revises: 014
"""

from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


# ── Required columns/constraints for the strict migration guard ──────────
# If the table already exists (partial/incomplete prior run), we verify these
# rather than silently skipping. Named explicitly for stable downgrade.

_REQUIRED_EXEC_COLUMNS = {
    "id", "search_query_id", "source", "translated_query", "status",
    "attempt_count", "error_detail", "attempted_at", "completed_at",
    "raw_result_count", "normalized_result_count", "rejected_result_count",
    "source_unique_count", "accounting_status", "created_at", "updated_at",
}


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    # ── 1. search_query_executions table ─────────────────────────
    if inspector.has_table("search_query_executions"):
        # Strict guard: verify the existing table is complete, don't skip.
        existing_cols = {c["name"] for c in inspector.get_columns("search_query_executions")}
        missing = _REQUIRED_EXEC_COLUMNS - existing_cols
        if missing:
            raise RuntimeError(
                "search_query_executions already exists but is missing required "
                f"columns: {sorted(missing)}. Refusing to proceed with a partial "
                "table — investigate the incomplete migration before continuing."
            )
        # Table exists and is complete: nothing to create.
    else:
        op.create_table(
            "search_query_executions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "search_query_id",
                sa.Integer(),
                sa.ForeignKey("search_queries.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("source", sa.String(50), nullable=False),
            sa.Column("translated_query", sa.Text(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_detail", sa.Text(), nullable=True),
            sa.Column("attempted_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("raw_result_count", sa.Integer(), nullable=True),
            sa.Column("normalized_result_count", sa.Integer(), nullable=True),
            sa.Column("rejected_result_count", sa.Integer(), nullable=True),
            sa.Column("source_unique_count", sa.Integer(), nullable=True),
            sa.Column(
                "accounting_status",
                sa.String(20),
                nullable=False,
                server_default="incomplete",
            ),
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
            sa.UniqueConstraint(
                "search_query_id", "source",
                name="uq_search_query_executions_query_source",
            ),
            sa.UniqueConstraint(
                "id", "search_query_id",
                name="uq_search_query_executions_id_query",
            ),
            sa.CheckConstraint(
                "source = lower(trim(source)) AND length(trim(source)) > 0",
                name="ck_search_query_executions_source_canonical",
            ),
            sa.CheckConstraint(
                "status IN ('pending','running','success','partial',"
                "'failed','timeout','skipped')",
                name="ck_search_query_executions_status",
            ),
            sa.CheckConstraint(
                "accounting_status IN ('incomplete','reconciled')",
                name="ck_search_query_executions_accounting_status",
            ),
            sa.CheckConstraint(
                "attempt_count >= 0",
                name="ck_search_query_executions_attempt_count_nonnegative",
            ),
            sa.CheckConstraint(
                "raw_result_count IS NULL OR raw_result_count >= 0",
                name="ck_search_query_executions_raw_count_nonnegative",
            ),
            sa.CheckConstraint(
                "normalized_result_count IS NULL OR normalized_result_count >= 0",
                name="ck_search_query_executions_normalized_count_nonnegative",
            ),
            sa.CheckConstraint(
                "rejected_result_count IS NULL OR rejected_result_count >= 0",
                name="ck_search_query_executions_rejected_count_nonnegative",
            ),
            sa.CheckConstraint(
                "source_unique_count IS NULL OR source_unique_count >= 0",
                name="ck_search_query_executions_source_unique_count_nonnegative",
            ),
        )
        op.create_index(
            "ix_search_query_executions_query_id",
            "search_query_executions",
            ["search_query_id"],
        )

    # ── 2. paper_discoveries.execution_id + composite FK ─────────
    # SQLite can't ALTER TABLE ADD CONSTRAINT, so batch mode reconstructs
    # the table. We add the column, then create the CHECK + composite FK
    # INSIDE the batch context (batch_op.create_*), which resolves the
    # referenced table correctly — unlike table_args= which fails to find
    # the referenced table during temp-table creation.
    disc_cols = {c["name"] for c in inspector.get_columns("paper_discoveries")}
    need_column_add = "execution_id" not in disc_cols

    with op.batch_alter_table("paper_discoveries", recreate="always") as batch_op:
        if need_column_add:
            batch_op.add_column(
                sa.Column("execution_id", sa.Integer(), nullable=True)
            )
        batch_op.create_check_constraint(
            "ck_paper_discoveries_execution_requires_query",
            "execution_id IS NULL OR search_query_id IS NOT NULL",
        )
        batch_op.create_foreign_key(
            "fk_paper_discoveries_execution_query",
            "search_query_executions",
            ["execution_id", "search_query_id"],
            ["id", "search_query_id"],
            ondelete="RESTRICT",
        )

    op.create_index(
        "ix_paper_discoveries_execution_id",
        "paper_discoveries",
        ["execution_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    # ── 1. Remove execution_id from paper_discoveries ────────────
    # Drop the index first, then batch-reconstruct the table: explicitly drop
    # the named composite FK + null-bypass CHECK (which reference execution_id)
    # BEFORE dropping the column, so the temp-table recreation doesn't carry
    # a FK to a soon-nonexistent column.
    disc_cols = {c["name"] for c in inspector.get_columns("paper_discoveries")}
    if "execution_id" in disc_cols:
        try:
            op.drop_index("ix_paper_discoveries_execution_id", table_name="paper_discoveries")
        except Exception:
            pass  # index may not exist if upgrade was partial

        with op.batch_alter_table("paper_discoveries", recreate="always") as batch_op:
            batch_op.drop_constraint(
                "fk_paper_discoveries_execution_query", type_="foreignkey"
            )
            batch_op.drop_constraint(
                "ck_paper_discoveries_execution_requires_query", type_="check"
            )
            batch_op.drop_column("execution_id")

    # ── 2. Drop search_query_executions ──────────────────────────
    if inspector.has_table("search_query_executions"):
        try:
            op.drop_index(
                "ix_search_query_executions_query_id",
                table_name="search_query_executions",
            )
        except Exception:
            pass
        op.drop_table("search_query_executions")
