"""Migration: discovery-to-execution linkage (P0.2.5).

Connects every governed source-unique result to the exact
SearchQueryExecution that produced it. Adds:

  - ``source_result_key`` and ``linkage_schema_version`` on paper_discoveries
  - ``execution_discovery_linkages`` ledger table (one row per execution)
  - Triple composite FK on paper_discoveries (execution_id, search_query_id, source)
  - UNIQUE(execution_id, source_result_key) for replay-safe one-to-one linkage
  - UNIQUE(id, search_query_id, source) on search_query_executions

Legacy rows: NULL source_result_key, NULL linkage_schema_version, no ledger rows.
No historical linkages are fabricated.

Revision ID: 018
Revises: 017
"""

from alembic import op
import sqlalchemy as sa

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect, text

    inspector = inspect(bind)

    # ── Preflight: verify existing non-null execution links are consistent ──
    mismatches = bind.execute(text(
        "SELECT COUNT(*) FROM paper_discoveries d "
        "JOIN search_query_executions e ON d.execution_id = e.id "
        "WHERE d.execution_id IS NOT NULL "
        "AND (d.search_query_id != e.search_query_id "
        "     OR d.source != e.source)"
    )).scalar()
    if mismatches and mismatches > 0:
        raise RuntimeError(
            f"Preflight check failed: {mismatches} discovery row(s) have "
            "execution links that don't match the execution's query_id or source. "
            "Manual investigation required before proceeding."
        )

    # ── 1. Add execution uniqueness constraint (id, search_query_id, source) ──
    # This supports the triple composite FK on paper_discoveries.
    # We add it via batch alter on search_query_executions.
    exec_cols = {c["name"] for c in inspector.get_columns("search_query_executions")}
    if "accounting_schema_version" not in exec_cols:
        raise RuntimeError("search_query_executions missing P0.2.4 columns")

    with op.batch_alter_table("search_query_executions", recreate="always") as batch_op:
        batch_op.create_unique_constraint(
            "uq_search_query_executions_id_query_source",
            ["id", "search_query_id", "source"],
        )

    # ── 2. Add source_result_key + linkage_schema_version to paper_discoveries ──
    disc_cols = {c["name"] for c in inspector.get_columns("paper_discoveries")}
    need_srkey = "source_result_key" not in disc_cols
    need_lsv = "linkage_schema_version" not in disc_cols

    if need_srkey or need_lsv:
        with op.batch_alter_table("paper_discoveries", recreate="always") as batch_op:
            # Drop the old P0.2.1 composite FK first
            try:
                batch_op.drop_constraint(
                    "fk_paper_discoveries_execution_query", type_="foreignkey"
                )
            except Exception:
                pass
            # Drop the old P0.2.1 null-bypass check
            try:
                batch_op.drop_constraint(
                    "ck_paper_discoveries_execution_requires_query", type_="check"
                )
            except Exception:
                pass

            if need_srkey:
                batch_op.add_column(
                    sa.Column("source_result_key", sa.String(64), nullable=True)
                )
            if need_lsv:
                batch_op.add_column(
                    sa.Column("linkage_schema_version", sa.String(20), nullable=True)
                )

            # Re-add null-bypass check (still needed)
            batch_op.create_check_constraint(
                "ck_paper_discoveries_execution_requires_query",
                "execution_id IS NULL OR search_query_id IS NOT NULL",
            )
            # Re-add null-bypass for source_result_key: if linkage_v1, all required
            batch_op.create_check_constraint(
                "ck_paper_discoveries_linkage_governed",
                "linkage_schema_version IS NULL "
                "OR ("
                "  linkage_schema_version = 'linkage_v1' "
                "  AND execution_id IS NOT NULL "
                "  AND search_query_id IS NOT NULL "
                "  AND source_result_key IS NOT NULL "
                "  AND discovery_origin = 'remote_search'"
                ")",
            )
            # Triple composite FK (replaces the old two-column FK)
            batch_op.create_foreign_key(
                "fk_paper_discoveries_execution_query_source",
                "search_query_executions",
                ["execution_id", "search_query_id", "source"],
                ["id", "search_query_id", "source"],
                ondelete="RESTRICT",
            )
            # Replay uniqueness: one source-unique result per execution
            batch_op.create_unique_constraint(
                "uq_paper_discoveries_execution_result_key",
                ["execution_id", "source_result_key"],
            )

    # ── 3. Index on source_result_key ──
    existing_indexes = {ix["name"] for ix in inspector.get_indexes("paper_discoveries")}
    if "ix_paper_discoveries_source_result_key" not in existing_indexes:
        op.create_index(
            "ix_paper_discoveries_source_result_key",
            "paper_discoveries",
            ["source_result_key"],
        )

    # ── 4. execution_discovery_linkages ledger ──
    if not inspector.has_table("execution_discovery_linkages"):
        op.create_table(
            "execution_discovery_linkages",
            sa.Column(
                "execution_id",
                sa.Integer(),
                sa.ForeignKey("search_query_executions.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("linkage_schema_version", sa.String(20), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("expected_discovery_count", sa.Integer(), nullable=True),
            sa.Column("linked_discovery_count", sa.Integer(), nullable=True),
            sa.Column("linkage_attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_error_detail", sa.Text(), nullable=True),
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
            sa.CheckConstraint(
                "linkage_schema_version = 'linkage_v1'",
                name="ck_edl_linkage_schema_version",
            ),
            sa.CheckConstraint(
                "status IN ('pending','linked','failed','not_applicable')",
                name="ck_edl_status",
            ),
            sa.CheckConstraint(
                "linkage_attempt_count >= 0",
                name="ck_edl_attempt_count_nonnegative",
            ),
            sa.CheckConstraint(
                "expected_discovery_count IS NULL OR expected_discovery_count >= 0",
                name="ck_edl_expected_count_nonnegative",
            ),
            sa.CheckConstraint(
                "linked_discovery_count IS NULL OR linked_discovery_count >= 0",
                name="ck_edl_linked_count_nonnegative",
            ),
            sa.CheckConstraint(
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


def downgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    # 1. Drop linkage ledger
    if inspector.has_table("execution_discovery_linkages"):
        op.drop_table("execution_discovery_linkages")

    # 2. Remove paper_discoveries columns + restore old FK
    disc_cols = {c["name"] for c in inspector.get_columns("paper_discoveries")}
    if "source_result_key" in disc_cols or "linkage_schema_version" in disc_cols:
        # Drop index
        try:
            op.drop_index("ix_paper_discoveries_source_result_key", table_name="paper_discoveries")
        except Exception:
            pass

        with op.batch_alter_table("paper_discoveries", recreate="always") as batch_op:
            # Drop P0.2.5 constraints first
            for name in (
                "fk_paper_discoveries_execution_query_source",
                "uq_paper_discoveries_execution_result_key",
                "ck_paper_discoveries_linkage_governed",
                "ck_paper_discoveries_execution_requires_query",
            ):
                try:
                    if name.startswith("fk_"):
                        batch_op.drop_constraint(name, type_="foreignkey")
                    elif name.startswith("uq_"):
                        batch_op.drop_constraint(name, type_="unique")
                    else:
                        batch_op.drop_constraint(name, type_="check")
                except Exception:
                    pass

            # Restore P0.2.1 FK and check
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

            if "linkage_schema_version" in disc_cols:
                batch_op.drop_column("linkage_schema_version")
            if "source_result_key" in disc_cols:
                batch_op.drop_column("source_result_key")

    # 3. Drop execution uniqueness constraint
    with op.batch_alter_table("search_query_executions", recreate="always") as batch_op:
        try:
            batch_op.drop_constraint(
                "uq_search_query_executions_id_query_source", type_="unique"
            )
        except Exception:
            pass
