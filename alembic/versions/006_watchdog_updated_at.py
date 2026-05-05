"""Add updated_at column to pipeline_runs for watchdog tracking.

BATCH-74/TASK-03: Pipeline run watchdog needs updated_at to detect stale runs.
"""

from alembic import op
import sqlalchemy as sa

revision = "006_watchdog_updated_at"
down_revision = "005_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pipeline_runs",
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pipeline_runs", "updated_at")
