"""Migration: quarantined_citations table for fabricated-citation audit trail.

Creates the append-only quarantined citations table. One row per fabricated
[source-x] citation found by citation_audit. Rows are never updated or deleted.

STOPGAP: this table exists because the in-memory quarantine side-channel
evaporates at persistence. It follows the pattern established by
ProposalSectionRevision and GovernanceDecision — append-only audit-trail tables
for trust-relevant facts. When proposal.sections gains an ownership contract,
this table should be revisited.

Revision ID: 013
Revises: 012
"""

import sqlalchemy as sa

from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Guard against the table already existing: db/database.py:init_db() calls
    # Base.metadata.create_all() at startup, which creates any table defined in
    # models.py regardless of migration state. On a dev DB that has run init_db()
    # but not `alembic upgrade head`, this table already exists and a bare
    # op.create_table would raise. No existing migration in this repo guards
    # against this; this one does because it's the correct shape and because the
    # project's migration hygiene (12 migrations for 193 batches + auto-patching)
    # makes the collision likely in practice.
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)
    if inspector.has_table("quarantined_citations"):
        # Table already created by create_all(); just ensure indexes exist.
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("quarantined_citations")}
        if "ix_qc_proposal_section" not in existing_indexes:
            op.create_index(
                "ix_qc_proposal_section", "quarantined_citations", ["proposal_id", "section_key"]
            )
        if "ix_qc_audit_run" not in existing_indexes:
            op.create_index("ix_qc_audit_run", "quarantined_citations", ["audit_run_id"])
        if "ix_qc_created_at" not in existing_indexes:
            op.create_index("ix_qc_created_at", "quarantined_citations", ["created_at"])
        return

    op.create_table(
        "quarantined_citations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "proposal_id",
            sa.Integer(),
            sa.ForeignKey("proposals.id"),
            nullable=False,
        ),
        sa.Column("section_key", sa.String(50), nullable=False),
        sa.Column("ref_index", sa.Integer(), nullable=False),
        sa.Column("audit_run_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_qc_proposal_section",
        "quarantined_citations",
        ["proposal_id", "section_key"],
    )
    op.create_index(
        "ix_qc_audit_run",
        "quarantined_citations",
        ["audit_run_id"],
    )
    op.create_index(
        "ix_qc_created_at",
        "quarantined_citations",
        ["created_at"],
    )


def downgrade() -> None:
    # Guard symmetric to upgrade(): table may have been created by create_all().
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)
    if not inspector.has_table("quarantined_citations"):
        return
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("quarantined_citations")}
    if "ix_qc_created_at" in existing_indexes:
        op.drop_index("ix_qc_created_at", table_name="quarantined_citations")
    if "ix_qc_audit_run" in existing_indexes:
        op.drop_index("ix_qc_audit_run", table_name="quarantined_citations")
    if "ix_qc_proposal_section" in existing_indexes:
        op.drop_index("ix_qc_proposal_section", table_name="quarantined_citations")
    op.drop_table("quarantined_citations")
