"""Migration: corpus provenance — run-scoped paper ownership.

P0.1: Establishes an auditable relational boundary around each new pipeline
run's corpus. Three new tables:

  search_queries     — logical queries executed during literature search
  run_papers         — membership of a paper in a run's working corpus
  paper_discoveries  — every distinct route through which a paper was found

Plus a provenance_version column on pipeline_runs:
  NOT NULL DEFAULT 'pre_provenance' — prevents ambiguous NULL state.
  Legacy runs are explicitly marked. New governed runs write 'provenance_v1'.

Legacy policy: no historical run_papers or paper_discoveries rows are
fabricated. Existing papers remain canonical bibliographic records.

Revision ID: 014
Revises: 013
"""

from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    # ── 1. Add provenance_version to pipeline_runs ──────────────
    existing_cols = {c["name"] for c in inspector.get_columns("pipeline_runs")}
    if "provenance_version" not in existing_cols:
        op.add_column(
            "pipeline_runs",
            sa.Column(
                "provenance_version",
                sa.String(20),
                nullable=False,
                server_default="pre_provenance",
            ),
        )

    # Belt-and-suspenders: ensure all existing runs are marked
    op.execute(
        "UPDATE pipeline_runs SET provenance_version = 'pre_provenance' "
        "WHERE provenance_version IS NULL OR provenance_version = ''"
    )

    # ── 2. search_queries table ─────────────────────────────────
    if not inspector.has_table("search_queries"):
        op.create_table(
            "search_queries",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "run_id",
                sa.Integer(),
                sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("query_key", sa.String(32), nullable=False),
            sa.Column("query_text", sa.Text(), nullable=False),
            sa.Column("query_type", sa.String(30), nullable=False, server_default="template"),
            sa.Column("generation_origin", sa.String(30), nullable=False, server_default="base"),
            sa.Column("sequence_number", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("source_target", sa.String(50), nullable=True),
            sa.Column("executed_query", sa.Text(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="persisted"),
            sa.Column("executed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("run_id", "query_key", name="uq_search_queries_run_key"),
        )
        op.create_index("ix_search_queries_run_id", "search_queries", ["run_id"])

    # ── 3. run_papers table ─────────────────────────────────────
    if not inspector.has_table("run_papers"):
        op.create_table(
            "run_papers",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "run_id",
                sa.Integer(),
                sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "paper_id",
                sa.Integer(),
                sa.ForeignKey("papers.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("inclusion_origin", sa.String(30), nullable=False, server_default="remote_search"),
            sa.Column("inclusion_status", sa.String(20), nullable=False, server_default="candidate"),
            sa.Column("first_discovered_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("selected_for_downstream", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("selection_stage", sa.String(50), nullable=True),
            sa.Column("relevance_score", sa.Float(), nullable=True),
            sa.Column("exclusion_reason", sa.Text(), nullable=True),
            sa.Column("provenance_schema_version", sa.String(20), nullable=False, server_default="provenance_v1"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("run_id", "paper_id", name="uq_run_papers_run_paper"),
        )
        op.create_index("ix_run_papers_run_id", "run_papers", ["run_id"])
        op.create_index("ix_run_papers_paper_id", "run_papers", ["paper_id"])

    # ── 4. paper_discoveries table ──────────────────────────────
    if not inspector.has_table("paper_discoveries"):
        op.create_table(
            "paper_discoveries",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "run_id",
                sa.Integer(),
                sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "paper_id",
                sa.Integer(),
                sa.ForeignKey("papers.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "search_query_id",
                sa.Integer(),
                sa.ForeignKey("search_queries.id", ondelete="RESTRICT"),
                nullable=True,
            ),
            sa.Column("source", sa.String(50), nullable=False),
            sa.Column("source_record_id", sa.String(256), nullable=True),
            sa.Column("source_rank", sa.Integer(), nullable=True),
            sa.Column("discovery_origin", sa.String(30), nullable=False, server_default="remote_search"),
            sa.Column("retrieved_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("raw_identifier", sa.Text(), nullable=True),
            sa.Column("deduplication_status", sa.String(20), nullable=False, server_default="unique"),
            sa.Column("canonicalization_method", sa.String(30), nullable=True),
            sa.Column("discovery_key", sa.String(32), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("run_id", "discovery_key", name="uq_paper_discoveries_run_key"),
        )
        op.create_index("ix_paper_discoveries_run_paper", "paper_discoveries", ["run_id", "paper_id"])
        op.create_index("ix_paper_discoveries_query", "paper_discoveries", ["search_query_id"])

    # ── 5. Add updated_at onupdate trigger for run_papers ───────
    # SQLite doesn't support ON UPDATE via DDL, but the ORM handles it
    # via onupdate=lambda. For PostgreSQL, the column declaration suffices.
    # No additional DDL needed.


def downgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    if inspector.has_table("paper_discoveries"):
        op.drop_index("ix_paper_discoveries_query", table_name="paper_discoveries")
        op.drop_index("ix_paper_discoveries_run_paper", table_name="paper_discoveries")
        op.drop_table("paper_discoveries")

    if inspector.has_table("run_papers"):
        op.drop_index("ix_run_papers_paper_id", table_name="run_papers")
        op.drop_index("ix_run_papers_run_id", table_name="run_papers")
        op.drop_table("run_papers")

    if inspector.has_table("search_queries"):
        op.drop_index("ix_search_queries_run_id", table_name="search_queries")
        op.drop_table("search_queries")

    # Remove provenance_version column (SQLite batch mode for ALTER)
    existing_cols = {c["name"] for c in inspector.get_columns("pipeline_runs")}
    if "provenance_version" in existing_cols:
        with op.batch_alter_table("pipeline_runs") as batch_op:
            batch_op.drop_column("provenance_version")
