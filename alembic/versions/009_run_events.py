"""Migration: durable run state — events, cancellations, workers.

Replaces process-local globals (_cancel_events, _progress_queues,
_background_tasks) with durable DB tables that survive process restart.

Tables:
- run_events: append-only event outbox for SSE/WS replay
- run_cancellations: explicit cancellation requests
- run_workers: worker lease tracking with heartbeat and orphan detection
"""

from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add columns to pipeline_runs and ideas that were added to the model without
    # corresponding migrations (schema drift fix).
    with op.batch_alter_table("pipeline_runs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "run_id_str",
                sa.String(50),
                nullable=True,
                comment="String run ID for URL-safe lookups",
            )
        )
        batch_op.add_column(
            sa.Column("stage_report_json", sa.Text(), nullable=True, comment="Per-stage observability report (BATCH-173)"),
        )
        batch_op.add_column(
            sa.Column("tree_data_json", sa.Text(), nullable=True, comment="Serialized search tree data"),
        )
        batch_op.create_index("ix_pipeline_runs_run_id_str", ["run_id_str"], unique=True)

    with op.batch_alter_table("ideas") as batch_op:
        batch_op.add_column(
            sa.Column("parent_idea_ids", sa.Text(), nullable=True, comment="JSON array of parent idea IDs for tree-based ideation"),
        )

    # Run events — append-only outbox for SSE/WS progress streaming.
    # seq is per-run monotonic, used for Last-Event-ID replay.
    op.create_table(
        "run_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("pipeline_runs.id"), nullable=False, index=True),
        sa.Column("seq", sa.Integer(), nullable=False, comment="Per-run monotonic sequence number"),
        sa.Column("event_type", sa.String(50), nullable=False, comment="stage_progress|completed|failed|cancelled|heartbeat"),
        sa.Column("payload", sa.Text(), nullable=True, comment="JSON event payload"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", "seq", name="uq_run_events_run_id_seq"),
    )

    # Run cancellations — explicit cancellation requests.
    # Durable: survives process restart so a cancelled run stays cancelled.
    op.create_table(
        "run_cancellations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("pipeline_runs.id"), nullable=False, index=True),
        sa.Column("run_id_str", sa.String(50), nullable=False, index=True, comment="String run ID for URL lookups"),
        sa.Column("requested_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("reason", sa.String(500), nullable=True),
    )

    # Run workers — durable lease tracking.
    # A run becomes running only if no active owner exists.
    # Stale heartbeat marks run orphaned for recovery.
    op.create_table(
        "run_workers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("pipeline_runs.id"), nullable=False, index=True),
        sa.Column("run_id_str", sa.String(50), nullable=False, index=True),
        sa.Column("worker_id", sa.String(100), nullable=False, comment="Unique worker identifier"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active", comment="active|orphaned|completed"),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("last_heartbeat", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("run_workers")
    op.drop_table("run_cancellations")
    op.drop_table("run_events")

    with op.batch_alter_table("ideas") as batch_op:
        batch_op.drop_column("parent_idea_ids")

    with op.batch_alter_table("pipeline_runs") as batch_op:
        batch_op.drop_index("ix_pipeline_runs_run_id_str")
        batch_op.drop_column("tree_data_json")
        batch_op.drop_column("stage_report_json")
        batch_op.drop_column("run_id_str")
