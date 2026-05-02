"""gap_enrichment

Revision ID: 38a2b1e7c4d5
Revises: 29607f14fd7f
Create Date: 2026-05-02

Adds truth value columns to research_gaps and cluster_report_json to pipeline_runs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '38a2b1e7c4d5'
down_revision: Union[str, None] = '29607f14fd7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add truth value columns to research_gaps
    with op.batch_alter_table('research_gaps', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('truth_frequency', sa.Float(), nullable=True, server_default='0.5')
        )
        batch_op.add_column(
            sa.Column('truth_confidence', sa.Float(), nullable=True, server_default='0.5')
        )
        batch_op.add_column(
            sa.Column('truth_evidence_count', sa.Integer(), nullable=True, server_default='0')
        )
        batch_op.add_column(
            sa.Column('related_clusters', sa.Text(), nullable=True)
        )

    # Add cluster report JSON to pipeline_runs
    with op.batch_alter_table('pipeline_runs', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('cluster_report_json', sa.Text(), nullable=True)
        )


def downgrade() -> None:
    # Remove cluster report JSON from pipeline_runs
    with op.batch_alter_table('pipeline_runs', schema=None) as batch_op:
        batch_op.drop_column('cluster_report_json')

    # Remove truth value columns from research_gaps
    with op.batch_alter_table('research_gaps', schema=None) as batch_op:
        batch_op.drop_column('related_clusters')
        batch_op.drop_column('truth_evidence_count')
        batch_op.drop_column('truth_confidence')
        batch_op.drop_column('truth_frequency')
