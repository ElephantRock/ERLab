"""Migration: proposal_section_revisions table for revision tracking.

Creates the append-only revision table that tracks every change to a
proposal section — pipeline origin, user-triggered refinement, and rollback.
Includes SHA-256 content hashes for optimistic concurrency and audit.

Revision ID: 011
Revises: 010
"""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proposal_section_revisions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "proposal_id",
            sa.Integer(),
            sa.ForeignKey("proposals.id"),
            nullable=False,
        ),
        sa.Column("section_key", sa.String(50), nullable=False),
        sa.Column("section_text", sa.Text(), nullable=False),
        sa.Column("section_hash", sa.String(64), nullable=False),
        sa.Column("previous_text", sa.Text(), nullable=True),
        sa.Column("previous_hash", sa.String(64), nullable=True),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("trigger", sa.String(30), nullable=False),
        sa.Column("trigger_detail", sa.Text(), nullable=True),
        sa.Column("model_receipt_json", sa.Text(), nullable=True),
        sa.Column("quality_checks_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_psr_proposal_section_created",
        "proposal_section_revisions",
        ["proposal_id", "section_key", "created_at"],
    )
    op.create_index(
        "ix_psr_proposal_created",
        "proposal_section_revisions",
        ["proposal_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_psr_proposal_created", table_name="proposal_section_revisions")
    op.drop_index("ix_psr_proposal_section_created", table_name="proposal_section_revisions")
    op.drop_table("proposal_section_revisions")
