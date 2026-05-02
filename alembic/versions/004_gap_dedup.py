"""BATCH-42: Add deduplication columns to research_gaps.

Revision ID: 004_gap_dedup
Revises: 003_gap_feedback
"""
from alembic import op
import sqlalchemy as sa

revision = "004_gap_dedup"
down_revision = "003_gap_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("research_gaps", schema=None) as batch_op:
        batch_op.add_column(sa.Column("canonical_id", sa.String(128), nullable=True))
        batch_op.add_column(sa.Column("content_hash", sa.String(64), nullable=True))
        batch_op.create_index("ix_research_gaps_content_hash", ["content_hash"])


def downgrade() -> None:
    with op.batch_alter_table("research_gaps", schema=None) as batch_op:
        batch_op.drop_index("ix_research_gaps_content_hash")
        batch_op.drop_column("content_hash")
        batch_op.drop_column("canonical_id")
