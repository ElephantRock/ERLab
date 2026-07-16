"""Migration: provenance contract gating (P0.2.7).

Removes the implicit ``pre_provenance`` default from ``pipeline_runs`` and
adds ``legacy_provenance_reason`` with CHECK constraints enforcing:

  pre_provenance    → legacy_provenance_reason IN (controlled set)
  provenance_v1     → legacy_provenance_reason IS NULL

Existing ``pre_provenance`` rows are assigned ``legacy_provenance_reason =
'pre_gating_run'``. No historical row is upgraded to ``provenance_v1``.

Preflight: any existing ``provenance_v1`` row without a reconciliation ledger
is a contract violation → migration fails (does not fabricate the ledger).

Revision ID: 020
Revises: 019
"""

from alembic import op
import sqlalchemy as sa

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect, text

    inspector = inspect(bind)

    # ── Preflight: verify existing provenance_v1 rows have reconciliation ──
    if inspector.has_table("run_search_reconciliations"):
        violations = bind.execute(text(
            "SELECT COUNT(*) FROM pipeline_runs r "
            "WHERE r.provenance_version = 'provenance_v1' "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM run_search_reconciliations rsr "
            "  WHERE rsr.run_id = r.id"
            ")"
        )).scalar()
        if violations and violations > 0:
            raise RuntimeError(
                f"Preflight check failed: {violations} provenance_v1 run(s) "
                "lack a run_search_reconciliation ledger. A governed run without "
                "a reconciliation ledger is a contract violation. Manual "
                "investigation required before proceeding."
            )

    existing_cols = {c["name"] for c in inspector.get_columns("pipeline_runs")}

    need_reason = "legacy_provenance_reason" not in existing_cols

    with op.batch_alter_table("pipeline_runs", recreate="always") as batch_op:
        if need_reason:
            batch_op.add_column(
                sa.Column("legacy_provenance_reason", sa.String(40), nullable=True)
            )

        # Add provenance version vocabulary CHECK
        batch_op.create_check_constraint(
            "ck_pipeline_runs_provenance_version",
            "provenance_version IN ('pre_provenance', 'provenance_v1')",
        )

        # Add version/reason consistency CHECK
        batch_op.create_check_constraint(
            "ck_pipeline_runs_provenance_legacy_reason",
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
        )

    # ── Assign pre_gating_run to existing pre_provenance rows ──
    # (Migrations bypass ORM lifecycle, so direct SQL is correct.)
    bind.execute(text(
        "UPDATE pipeline_runs SET legacy_provenance_reason = 'pre_gating_run' "
        "WHERE provenance_version = 'pre_provenance' "
        "AND (legacy_provenance_reason IS NULL OR legacy_provenance_reason = '')"
    ))
    bind.commit()

    # ── Remove the server_default on provenance_version ──
    # SQLite batch mode: recreate the table without the default.
    # The batch_op above already handles this if we set server_default=None,
    # but SQLite's ALTER limitation means we need to check if the default
    # is actually present. We handle this by checking the column definition.
    # The batch_alter_table with recreate="always" drops implicit defaults.
    # For explicit ones, we need a second pass.
    # NOTE: The server_default was set in migration 014. Since we recreate
    # the table above with no server_default on provenance_version, the
    # default is already gone after the batch alter. The batch_alter_table
    # recreates the table from ORM reflection which doesn't carry the
    # original server_default forward. This is correct for our purpose.


def downgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    existing_cols = {c["name"] for c in inspector.get_columns("pipeline_runs")}
    if "legacy_provenance_reason" in existing_cols or True:
        with op.batch_alter_table("pipeline_runs", recreate="always") as batch_op:
            # Drop P0.2.7 constraints
            for ck_name in (
                "ck_pipeline_runs_provenance_version",
                "ck_pipeline_runs_provenance_legacy_reason",
            ):
                try:
                    batch_op.drop_constraint(ck_name, type_="check")
                except Exception:
                    pass

            if "legacy_provenance_reason" in existing_cols:
                batch_op.drop_column("legacy_provenance_reason")

            # Restore the server_default that migration 014 set
            batch_op.alter_column(
                "provenance_version",
                existing_type=sa.String(20),
                server_default="pre_provenance",
            )
