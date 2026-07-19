"""Migration: binding activation, cutover, and write-guard schema (P0.4A2.1).

Migration B: creates the activation, cutover, and write-guard tables
that govern the atomic transition from pre-capability to capability-
bound vector retrieval.

Tables created:
  embedding_profile_binding_activations
      One row per governed activation attempt.
      At most one active activation per profile.

  embedding_binding_cutovers
      Generalized cutover ledger (paper, KG, tool).

  embedding_binding_cutover_items
      Per-item remediation tracking.

  embedding_profile_embedding_write_guards
      One guard row per persistent embedding profile + purpose.
      All persistent writes consult the guard before claiming work.

Revision ID: 029
Revises: 028
"""

from alembic import op
import sqlalchemy as sa

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    # ── 1. embedding_profile_binding_activations ──────────────────
    if not inspector.has_table("embedding_profile_binding_activations"):
        op.create_table(
            "embedding_profile_binding_activations",
            sa.Column("activation_id", sa.String(64), primary_key=True),
            sa.Column(
                "embedding_profile_id", sa.String(64),
                sa.ForeignKey("embedding_profiles.profile_id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("embedding_purpose", sa.String(40), nullable=False),
            sa.Column(
                "capability_binding_id", sa.String(64),
                sa.ForeignKey(
                    "embedding_capability_bindings.binding_id", ondelete="RESTRICT"
                ),
                nullable=False,
            ),
            sa.Column(
                "cutover_id", sa.String(64),
                nullable=True,  # NOT NULL when active
            ),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("activation_generation", sa.Integer, nullable=False),
            sa.Column(
                "created_at", sa.DateTime, nullable=False,
                server_default=sa.func.current_timestamp(),
            ),
            sa.Column("activated_at", sa.DateTime, nullable=True),
            sa.Column("retired_at", sa.DateTime, nullable=True),
            sa.Column("rejected_at", sa.DateTime, nullable=True),
            sa.CheckConstraint(
                "status IN ('candidate','active','retired','rejected')",
                name="ck_epba_status",
            ),
            sa.CheckConstraint(
                "activation_generation > 0",
                name="ck_epba_generation_positive",
            ),
            sa.CheckConstraint(
                "embedding_purpose IN ('paper','knowledge_graph_entity','tool_description')",
                name="ck_epba_purpose",
            ),
            # active requires cutover_id and activated_at
            sa.CheckConstraint(
                "status != 'active' OR (cutover_id IS NOT NULL AND activated_at IS NOT NULL)",
                name="ck_epba_active_requires_cutover",
            ),
            # retired requires retired_at
            sa.CheckConstraint(
                "status != 'retired' OR retired_at IS NOT NULL",
                name="ck_epba_retired_requires_timestamp",
            ),
            # rejected requires rejected_at
            sa.CheckConstraint(
                "status != 'rejected' OR rejected_at IS NOT NULL",
                name="ck_epba_rejected_requires_timestamp",
            ),
        )
        op.create_index(
            "ix_epba_profile_status", "embedding_profile_binding_activations",
            ["embedding_profile_id", "status"],
        )
        op.create_index(
            "ix_epba_binding_id", "embedding_profile_binding_activations",
            ["capability_binding_id"],
        )

    # ── 2. embedding_binding_cutovers ─────────────────────────────
    if not inspector.has_table("embedding_binding_cutovers"):
        op.create_table(
            "embedding_binding_cutovers",
            sa.Column("cutover_id", sa.String(64), primary_key=True),
            sa.Column("cutover_schema_version", sa.String(30), nullable=False),
            sa.Column(
                "embedding_profile_id", sa.String(64),
                sa.ForeignKey("embedding_profiles.profile_id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("embedding_purpose", sa.String(40), nullable=False),
            sa.Column("source_contract_version", sa.String(30), nullable=False),
            sa.Column("source_binding_id", sa.String(64), nullable=True),
            sa.Column(
                "target_binding_id", sa.String(64),
                sa.ForeignKey(
                    "embedding_capability_bindings.binding_id", ondelete="RESTRICT"
                ),
                nullable=False,
            ),
            sa.Column("source_snapshot_kind", sa.String(40), nullable=False),
            sa.Column("source_snapshot_fingerprint", sa.String(64), nullable=False),
            sa.Column("source_item_count", sa.Integer, nullable=False),
            sa.Column("target_indexed_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("target_failed_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("content_unavailable_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("verification_failure_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("write_guard_epoch", sa.Integer, nullable=True),
            sa.Column(
                "created_at", sa.DateTime, nullable=False,
                server_default=sa.func.current_timestamp(),
            ),
            sa.Column("snapshot_completed_at", sa.DateTime, nullable=True),
            sa.Column("reindex_completed_at", sa.DateTime, nullable=True),
            sa.Column("verified_at", sa.DateTime, nullable=True),
            sa.Column("sealed_at", sa.DateTime, nullable=True),
            sa.Column("activated_at", sa.DateTime, nullable=True),
            sa.Column("failed_at", sa.DateTime, nullable=True),
            sa.Column("failure_code", sa.String(80), nullable=True),
            sa.Column("sanitized_failure_detail", sa.String(500), nullable=True),
            sa.CheckConstraint(
                "cutover_schema_version = 'cutover_v1'",
                name="ck_ebc_schema_version",
            ),
            sa.CheckConstraint(
                "status IN ('pending','snapshotting','reindexing','verifying',"
                "'ready','sealed','active','failed','cancelled')",
                name="ck_ebc_status",
            ),
            sa.CheckConstraint(
                "embedding_purpose IN ('paper','knowledge_graph_entity','tool_description')",
                name="ck_ebc_purpose",
            ),
            sa.CheckConstraint("source_item_count >= 0", name="ck_ebc_source_count"),
            sa.CheckConstraint("target_indexed_count >= 0", name="ck_ebc_indexed_count"),
            sa.CheckConstraint("target_failed_count >= 0", name="ck_ebc_failed_count"),
        )
        op.create_index(
            "ix_ebc_profile_status", "embedding_binding_cutovers",
            ["embedding_profile_id", "status"],
        )
        op.create_index(
            "ix_ebc_target_binding", "embedding_binding_cutovers",
            ["target_binding_id"],
        )

    # ── 3. embedding_binding_cutover_items ────────────────────────
    if not inspector.has_table("embedding_binding_cutover_items"):
        op.create_table(
            "embedding_binding_cutover_items",
            sa.Column("item_id", sa.String(64), primary_key=True),
            sa.Column(
                "cutover_id", sa.String(64),
                sa.ForeignKey("embedding_binding_cutovers.cutover_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("source_object_type", sa.String(40), nullable=False),
            sa.Column("source_object_id", sa.String(255), nullable=False),
            sa.Column("source_vector_record_id", sa.String(64), nullable=True),
            sa.Column("paper_id", sa.Integer, nullable=True),
            sa.Column("chunk_key", sa.String(255), nullable=True),
            sa.Column("canonical_content_hash", sa.String(64), nullable=False),
            sa.Column("source_contract_version", sa.String(30), nullable=False),
            sa.Column("target_vector_record_id", sa.String(64), nullable=True),
            sa.Column("target_collection_name", sa.String(120), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("claimed_at", sa.DateTime, nullable=True),
            sa.Column("completed_at", sa.DateTime, nullable=True),
            sa.Column("failure_code", sa.String(80), nullable=True),
            sa.Column("sanitized_failure_detail", sa.String(500), nullable=True),
            sa.CheckConstraint(
                "status IN ('pending','indexing','indexed','already_indexed',"
                "'content_unavailable','failed')",
                name="ck_ebci_status",
            ),
            sa.CheckConstraint("attempt_count >= 0", name="ck_ebci_attempt_count"),
        )
        op.create_index(
            "ix_ebci_cutover_status", "embedding_binding_cutover_items",
            ["cutover_id", "status"],
        )

    # ── 4. embedding_profile_embedding_write_guards ───────────────
    if not inspector.has_table("embedding_profile_embedding_write_guards"):
        op.create_table(
            "embedding_profile_embedding_write_guards",
            sa.Column(
                "embedding_profile_id", sa.String(64),
                sa.ForeignKey("embedding_profiles.profile_id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("embedding_purpose", sa.String(40), nullable=False),
            sa.Column("state", sa.String(20), nullable=False, server_default="open"),
            sa.Column("guard_epoch", sa.Integer, nullable=False, server_default="0"),
            sa.Column("cutover_id", sa.String(64), nullable=True),
            sa.Column("frozen_at", sa.DateTime, nullable=True),
            sa.Column("released_at", sa.DateTime, nullable=True),
            sa.CheckConstraint(
                "state IN ('open','frozen')",
                name="ck_epewg_state",
            ),
            sa.CheckConstraint(
                "embedding_purpose IN ('paper','knowledge_graph_entity','tool_description')",
                name="ck_epewg_purpose",
            ),
            # frozen requires cutover_id and frozen_at
            sa.CheckConstraint(
                "state != 'frozen' OR (cutover_id IS NOT NULL AND frozen_at IS NOT NULL)",
                name="ck_epewg_frozen_requires_cutover",
            ),
        )
        # One guard row per profile + purpose
        op.create_index(
            "ix_epewg_profile_purpose", "embedding_profile_embedding_write_guards",
            ["embedding_profile_id", "embedding_purpose"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    for table_name in (
        "embedding_profile_embedding_write_guards",
        "embedding_binding_cutover_items",
        "embedding_binding_cutovers",
        "embedding_profile_binding_activations",
    ):
        if inspector.has_table(table_name):
            # Drop indexes first
            for ix in inspector.get_indexes(table_name):
                try:
                    op.drop_index(ix["name"], table_name=table_name)
                except Exception:
                    pass
            op.drop_table(table_name)
