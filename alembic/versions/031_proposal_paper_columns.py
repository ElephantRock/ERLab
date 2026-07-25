"""Migration: persist full-paper artifact on proposals (Phase 1 1C).

Adds two nullable columns to `proposals`:

  paper_md         The synthesized full-paper markdown (PaperSynthesizer output)
  paper_meta_json  Synthesis metadata JSON: status, word_count, venue, model,
                   source_count, synthesis_strategy, generated_at.

Background: PaperSynthesisStage previously wrote the paper only to the
in-memory proposal.metadata["full_paper"] dict, which persist_proposals()
dropped on the floor. The paper was therefore generated but never persisted,
never returned by the API, and lost on process exit. These columns give the
paper a DB home on the existing Proposal row (one paper per proposal),
without introducing a new model or output-mode abstraction.

Revision ID: 031
Revises: 030
"""

from alembic import op
import sqlalchemy as sa

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("proposals", sa.Column("paper_md", sa.Text(), nullable=True))
    op.add_column("proposals", sa.Column("paper_meta_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("proposals", "paper_meta_json")
    op.drop_column("proposals", "paper_md")
