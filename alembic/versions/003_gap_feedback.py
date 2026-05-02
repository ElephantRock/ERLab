"""BATCH-41: Add feedback & lifecycle columns to research_gaps.

Revision ID: 003_gap_feedback
Revises: 002_gap_enrichment
"""
from alembic import op
import sqlalchemy as sa

revision = "003_gap_feedback"
down_revision = "38a2b1e7c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("research_gaps", schema=None) as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(20), server_default="identified", nullable=False))
        batch_op.add_column(sa.Column("user_rating", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("user_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("research_gaps", schema=None) as batch_op:
        batch_op.drop_column("user_notes")
        batch_op.drop_column("user_rating")
        batch_op.drop_column("status")
