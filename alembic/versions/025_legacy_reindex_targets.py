"""Migration: legacy reindex target ledger (P0.3.5B1).

The record-level inventory alone is insufficient because several legacy
records can map to one canonical reindex target. This table provides the
authoritative target-level lifecycle independent of source records.

Revision ID: 025
Revises: 024
"""

from alembic import op
import sqlalchemy as sa

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    if not inspector.has_table("legacy_vector_reindex_targets"):
        op.create_table(
            "legacy_vector_reindex_targets",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("inventory_run_id", sa.Integer,
                      sa.ForeignKey("legacy_vector_inventory_runs.id", ondelete="CASCADE"),
                      nullable=False),
            sa.Column("paper_id", sa.Integer,
                      sa.ForeignKey("papers.id", ondelete="RESTRICT"),
                      nullable=False),
            sa.Column("chunk_key", sa.String(255), nullable=False),
            sa.Column("embedding_profile_id", sa.String(64),
                      sa.ForeignKey("embedding_profiles.profile_id", ondelete="RESTRICT"),
                      nullable=False),
            sa.Column("content_hash", sa.String(64), nullable=False),
            sa.Column("target_vector_record_id", sa.String(64), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="planned"),
            sa.Column("representative_legacy_record_id", sa.String(256), nullable=True),
            sa.Column("source_record_count", sa.Integer, nullable=False, server_default="1"),
            sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("failure_code", sa.String(80), nullable=True),
            sa.Column("failure_detail", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("completed_at", sa.DateTime, nullable=True),
            # Constraints
            sa.UniqueConstraint(
                "inventory_run_id", "paper_id", "chunk_key", "embedding_profile_id",
                name="uq_lvrt_target_identity",
            ),
            sa.CheckConstraint(
                "status IN ('planned','indexing','indexed','already_indexed',"
                "'content_unavailable','failed')",
                name="ck_lvrt_status",
            ),
            sa.CheckConstraint("attempt_count >= 0", name="ck_lvrt_attempt_count"),
            sa.CheckConstraint("source_record_count >= 1", name="ck_lvrt_source_count"),
        )
        op.create_index(
            "ix_lvrt_run_status", "legacy_vector_reindex_targets",
            ["inventory_run_id", "status"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)
    if inspector.has_table("legacy_vector_reindex_targets"):
        try:
            op.drop_index("ix_lvrt_run_status", table_name="legacy_vector_reindex_targets")
        except Exception:
            pass
        op.drop_table("legacy_vector_reindex_targets")
