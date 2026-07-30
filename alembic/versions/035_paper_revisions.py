"""Migration: paper revision history table (Phase 9 9D).

Creates ``paper_revisions`` — an append-only table storing every version
of a paper: original draft, automatic remediation, manual recovery.

The live ``proposals.paper_md`` always holds the accepted version. This
table preserves the full history including failed drafts.

Constraints:
  UNIQUE(proposal_id, revision_number) — atomic one-revision enforcement
  revision_number >= 0
  revision 0 = original, revision 1 = first remediation

Revision ID: 035
Revises: 034
"""

from alembic import op
import sqlalchemy as sa

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_revisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("proposal_id", sa.Integer(), nullable=False),
        sa.Column("experiment_result_id", sa.Integer(), nullable=True),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("parent_revision_id", sa.Integer(), nullable=True),
        sa.Column("paper_md", sa.Text(), nullable=False),
        sa.Column("paper_hash", sa.String(64), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("trigger", sa.String(40), nullable=False),
        sa.Column("trigger_detail_json", sa.Text(), nullable=True),
        sa.Column("directive_json", sa.Text(), nullable=True),
        sa.Column("eval_status", sa.String(20), nullable=False),
        sa.Column("gates_json", sa.Text(), nullable=True),
        sa.Column("experiment_manifest_hash", sa.String(64), nullable=True),
        sa.Column("result_map_hash", sa.String(64), nullable=True),
        sa.Column("source_map_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("revision_number >= 0", name="ck_paper_rev_nonneg"),
        sa.UniqueConstraint("proposal_id", "revision_number", name="uq_paper_rev_proposal_number"),
        sa.ForeignKeyConstraint(["proposal_id"], ["proposals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_paper_rev_proposal_number",
        "paper_revisions",
        ["proposal_id", "revision_number"],
    )
    op.create_index(
        "ix_paper_rev_proposal_created",
        "paper_revisions",
        ["proposal_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_paper_rev_proposal_created", table_name="paper_revisions")
    op.drop_index("ix_paper_rev_proposal_number", table_name="paper_revisions")
    op.drop_table("paper_revisions")
