"""add stages_failed to pipeline_runs

Revision ID: 036_stages_failed
Revises: 035_paper_revisions
Create Date: 2026-09-12
"""
from alembic import op
import sqlalchemy as sa

revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pipeline_runs", sa.Column("stages_failed", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("pipeline_runs", "stages_failed")
