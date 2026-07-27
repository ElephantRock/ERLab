"""Migration: paper_source_markers — durable marker-to-source map (Phase 4 / WP-4B).

Background: Phase 3 closeout found all six live papers contained ``[SOURCE-N]``
markers (10-83 per paper) but zero bibliography or recoverable source identity.
The Phase 4 provenance trace (docs/project/phase4/PHASE_4_SOURCE_PROVENANCE_TRACE.md)
established that the first demonstrated loss boundary is the non-persistence of
the synthesis-time marker-to-source map: ``PaperSynthesisStage`` builds the map
as an in-memory ``list[str]`` and discards it on return.

This migration introduces the smallest run-scoped source manifest: one row per
cited source per generated paper (one paper per proposal), carrying the literal
marker (``SOURCE-1``), a link back to the existing ``papers`` row, or an
explicit ``unmapped`` state. Bibliographic fields stay on ``Paper``; this table
holds only the linkage. ``run_id`` is derivable through proposal ownership,
``source_rank`` duplicates ``marker_index``, and ``synthesis_strategy`` belongs
in existing paper metadata — so none are duplicated here.

Truth rules enforced by the schema:
  * UNIQUE (proposal_id, marker_index) — one canonical slot per marker.
  * mapping_status in {mapped, unmapped} — a marker without a mapped source is
    explicit, never silently dropped.

Revision ID: 033
Revises: 032
"""

from alembic import op
import sqlalchemy as sa

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_source_markers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("proposal_id", sa.Integer(), sa.ForeignKey("proposals.id"), nullable=False),
        sa.Column("marker_index", sa.Integer(), nullable=False),
        sa.Column("marker", sa.String(length=32), nullable=False),
        sa.Column("source_paper_id", sa.Integer(), sa.ForeignKey("papers.id"), nullable=True),
        sa.Column(
            "mapping_status",
            sa.String(length=16),
            nullable=False,
            server_default="mapped",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "proposal_id", "marker_index", name="uq_proposal_marker_index"
        ),
        sa.CheckConstraint(
            "mapping_status IN ('mapped', 'unmapped')",
            name="ck_paper_source_markers_mapping_status",
        ),
    )
    op.create_index(
        "ix_paper_source_markers_proposal_id", "paper_source_markers", ["proposal_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_paper_source_markers_proposal_id", table_name="paper_source_markers"
    )
    op.drop_table("paper_source_markers")
