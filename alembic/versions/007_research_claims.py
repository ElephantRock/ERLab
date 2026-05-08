"""Add research_claims table for structured claim storage (BATCH-122)."""

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_claims",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("claim_id", sa.String(36), unique=True, nullable=False),
        sa.Column("claim_type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_paper_id", sa.String(256), nullable=False),
        sa.Column("source_section", sa.String(50), server_default="abstract"),
        sa.Column("confidence", sa.Float(), server_default="0.5"),
        sa.Column("method_name", sa.String(200), nullable=True),
        sa.Column("method_category", sa.String(50), nullable=True),
        sa.Column("dataset", sa.String(200), nullable=True),
        sa.Column("metric", sa.String(100), nullable=True),
        sa.Column("value", sa.String(100), nullable=True),
        sa.Column("baseline_method", sa.String(200), nullable=True),
        sa.Column("baseline_value", sa.String(100), nullable=True),
        sa.Column("limitation_category", sa.String(50), nullable=True),
        sa.Column("acknowledged", sa.Boolean(), nullable=True),
        sa.Column("feasibility", sa.String(20), nullable=True),
        sa.Column("potential_impact", sa.String(20), nullable=True),
        sa.Column("compared_to", sa.String(200), nullable=True),
        sa.Column("relationship", sa.String(50), nullable=True),
        sa.Column("extra_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_research_claims_paper_id", "research_claims", ["source_paper_id"])
    op.create_index("ix_research_claims_type", "research_claims", ["claim_type"])


def downgrade() -> None:
    op.drop_index("ix_research_claims_type")
    op.drop_index("ix_research_claims_paper_id")
    op.drop_table("research_claims")
