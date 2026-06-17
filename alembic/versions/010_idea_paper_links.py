"""Migration: idea_paper_links junction table for schema-backed provenance.

Creates the idea_paper_links table linking ideas to supporting/cited papers.
The unique constraint includes ``role`` so the same paper can appear as both
'supporting' and 'cited' for a single idea.

Revision ID: 010
Revises: 009
"""

from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idea_paper_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "idea_id",
            sa.Integer(),
            sa.ForeignKey("ideas.id"),
            nullable=False,
        ),
        sa.Column(
            "paper_id",
            sa.Integer(),
            sa.ForeignKey("papers.id"),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(30),
            nullable=False,
            server_default="supporting",
            comment="supporting | cited",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "idea_id", "paper_id", "role", name="uq_idea_paper_role",
        ),
    )
    op.create_index(
        "ix_idea_paper_links_idea_id", "idea_paper_links", ["idea_id"],
    )
    op.create_index(
        "ix_idea_paper_links_paper_id", "idea_paper_links", ["paper_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_idea_paper_links_paper_id", table_name="idea_paper_links")
    op.drop_index("ix_idea_paper_links_idea_id", table_name="idea_paper_links")
    op.drop_table("idea_paper_links")
