"""Migration: capability-aware vector and retrieval evidence (P0.4A2.1).

Migration A: adds capability binding/check columns to
``vector_index_records`` and ``vector_retrieval_events``, and relaxes
the ``index_schema_version`` CHECK to allow both ``vector_index_v1``
and ``vector_index_v2``.

Historical rows remain ``pre_capability_v0`` with NULL capability
fields — no binding backfill.

Revision ID: 028
Revises: 027
"""

from alembic import op
import sqlalchemy as sa

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    # ── 1. vector_index_records: add capability columns ────────────
    existing_vir_cols = {c["name"] for c in inspector.get_columns("vector_index_records")}

    if "embedding_contract_version" not in existing_vir_cols:
        with op.batch_alter_table("vector_index_records", recreate="always") as batch_op:
            batch_op.add_column(
                sa.Column("embedding_contract_version", sa.String(30),
                          nullable=True)
            )

    if "capability_binding_id" not in existing_vir_cols:
        with op.batch_alter_table("vector_index_records", recreate="always") as batch_op:
            batch_op.add_column(
                sa.Column("capability_binding_id", sa.String(64),
                          nullable=True)
            )

    if "generation_capability_check_id" not in existing_vir_cols:
        with op.batch_alter_table("vector_index_records", recreate="always") as batch_op:
            batch_op.add_column(
                sa.Column("generation_capability_check_id", sa.String(64),
                          nullable=True)
            )

    # ── 2. Backfill historical rows: pre_capability_v0 ────────────
    # Existing v1 rows get the pre-capability contract. No binding backfill.
    op.execute(
        "UPDATE vector_index_records SET embedding_contract_version = 'pre_capability_v0' "
        "WHERE embedding_contract_version IS NULL"
    )

    # ── 3. Make embedding_contract_version NOT NULL after backfill ──
    with op.batch_alter_table("vector_index_records", recreate="always") as batch_op:
        batch_op.alter_column(
            "embedding_contract_version",
            existing_type=sa.String(30),
            nullable=False,
        )

    # ── 4. Relax index_schema_version CHECK to allow v1 and v2 ────
    # Drop old CHECK, add new one that allows both versions.
    with op.batch_alter_table("vector_index_records", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_vir_index_schema", type_="check")
        batch_op.create_check_constraint(
            "ck_vir_index_schema",
            "index_schema_version IN ('vector_index_v1', 'vector_index_v2')",
        )

    # ── 5. Add capability contract CHECK (v1+v0, v2+v1 only) ─────
    with op.batch_alter_table("vector_index_records", recreate="always") as batch_op:
        batch_op.create_check_constraint(
            "ck_vir_capability_contract",
            "(index_schema_version = 'vector_index_v1' "
            "AND embedding_contract_version = 'pre_capability_v0' "
            "AND capability_binding_id IS NULL "
            "AND generation_capability_check_id IS NULL) "
            "OR (index_schema_version = 'vector_index_v2' "
            "AND embedding_contract_version = 'capability_v1' "
            "AND capability_binding_id IS NOT NULL "
            "AND (index_status != 'indexed' OR generation_capability_check_id IS NOT NULL))",
        )

    # ── 6. Index for capability lookups ───────────────────────────
    existing_vir_indexes = {ix["name"] for ix in inspector.get_indexes("vector_index_records")}
    if "ix_vir_capability_binding" not in existing_vir_indexes:
        op.create_index(
            "ix_vir_capability_binding",
            "vector_index_records",
            ["capability_binding_id"],
        )

    # ── 7. vector_retrieval_events: add capability columns ────────
    existing_vre_cols = {c["name"] for c in inspector.get_columns("vector_retrieval_events")}

    cols_to_add = [
        ("query_embedding_contract_version", sa.String(30)),
        ("vector_eligibility_contract_version", sa.String(30)),
        ("query_capability_binding_id", sa.String(64)),
        ("query_capability_check_id", sa.String(64)),
        ("binding_activation_id", sa.String(64)),
    ]
    for col_name, col_type in cols_to_add:
        if col_name not in existing_vre_cols:
            with op.batch_alter_table("vector_retrieval_events", recreate="always") as batch_op:
                batch_op.add_column(sa.Column(col_name, col_type, nullable=True))

    # ── 8. Backfill historical retrieval rows ─────────────────────
    op.execute(
        "UPDATE vector_retrieval_events SET "
        "query_embedding_contract_version = 'pre_capability_v0', "
        "vector_eligibility_contract_version = 'pre_capability_v0' "
        "WHERE query_embedding_contract_version IS NULL"
    )

    # ── 9. Make contract columns NOT NULL ─────────────────────────
    with op.batch_alter_table("vector_retrieval_events", recreate="always") as batch_op:
        batch_op.alter_column(
            "query_embedding_contract_version",
            existing_type=sa.String(30),
            nullable=False,
        )
        batch_op.alter_column(
            "vector_eligibility_contract_version",
            existing_type=sa.String(30),
            nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    # ── Drop indexes FIRST (before dropping the columns they reference) ──
    existing_vir_indexes = {ix["name"] for ix in inspector.get_indexes("vector_index_records")}
    if "ix_vir_capability_binding" in existing_vir_indexes:
        op.drop_index("ix_vir_capability_binding", table_name="vector_index_records")

    # Restore original CHECK constraint + drop columns in ONE batch operation
    with op.batch_alter_table("vector_index_records", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_vir_capability_contract", type_="check")
        batch_op.drop_constraint("ck_vir_index_schema", type_="check")
        batch_op.create_check_constraint(
            "ck_vir_index_schema",
            "index_schema_version = 'vector_index_v1'",
        )
        # Drop capability columns
        existing_vir_cols = {c["name"] for c in inspector.get_columns("vector_index_records")}
        for col in ("embedding_contract_version", "capability_binding_id",
                    "generation_capability_check_id"):
            if col in existing_vir_cols:
                batch_op.drop_column(col)

    # Drop added columns from vector_retrieval_events
    existing_vre_cols = {c["name"] for c in inspector.get_columns("vector_retrieval_events")}
    for col in ("query_embedding_contract_version", "vector_eligibility_contract_version",
                "query_capability_binding_id", "query_capability_check_id",
                "binding_activation_id"):
        if col in existing_vre_cols:
            with op.batch_alter_table("vector_retrieval_events", recreate="always") as batch_op:
                batch_op.drop_column(col)
