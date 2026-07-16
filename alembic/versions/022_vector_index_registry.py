"""Migration: governed vector index registry (P0.3.2).

Creates two tables:
  embedding_profiles   — durable profile declarations (unverified until P0.4)
  vector_index_records — canonical vector lifecycle (pending→indexing→indexed)

No registry rows are fabricated for existing Chroma records. Legacy
``research_papers`` collection is classified as ``legacy_unscoped``.

Revision ID: 022
Revises: 021
"""

from alembic import op
import sqlalchemy as sa

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    # ── 1. embedding_profiles ─────────────────────────────────────
    if not inspector.has_table("embedding_profiles"):
        op.create_table(
            "embedding_profiles",
            sa.Column("profile_id", sa.String(64), primary_key=True),
            sa.Column("profile_schema_version", sa.String(30), nullable=False),
            sa.Column("provider", sa.String(80), nullable=False),
            sa.Column("model_identifier", sa.String(255), nullable=False),
            sa.Column("dimension", sa.Integer, nullable=False),
            sa.Column("normalization_policy", sa.String(80), nullable=False),
            sa.Column("chunking_schema_version", sa.String(80), nullable=False),
            sa.Column("collection_name", sa.String(120), nullable=False),
            sa.Column("verification_status", sa.String(20), nullable=False),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
            sa.CheckConstraint(
                "profile_schema_version = 'embedding_profile_v1'",
                name="ck_ep_schema_version",
            ),
            sa.CheckConstraint(
                "verification_status = 'unverified'",
                name="ck_ep_verification_status",
            ),
            sa.CheckConstraint("dimension > 0", name="ck_ep_dimension_positive"),
            sa.UniqueConstraint("collection_name", name="uq_ep_collection_name"),
        )

    # ── 2. vector_index_records ───────────────────────────────────
    if not inspector.has_table("vector_index_records"):
        op.create_table(
            "vector_index_records",
            # Identity
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("vector_record_id", sa.String(64), nullable=False),
            sa.Column("paper_id", sa.Integer,
                      sa.ForeignKey("papers.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("chunk_key", sa.String(255), nullable=False),
            sa.Column("content_kind", sa.String(40), nullable=False),
            sa.Column("content_hash", sa.String(64), nullable=False),
            sa.Column("embedding_profile_id", sa.String(64),
                      sa.ForeignKey("embedding_profiles.profile_id", ondelete="RESTRICT"),
                      nullable=False),
            # Backend placement
            sa.Column("vector_store", sa.String(40), nullable=False, server_default="chroma"),
            sa.Column("collection_name", sa.String(120), nullable=False),
            sa.Column("index_schema_version", sa.String(30), nullable=False,
                      server_default="vector_index_v1"),
            # Lifecycle
            sa.Column("index_status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("failure_code", sa.String(80), nullable=True),
            sa.Column("failure_detail", sa.Text, nullable=True),
            sa.Column("indexing_started_at", sa.DateTime, nullable=True),
            sa.Column("indexed_at", sa.DateTime, nullable=True),
            sa.Column("backend_verified_at", sa.DateTime, nullable=True),
            sa.Column("stale_at", sa.DateTime, nullable=True),
            sa.Column("deleting_started_at", sa.DateTime, nullable=True),
            sa.Column("deleted_at", sa.DateTime, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
            # Uniqueness
            sa.UniqueConstraint("vector_record_id", name="uq_vir_vector_record_id"),
            sa.UniqueConstraint(
                "paper_id", "chunk_key", "content_hash", "embedding_profile_id",
                name="uq_vir_chunk_identity",
            ),
            # Vocabularies
            sa.CheckConstraint("vector_store = 'chroma'", name="ck_vir_vector_store"),
            sa.CheckConstraint(
                "index_schema_version = 'vector_index_v1'", name="ck_vir_index_schema",
            ),
            sa.CheckConstraint(
                "content_kind IN ('title_abstract', 'abstract', 'full_text_chunk', 'metadata')",
                name="ck_vir_content_kind",
            ),
            sa.CheckConstraint(
                "index_status IN ('pending','indexing','indexed','failed','stale','deleting','deleted')",
                name="ck_vir_index_status",
            ),
            sa.CheckConstraint("attempt_count >= 0", name="ck_vir_attempt_count_nonnegative"),
            # SHA-256 format checks
            sa.CheckConstraint(
                "length(vector_record_id) = 64 AND vector_record_id = lower(vector_record_id)",
                name="ck_vir_vector_record_id_format",
            ),
            sa.CheckConstraint(
                "length(content_hash) = 64 AND content_hash = lower(content_hash)",
                name="ck_vir_content_hash_format",
            ),
            sa.CheckConstraint(
                "length(embedding_profile_id) = 64 AND embedding_profile_id = lower(embedding_profile_id)",
                name="ck_vir_embedding_profile_id_format",
            ),
        )
        op.create_index(
            "ix_vir_paper_id", "vector_index_records", ["paper_id"],
        )
        op.create_index(
            "ix_vir_profile_status", "vector_index_records",
            ["embedding_profile_id", "index_status"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    if inspector.has_table("vector_index_records"):
        try:
            op.drop_index("ix_vir_profile_status", table_name="vector_index_records")
            op.drop_index("ix_vir_paper_id", table_name="vector_index_records")
        except Exception:
            pass
        op.drop_table("vector_index_records")

    if inspector.has_table("embedding_profiles"):
        op.drop_table("embedding_profiles")
