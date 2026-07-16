"""Migration: legacy vector migration ledger (P0.3.5).

Two tables for immutable inventory and reindex tracking:
  legacy_vector_inventory_runs    — one row per scan+reindex attempt
  legacy_vector_inventory_records — one row per legacy Chroma record

No historical inventory rows are fabricated.

Revision ID: 024
Revises: 023
"""

from alembic import op
import sqlalchemy as sa

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    # ── 1. legacy_vector_inventory_runs ───────────────────────────
    if not inspector.has_table("legacy_vector_inventory_runs"):
        op.create_table(
            "legacy_vector_inventory_runs",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("inventory_schema_version", sa.String(30), nullable=False),
            sa.Column("vector_store", sa.String(40), nullable=False, server_default="chroma"),
            sa.Column("collection_name", sa.String(120), nullable=False),
            sa.Column("target_embedding_profile_id", sa.String(64),
                      sa.ForeignKey("embedding_profiles.profile_id", ondelete="RESTRICT"),
                      nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            # Source counts
            sa.Column("source_record_count", sa.Integer, nullable=True),
            sa.Column("mapped_record_count", sa.Integer, nullable=True),
            sa.Column("ambiguous_record_count", sa.Integer, nullable=True),
            sa.Column("unmapped_record_count", sa.Integer, nullable=True),
            sa.Column("invalid_record_count", sa.Integer, nullable=True),
            sa.Column("identity_conflict_count", sa.Integer, nullable=True),
            # Target counts
            sa.Column("distinct_target_paper_count", sa.Integer, nullable=True),
            sa.Column("newly_indexed_target_count", sa.Integer, nullable=True),
            sa.Column("already_indexed_target_count", sa.Integer, nullable=True),
            sa.Column("duplicate_target_record_count", sa.Integer, nullable=True),
            sa.Column("content_unavailable_target_count", sa.Integer, nullable=True),
            sa.Column("reindex_failed_target_count", sa.Integer, nullable=True),
            # Snapshot
            sa.Column("source_snapshot_fingerprint", sa.String(64), nullable=True),
            # Failure
            sa.Column("failure_code", sa.String(80), nullable=True),
            sa.Column("failure_detail", sa.Text, nullable=True),
            # Timestamps
            sa.Column("started_at", sa.DateTime, nullable=True),
            sa.Column("scanned_at", sa.DateTime, nullable=True),
            sa.Column("completed_at", sa.DateTime, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
            # Constraints
            sa.CheckConstraint(
                "inventory_schema_version = 'legacy_vector_inventory_v1'",
                name="ck_lvir_schema_version",
            ),
            sa.CheckConstraint(
                "status IN ('pending','scanning','scanned','reindexing','complete','failed')",
                name="ck_lvir_status",
            ),
        )

    # ── 2. legacy_vector_inventory_records ────────────────────────
    if not inspector.has_table("legacy_vector_inventory_records"):
        op.create_table(
            "legacy_vector_inventory_records",
            # Identity
            sa.Column("inventory_run_id", sa.Integer,
                      sa.ForeignKey("legacy_vector_inventory_runs.id", ondelete="CASCADE"),
                      primary_key=True),
            sa.Column("legacy_record_id", sa.String(256), primary_key=True),
            # Legacy snapshot
            sa.Column("legacy_record_fingerprint", sa.String(64), nullable=False),
            sa.Column("legacy_metadata_fingerprint", sa.String(64), nullable=True),
            sa.Column("legacy_document_hash", sa.String(64), nullable=True),
            sa.Column("legacy_embedding_dimension", sa.Integer, nullable=True),
            # Mapping
            sa.Column("mapping_schema_version", sa.String(30), nullable=False),
            sa.Column("mapping_status", sa.String(30), nullable=False),
            sa.Column("mapping_method", sa.String(40), nullable=True),
            sa.Column("mapped_paper_id", sa.Integer, nullable=True),
            sa.Column("candidate_match_count", sa.Integer, nullable=True),
            sa.Column("identity_conflict_code", sa.String(60), nullable=True),
            # Disposition
            sa.Column("disposition", sa.String(40), nullable=True),
            sa.Column("target_vector_record_id", sa.String(64), nullable=True),
            # Failure
            sa.Column("failure_code", sa.String(80), nullable=True),
            sa.Column("failure_detail", sa.Text, nullable=True),
            # Timestamps
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("completed_at", sa.DateTime, nullable=True),
            # Constraints
            sa.CheckConstraint(
                "mapping_status IN ('mapped','ambiguous','unmapped','invalid','identity_conflict')",
                name="ck_lvirec_mapping_status",
            ),
            sa.CheckConstraint(
                "mapping_method IS NULL OR mapping_method IN "
                "('paper_id_exact','doi_exact','source_identifier_exact',"
                "'title_author_year_exact','none')",
                name="ck_lvirec_mapping_method",
            ),
            sa.CheckConstraint(
                "disposition IS NULL OR disposition IN "
                "('reindexed','already_indexed','duplicate_target',"
                "'quarantined_ambiguous','quarantined_unmapped',"
                "'quarantined_invalid','quarantined_identity_conflict',"
                "'content_unavailable','reindex_failed')",
                name="ck_lvirec_disposition",
            ),
        )
        op.create_index(
            "ix_lvirec_run_mapping", "legacy_vector_inventory_records",
            ["inventory_run_id", "mapping_status"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    if inspector.has_table("legacy_vector_inventory_records"):
        try:
            op.drop_index("ix_lvirec_run_mapping", table_name="legacy_vector_inventory_records")
        except Exception:
            pass
        op.drop_table("legacy_vector_inventory_records")

    if inspector.has_table("legacy_vector_inventory_runs"):
        op.drop_table("legacy_vector_inventory_runs")
