"""Migration: experiment_results proposal_id + manifest_json (Phase 5).

Adds two columns to experiment_results for the empirical execution path:
- proposal_id: nullable FK to proposals (links experiment to a generated proposal)
- manifest_json: Text, stores the ExperimentManifest as JSON

Revision ID: 034
Revises: 033
"""

from alembic import op
import sqlalchemy as sa

revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("experiment_results", sa.Column("proposal_id", sa.Integer(), nullable=True))
    op.add_column("experiment_results", sa.Column("manifest_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("experiment_results", "manifest_json")
    op.drop_column("experiment_results", "proposal_id")
