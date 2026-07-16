"""Migration: vector scope foundation (P0.3.1).

Adds stable domain identity and global-library membership to support
scoped vector retrieval.

  PipelineRun.domain_scope_key   — SHA-256 of normalized domain string
  PipelineRun.domain_scope_version — 'domain_scope_v1' or NULL
  global_library_memberships     — explicit active/removed membership

Historical runs are not backfilled with domain_scope_key.

Revision ID: 021
Revises: 020
"""

from alembic import op
import sqlalchemy as sa

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    # ── 1. domain_scope_key + domain_scope_version on pipeline_runs ──
    existing_cols = {c["name"] for c in inspector.get_columns("pipeline_runs")}
    need_domain = "domain_scope_key" not in existing_cols

    if need_domain:
        with op.batch_alter_table("pipeline_runs", recreate="always") as batch_op:
            batch_op.add_column(sa.Column("domain_scope_key", sa.String(64), nullable=True))
            batch_op.add_column(sa.Column("domain_scope_version", sa.String(20), nullable=True))
            batch_op.create_check_constraint(
                "ck_pipeline_runs_domain_scope",
                "("
                "  domain_scope_key IS NULL AND domain_scope_version IS NULL"
                ") OR ("
                "  domain_scope_key IS NOT NULL"
                "  AND domain_scope_version = 'domain_scope_v1'"
                ")",
            )

    # ── 2. global_library_memberships ──────────────────────────────
    if not inspector.has_table("global_library_memberships"):
        op.create_table(
            "global_library_memberships",
            sa.Column(
                "paper_id",
                sa.Integer(),
                sa.ForeignKey("papers.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("membership_schema_version", sa.String(30), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("membership_origin", sa.String(40), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("removed_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint(
                "membership_schema_version = 'global_library_v1'",
                name="ck_glm_schema_version",
            ),
            sa.CheckConstraint(
                "status IN ('active', 'removed')",
                name="ck_glm_status",
            ),
            sa.CheckConstraint(
                "membership_origin IS NULL OR membership_origin IN ('user_curated', 'admin_import', 'verified_migration')",
                name="ck_glm_origin",
            ),
            sa.CheckConstraint(
                "status != 'active' OR removed_at IS NULL",
                name="ck_glm_active_no_removed_at",
            ),
            sa.CheckConstraint(
                "status != 'removed' OR removed_at IS NOT NULL",
                name="ck_glm_removed_has_removed_at",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    if inspector.has_table("global_library_memberships"):
        op.drop_table("global_library_memberships")

    existing_cols = {c["name"] for c in inspector.get_columns("pipeline_runs")}
    if "domain_scope_key" in existing_cols:
        with op.batch_alter_table("pipeline_runs", recreate="always") as batch_op:
            try:
                batch_op.drop_constraint("ck_pipeline_runs_domain_scope", type_="check")
            except Exception:
                pass
            batch_op.drop_column("domain_scope_version")
            batch_op.drop_column("domain_scope_key")
