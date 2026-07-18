"""Migration: capability ledger — check-first schema (P0.4A1).

Creates two tables:

  embedding_capability_bindings
    Stable resolved semantic-space identity. Created ONLY after a
    successful dual-probe proves the runtime matches the declared
    contract. Immutable once created.

  embedding_capability_checks
    Timestamped runtime-health evidence. Check-first lifecycle: a
    pending check is created BEFORE any probe. The binding_id column
    is NULL while the check is pending, running, or failed, and is set
    ONLY when the probe passes and a binding is resolved.

Frozen rule (P0.4A1 directive):
    A failed or incomplete probe may create check evidence, but it may
    never create a resolved capability binding.

No embedding_profile_binding_activations table is created in A1.
Binding activation/cutover belongs to the following macro-wave.

Revision ID: 027
Revises: 026
"""

from alembic import op
import sqlalchemy as sa

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    # ── 1. embedding_capability_bindings ──────────────────────────
    # Created first because embedding_capability_checks has a FK to it.
    if not inspector.has_table("embedding_capability_bindings"):
        op.create_table(
            "embedding_capability_bindings",
            sa.Column("binding_id", sa.String(64), primary_key=True),
            sa.Column(
                "embedding_profile_id",
                sa.String(64),
                sa.ForeignKey("embedding_profiles.profile_id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("provider_kind", sa.String(80), nullable=False),
            sa.Column("resolved_model", sa.String(255), nullable=False),
            sa.Column("provider_revision", sa.String(255), nullable=True),
            sa.Column("model_resolution_posture", sa.String(40), nullable=False),
            sa.Column("resolved_document_task", sa.String(60), nullable=True),
            sa.Column("resolved_query_task", sa.String(60), nullable=True),
            sa.Column("resolved_dimension", sa.Integer, nullable=False),
            sa.Column("resolved_normalization", sa.String(80), nullable=False),
            sa.Column(
                "postprocessing_contract_version", sa.String(60), nullable=False
            ),
            sa.Column("resolved_endpoint_identity", sa.String(512), nullable=False),
            sa.Column("resolved_deployment_id", sa.String(255), nullable=True),
            sa.Column("profile_schema_version", sa.String(30), nullable=False),
            sa.Column(
                "provider_adapter_contract_version", sa.String(60), nullable=False
            ),
            sa.Column(
                "governed_adapter_contract_version", sa.String(60), nullable=False
            ),
            sa.Column(
                "resolution_classifier_version", sa.String(60), nullable=False
            ),
            sa.Column("binding_schema_version", sa.String(30), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime,
                nullable=False,
                server_default=sa.func.current_timestamp(),
            ),
            sa.CheckConstraint(
                "binding_schema_version = 'capability_binding_v1'",
                name="ck_ecb_schema_version",
            ),
            sa.CheckConstraint(
                "resolved_dimension > 0", name="ck_ecb_dimension_positive"
            ),
            sa.CheckConstraint(
                "length(binding_id) = 64 AND binding_id = lower(binding_id)",
                name="ck_ecb_binding_id_format",
            ),
            sa.CheckConstraint(
                "length(embedding_profile_id) = 64 "
                "AND embedding_profile_id = lower(embedding_profile_id)",
                name="ck_ecb_profile_id_format",
            ),
        )
        op.create_index(
            "ix_ecb_profile_id", "embedding_capability_bindings",
            ["embedding_profile_id"],
        )

    # ── 2. embedding_capability_checks ────────────────────────────
    if not inspector.has_table("embedding_capability_checks"):
        op.create_table(
            "embedding_capability_checks",
            sa.Column("check_id", sa.String(64), primary_key=True),
            sa.Column(
                "embedding_profile_id",
                sa.String(64),
                sa.ForeignKey("embedding_profiles.profile_id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "binding_id",
                sa.String(64),
                sa.ForeignKey(
                    "embedding_capability_bindings.binding_id", ondelete="RESTRICT"
                ),
                nullable=True,
            ),
            sa.Column(
                "runtime_config_fingerprint", sa.String(64), nullable=False
            ),
            sa.Column("probe_suite_version", sa.String(30), nullable=False),
            sa.Column("check_status", sa.String(20), nullable=False),
            sa.Column("probe_kind", sa.String(20), nullable=False),
            sa.Column(
                "attempt_count", sa.Integer, nullable=False, server_default="0"
            ),
            sa.Column(
                "provider_request_count",
                sa.Integer,
                nullable=False,
                server_default="0",
            ),
            sa.Column("claimed_at", sa.DateTime, nullable=True),
            sa.Column("lease_expires_at", sa.DateTime, nullable=True),
            sa.Column("probed_at", sa.DateTime, nullable=True),
            sa.Column("completed_at", sa.DateTime, nullable=True),
            sa.Column("expires_at", sa.DateTime, nullable=True),
            # ── Separate document/query observations ──
            sa.Column("observed_document_dimension", sa.Integer, nullable=True),
            sa.Column("observed_query_dimension", sa.Integer, nullable=True),
            sa.Column("observed_document_norm_min", sa.Float, nullable=True),
            sa.Column("observed_document_norm_max", sa.Float, nullable=True),
            sa.Column("observed_query_norm", sa.Float, nullable=True),
            sa.Column(
                "observed_document_reported_model", sa.String(255), nullable=True
            ),
            sa.Column(
                "observed_query_reported_model", sa.String(255), nullable=True
            ),
            sa.Column(
                "observed_document_provider_revision",
                sa.String(255),
                nullable=True,
            ),
            sa.Column(
                "observed_query_provider_revision", sa.String(255), nullable=True
            ),
            sa.Column(
                "observed_document_evidence_source", sa.String(60), nullable=True
            ),
            sa.Column(
                "observed_query_evidence_source", sa.String(60), nullable=True
            ),
            # ── Failure evidence ──
            sa.Column("failure_category", sa.String(40), nullable=True),
            sa.Column("failure_code", sa.String(80), nullable=True),
            sa.Column("sanitized_error_detail", sa.String(500), nullable=True),
            sa.Column("check_schema_version", sa.String(30), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime,
                nullable=False,
                server_default=sa.func.current_timestamp(),
            ),
            # ── Schema-version literal ──
            sa.CheckConstraint(
                "check_schema_version = 'capability_check_v1'",
                name="ck_ecc_schema_version",
            ),
            # ── Status vocabulary ──
            sa.CheckConstraint(
                "check_status IN ('pending','running','passed','failed',"
                "'cancelled','abandoned')",
                name="ck_ecc_check_status",
            ),
            sa.CheckConstraint(
                "probe_kind IN ('document_probe','query_probe','dual_probe')",
                name="ck_ecc_probe_kind",
            ),
            sa.CheckConstraint(
                "attempt_count >= 0", name="ck_ecc_attempt_count"
            ),
            sa.CheckConstraint(
                "provider_request_count >= 0",
                name="ck_ecc_provider_request_count",
            ),
            # ── Lifecycle completeness (DB-enforced) ──
            sa.CheckConstraint(
                "check_status != 'passed' OR "
                "(binding_id IS NOT NULL AND completed_at IS NOT NULL "
                "AND expires_at IS NOT NULL AND probed_at IS NOT NULL "
                "AND failure_code IS NULL)",
                name="ck_ecc_passed_completeness",
            ),
            sa.CheckConstraint(
                "check_status != 'failed' OR "
                "(completed_at IS NOT NULL AND failure_code IS NOT NULL "
                "AND binding_id IS NULL AND expires_at IS NULL)",
                name="ck_ecc_failed_completeness",
            ),
            sa.CheckConstraint(
                "check_status != 'cancelled' OR "
                "(completed_at IS NOT NULL AND binding_id IS NULL)",
                name="ck_ecc_cancelled_completeness",
            ),
            sa.CheckConstraint(
                "check_status != 'abandoned' OR "
                "(completed_at IS NOT NULL AND binding_id IS NULL)",
                name="ck_ecc_abandoned_completeness",
            ),
            sa.CheckConstraint(
                "check_status != 'running' OR "
                "(claimed_at IS NOT NULL AND lease_expires_at IS NOT NULL "
                "AND completed_at IS NULL)",
                name="ck_ecc_running_completeness",
            ),
            sa.CheckConstraint(
                "check_status != 'pending' OR claimed_at IS NULL",
                name="ck_ecc_pending_completeness",
            ),
            # ── Format checks ──
            sa.CheckConstraint(
                "length(embedding_profile_id) = 64 "
                "AND embedding_profile_id = lower(embedding_profile_id)",
                name="ck_ecc_profile_id_format",
            ),
            sa.CheckConstraint(
                "length(runtime_config_fingerprint) = 64 "
                "AND runtime_config_fingerprint = lower(runtime_config_fingerprint)",
                name="ck_ecc_fingerprint_format",
            ),
        )
        op.create_index(
            "ix_ecc_profile_fingerprint_suite",
            "embedding_capability_checks",
            ["embedding_profile_id", "runtime_config_fingerprint", "probe_suite_version"],
        )
        op.create_index(
            "ix_ecc_binding_id", "embedding_capability_checks", ["binding_id"],
        )
        op.create_index(
            "ix_ecc_lease_expires_at",
            "embedding_capability_checks",
            ["lease_expires_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(bind)

    if inspector.has_table("embedding_capability_checks"):
        # Drop indexes first (wrapped in try/except for idempotency)
        for ix_name in (
            "ix_ecc_profile_fingerprint_suite",
            "ix_ecc_binding_id",
            "ix_ecc_lease_expires_at",
        ):
            try:
                op.drop_index(ix_name, table_name="embedding_capability_checks")
            except Exception:
                pass
        op.drop_table("embedding_capability_checks")

    if inspector.has_table("embedding_capability_bindings"):
        try:
            op.drop_index("ix_ecb_profile_id", table_name="embedding_capability_bindings")
        except Exception:
            pass
        op.drop_table("embedding_capability_bindings")
