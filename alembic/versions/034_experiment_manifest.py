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
    # Create the table if it doesn't exist (it's normally created by
    # Base.metadata.create_all, not by a migration — but a fresh alembic
    # upgrade from base would not have it).
    from sqlalchemy import inspect as sa_inspect
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "experiment_results" not in inspector.get_table_names():
        op.create_table(
            "experiment_results",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("idea_id", sa.Integer(), sa.ForeignKey("ideas.id"), nullable=False),
            sa.Column("code_md", sa.Text(), nullable=False),
            sa.Column("stdout", sa.Text(), server_default=""),
            sa.Column("stderr", sa.Text(), server_default=""),
            sa.Column("exit_code", sa.Integer(), server_default="0"),
            sa.Column("success", sa.Boolean(), server_default="0"),
            sa.Column("execution_time_seconds", sa.Float(), server_default="0.0"),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("proposal_id", sa.Integer(), nullable=True),
            sa.Column("manifest_json", sa.Text(), nullable=True),
        )
    else:
        op.add_column("experiment_results", sa.Column("proposal_id", sa.Integer(), nullable=True))
        op.add_column("experiment_results", sa.Column("manifest_json", sa.Text(), nullable=True))


def downgrade() -> None:
    from sqlalchemy import inspect as sa_inspect
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "experiment_results" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("experiment_results")}
        if "manifest_json" in cols:
            op.drop_column("experiment_results", "manifest_json")
        if "proposal_id" in cols:
            op.drop_column("experiment_results", "proposal_id")
