"""Migration: add legacy_identity_json column (P0.3.5 completion).

Stores the frozen ExtractedLegacyIdentity snapshot in each inventory record
so the mapping phase reads from the immutable snapshot, not mutable Chroma.

Revision ID: 026
Revises: 025
"""

from alembic import op
import sqlalchemy as sa

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("legacy_vector_inventory_records")}

    if "legacy_identity_json" not in existing_cols:
        with op.batch_alter_table("legacy_vector_inventory_records", recreate="always") as batch_op:
            batch_op.add_column(sa.Column("legacy_identity_json", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("legacy_vector_inventory_records")}

    if "legacy_identity_json" in existing_cols:
        with op.batch_alter_table("legacy_vector_inventory_records", recreate="always") as batch_op:
            batch_op.drop_column("legacy_identity_json")
