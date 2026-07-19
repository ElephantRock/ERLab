"""Migration: durable configuration resolution evidence (P0.5B WP4).

Creates tables for operation-linked, secret-safe configuration receipts.

  configuration_resolution_snapshots
      One snapshot per operation, immutable once linked.

  configuration_resolution_items
      One item per resolved field within a snapshot.

Secret fields never persist raw values — only presence markers.

Revision ID: 030
Revises: 029
"""

from alembic import op
import sqlalchemy as sa

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    if not inspector.has_table("configuration_resolution_snapshots"):
        op.create_table(
            "configuration_resolution_snapshots",
            sa.Column("snapshot_id", sa.String(64), primary_key=True),
            sa.Column("scope_kind", sa.String(40), nullable=False),
            sa.Column("scope_id", sa.String(255), nullable=False),
            sa.Column("registry_schema_version", sa.String(30), nullable=False),
            sa.Column("precedence_policy_version", sa.String(30), nullable=False),
            sa.Column("effective_configuration_fingerprint", sa.String(64), nullable=False),
            sa.Column(
                "created_at", sa.DateTime, nullable=False,
                server_default=sa.func.current_timestamp(),
            ),
            sa.CheckConstraint(
                "scope_kind IN ('search_execution', 'retrieval_event', 'generation', 'release', 'capability_verification')",
                name="ck_crs_scope_kind",
            ),
        )
        op.create_index(
            "ix_crs_scope", "configuration_resolution_snapshots",
            ["scope_kind", "scope_id"],
        )

    if not inspector.has_table("configuration_resolution_items"):
        op.create_table(
            "configuration_resolution_items",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column(
                "snapshot_id", sa.String(64),
                sa.ForeignKey("configuration_resolution_snapshots.snapshot_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("field_id", sa.String(120), nullable=False),
            sa.Column("effect_class", sa.String(40), nullable=False),
            sa.Column("winning_semantic_tier", sa.String(40), nullable=False),
            sa.Column("winning_physical_origin", sa.String(40), nullable=False),
            sa.Column("default_applied", sa.Boolean, nullable=False, server_default="0"),
            sa.Column("normalization_applied", sa.Boolean, nullable=False, server_default="0"),
            sa.Column("value_representation", sa.String(200), nullable=True),
            sa.Column("value_fingerprint", sa.String(32), nullable=True),
            sa.Column("shadowed_source_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("sensitivity", sa.String(20), nullable=False, server_default="public"),
        )
        op.create_index(
            "ix_cri_snapshot", "configuration_resolution_items",
            ["snapshot_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    if inspector.has_table("configuration_resolution_items"):
        try:
            op.drop_index("ix_cri_snapshot", table_name="configuration_resolution_items")
        except Exception:
            pass
        op.drop_table("configuration_resolution_items")

    if inspector.has_table("configuration_resolution_snapshots"):
        try:
            op.drop_index("ix_crs_scope", table_name="configuration_resolution_snapshots")
        except Exception:
            pass
        op.drop_table("configuration_resolution_snapshots")
