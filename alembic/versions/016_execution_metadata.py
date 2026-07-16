"""Migration: execution metadata — translated queries and structured failures.

P0.2.3: Adds structured failure classification and a legacy-honest version
marker to ``search_query_executions``. Existing P0.2.2 rows keep
``execution_metadata_version = NULL`` (no fabricated classifications). New
governed rows write ``execution_v1``.

Three new columns:
  failure_category           — controlled vocabulary (CHECK-enforced)
  failure_code               — machine-readable lowercase code
  execution_metadata_version — NULL for legacy, 'execution_v1' for governed

The composite-state CHECK enforces metadata completeness for governed rows:
pending/running/success have no failure fields; terminal non-success states
require all failure fields populated.

Revision ID: 016
Revises: 015
"""

from alembic import op
import sqlalchemy as sa

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None

_FAILURE_CATEGORIES = (
    "'source_unavailable','query_translation','authentication',"
    "'authorization','rate_limit','timeout','transport',"
    "'provider_rejection','provider_internal','response_parse',"
    "'adapter_contract','configuration','internal'"
)


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("search_query_executions")}

    need_cols = {"failure_category", "failure_code", "execution_metadata_version"} - existing_cols

    if not need_cols:
        # Strict guard: verify the columns exist. If some but not all, fail loud.
        missing = {"failure_category", "failure_code", "execution_metadata_version"} - existing_cols
        if missing:
            raise RuntimeError(
                f"search_query_executions is missing expected columns: {sorted(missing)}"
            )
        return  # all present, nothing to do

    with op.batch_alter_table("search_query_executions", recreate="always") as batch_op:
        if "failure_category" in need_cols:
            batch_op.add_column(sa.Column("failure_category", sa.String(40), nullable=True))
        if "failure_code" in need_cols:
            batch_op.add_column(sa.Column("failure_code", sa.String(80), nullable=True))
        if "execution_metadata_version" in need_cols:
            batch_op.add_column(
                sa.Column("execution_metadata_version", sa.String(20), nullable=True)
            )

        # ── CHECK: execution_metadata_version vocabulary ──
        batch_op.create_check_constraint(
            "ck_search_query_executions_metadata_version",
            "execution_metadata_version IS NULL "
            "OR execution_metadata_version = 'execution_v1'",
        )

        # ── CHECK: failure_category vocabulary ──
        batch_op.create_check_constraint(
            "ck_search_query_executions_failure_category",
            f"failure_category IS NULL OR failure_category IN ({_FAILURE_CATEGORIES})",
        )

        # ── CHECK: failure_code canonical form ──
        batch_op.create_check_constraint(
            "ck_search_query_executions_failure_code",
            "failure_code IS NULL "
            "OR (failure_code = lower(trim(failure_code)) "
            "AND length(trim(failure_code)) BETWEEN 1 AND 80)",
        )

        # ── CHECK: composite metadata completeness for governed rows ──
        batch_op.create_check_constraint(
            "ck_search_query_executions_metadata_completeness",
            "execution_metadata_version IS NULL "
            # pending/running: no failure fields, no error_detail
            "OR (status IN ('pending','running') "
            "    AND failure_category IS NULL "
            "    AND failure_code IS NULL "
            "    AND error_detail IS NULL) "
            # success: no failure fields, no error_detail, completed
            "OR (status = 'success' "
            "    AND failure_category IS NULL "
            "    AND failure_code IS NULL "
            "    AND error_detail IS NULL "
            "    AND completed_at IS NOT NULL) "
            # terminal non-success: all failure fields required
            "OR (status IN ('partial','failed','timeout','skipped') "
            "    AND failure_category IS NOT NULL "
            "    AND failure_code IS NOT NULL "
            "    AND error_detail IS NOT NULL "
            "    AND completed_at IS NOT NULL)",
        )

        # ── CHECK: timeout implies failure_category = timeout ──
        batch_op.create_check_constraint(
            "ck_search_query_executions_timeout_category",
            "execution_metadata_version IS NULL "
            "OR status != 'timeout' "
            "OR failure_category = 'timeout'",
        )

        # ── CHECK: attempted executions must have a translated plan ──
        batch_op.create_check_constraint(
            "ck_search_query_executions_attempted_has_plan",
            "execution_metadata_version IS NULL "
            "OR attempt_count = 0 "
            "OR translated_query IS NOT NULL",
        )

        # ── CHECK: translated_query size limit ──
        batch_op.create_check_constraint(
            "ck_search_query_executions_translated_query_size",
            "translated_query IS NULL OR length(translated_query) <= 4096",
        )

        # ── CHECK: governed skipped rows have no attempts ──
        batch_op.create_check_constraint(
            "ck_search_query_executions_skipped_no_attempts",
            "execution_metadata_version IS NULL "
            "OR status != 'skipped' "
            "OR (attempt_count = 0 AND attempted_at IS NULL)",
        )

    # ── Reporting index ──
    existing_indexes = {ix["name"] for ix in inspector.get_indexes("search_query_executions")}
    if "ix_search_query_executions_status_category" not in existing_indexes:
        op.create_index(
            "ix_search_query_executions_status_category",
            "search_query_executions",
            ["status", "failure_category"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)
    existing_indexes = {ix["name"] for ix in inspector.get_indexes("search_query_executions")}

    if "ix_search_query_executions_status_category" in existing_indexes:
        try:
            op.drop_index(
                "ix_search_query_executions_status_category",
                table_name="search_query_executions",
            )
        except Exception:
            pass

    existing_cols = {c["name"] for c in inspector.get_columns("search_query_executions")}
    if {"failure_category", "failure_code", "execution_metadata_version"} & existing_cols:
        with op.batch_alter_table("search_query_executions", recreate="always") as batch_op:
            # Drop the P0.2.3 CHECK constraints FIRST — they reference the
            # columns we're about to drop, so the temp-table recreation would
            # fail if they remained.
            for ck_name in (
                "ck_search_query_executions_metadata_version",
                "ck_search_query_executions_failure_category",
                "ck_search_query_executions_failure_code",
                "ck_search_query_executions_metadata_completeness",
                "ck_search_query_executions_timeout_category",
                "ck_search_query_executions_attempted_has_plan",
                "ck_search_query_executions_translated_query_size",
                "ck_search_query_executions_skipped_no_attempts",
            ):
                try:
                    batch_op.drop_constraint(ck_name, type_="check")
                except Exception:
                    pass  # constraint may not exist if upgrade was partial
            if "execution_metadata_version" in existing_cols:
                batch_op.drop_column("execution_metadata_version")
            if "failure_code" in existing_cols:
                batch_op.drop_column("failure_code")
            if "failure_category" in existing_cols:
                batch_op.drop_column("failure_category")
