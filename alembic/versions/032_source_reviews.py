"""Migration: human source-review decisions + proposal-evaluation persistence (Phase 2).

Two changes:

1. `source_reviews` table — append-only, per-idea, per-source decisions with the
   enum accepted | flagged | exclude_on_next_revision (WP-2E). 2A established no
   existing model can represent per-source review decisions without distortion.

2. `proposals.proposal_evaluation_json` — persists the proposal-scope evaluation
   that EvaluationStage computes into metadata["evaluation"] and that
   persist_proposals currently drops (2A bug). Keeps proposal and paper
   evaluations both visible and distinct (WP-2B truth rule).

Background: Phase 2 restores trust and review depth. Source review lets a human
accept, flag, or mark a source for exclusion on the next revision. Decisions do
NOT mutate the current paper (immutability rule, WP-2E).

Revision ID: 032
Revises: 031
"""

from alembic import op
import sqlalchemy as sa

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Source-review decisions table.
    op.create_table(
        "source_reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("idea_id", sa.Integer(), sa.ForeignKey("ideas.id"), nullable=False),
        sa.Column("source_ref_hash", sa.String(length=64), nullable=False),
        sa.Column("source_ref_number", sa.Integer(), nullable=True),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reviewer", sa.String(length=128), nullable=False, server_default="anonymous"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_source_reviews_idea_id", "source_reviews", ["idea_id"])
    op.create_index("ix_source_reviews_source_ref_hash", "source_reviews", ["source_ref_hash"])
    op.create_index("ix_source_reviews_idea_hash", "source_reviews", ["idea_id", "source_ref_hash"])

    # 2. Proposal-evaluation persistence (2A bug fix).
    op.add_column("proposals", sa.Column("proposal_evaluation_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("proposals", "proposal_evaluation_json")
    op.drop_index("ix_source_reviews_idea_hash", table_name="source_reviews")
    op.drop_index("ix_source_reviews_source_ref_hash", table_name="source_reviews")
    op.drop_index("ix_source_reviews_idea_id", table_name="source_reviews")
    op.drop_table("source_reviews")
