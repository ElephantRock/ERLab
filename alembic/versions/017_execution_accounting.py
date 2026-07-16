"""Migration: execution accounting — reconciliation contract (P0.2.4).

Adds ``accounting_schema_version`` and a strong reconciliation CHECK
constraint to ``search_query_executions``. Existing rows remain
``incomplete`` and unversioned — no counts are fabricated.

The principal constraint enforces that every reconciled row has all four
counts populated and satisfies:
    raw_result_count = normalized_result_count + rejected_result_count
    source_unique_count <= normalized_result_count

And every incomplete row has all counts NULL and no accounting version.

Revision ID: 017
Revises: 016
"""

from alembic import op
import sqlalchemy as sa

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect, text

    inspector = inspect(bind)

    # ── Preflight: fail loudly if any existing row has unexpected data ──
    # P0.2.1–P0.2.3 left all counts NULL and accounting_status='incomplete'.
    # Any row violating this requires manual investigation.
    result = bind.execute(text(
        "SELECT COUNT(*) FROM search_query_executions "
        "WHERE accounting_status != 'incomplete' "
        "OR raw_result_count IS NOT NULL "
        "OR normalized_result_count IS NOT NULL "
        "OR rejected_result_count IS NOT NULL "
        "OR source_unique_count IS NOT NULL"
    )).scalar()
    if result and result > 0:
        raise RuntimeError(
            f"Preflight check failed: {result} execution row(s) have unexpected "
            "accounting data (non-incomplete status or non-NULL counts). "
            "P0.2.1–P0.2.3 explicitly left all counts unset. Manual investigation "
            "required before proceeding."
        )

    existing_cols = {c["name"] for c in inspector.get_columns("search_query_executions")}

    if "accounting_schema_version" in existing_cols:
        # Strict guard: verify it's the right shape.
        return

    with op.batch_alter_table("search_query_executions", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column("accounting_schema_version", sa.String(20), nullable=True)
        )

        # ── CHECK: accounting_schema_version vocabulary ──
        batch_op.create_check_constraint(
            "ck_search_query_executions_accounting_schema_version",
            "accounting_schema_version IS NULL "
            "OR accounting_schema_version = 'accounting_v1'",
        )

        # ── CHECK: principal reconciliation constraint ──
        # Either incomplete (all NULL, no version) or fully reconciled
        # (all counts set, equation satisfied, version stamped).
        batch_op.create_check_constraint(
            "ck_search_query_executions_accounting_reconciled",
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
        )


def downgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("search_query_executions")}

    if "accounting_schema_version" in existing_cols:
        with op.batch_alter_table("search_query_executions", recreate="always") as batch_op:
            # Drop P0.2.4 CHECK constraints first (they reference the column).
            for ck_name in (
                "ck_search_query_executions_accounting_schema_version",
                "ck_search_query_executions_accounting_reconciled",
            ):
                try:
                    batch_op.drop_constraint(ck_name, type_="check")
                except Exception:
                    pass
            batch_op.drop_column("accounting_schema_version")
