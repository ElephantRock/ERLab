"""Migration: governance_decisions table for audit-trail decisions.

Creates the append-only governance decisions table that tracks every
human review decision per idea (approved / denied / needs_changes).
Decisions are never updated or deleted.

Revision ID: 012
Revises: 011
"""

from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "governance_decisions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "idea_id",
            sa.Integer(),
            sa.ForeignKey("ideas.id"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("reviewer", sa.String(128), nullable=False, server_default="anonymous"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_governance_decisions_idea_id",
        "governance_decisions",
        ["idea_id"],
    )
    op.create_index(
        "ix_governance_decisions_created_at",
        "governance_decisions",
        ["created_at"],
    )
    op.create_index(
        "ix_governance_decisions_idea_created",
        "governance_decisions",
        ["idea_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_governance_decisions_idea_created", table_name="governance_decisions")
    op.drop_index("ix_governance_decisions_created_at", table_name="governance_decisions")
    op.drop_index("ix_governance_decisions_idea_id", table_name="governance_decisions")
    op.drop_table("governance_decisions")
