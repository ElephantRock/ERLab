"""BATCH-49: Create notifications table.

Revision ID: 005_notifications
Revises: 004_gap_dedup
"""
from alembic import op
import sqlalchemy as sa

revision = "005_notifications"
down_revision = "004_gap_dedup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("read", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.create_index("ix_notifications_user_id", ["user_id"])
        batch_op.create_index("ix_notifications_read", ["read"])
        batch_op.create_index("ix_notifications_created_at", ["created_at"])


def downgrade() -> None:
    op.drop_table("notifications")
