"""Central provenance gate: routes runs based on their immutable contract.

P0.2.7: Every run explicitly enters either ``provenance_v1`` (governed) or
``pre_provenance`` (reasoned legacy). This module loads the durable contract
and selects execution mode. No lifecycle or resume caller may independently
infer provenance mode from context-truthiness, candidate counts, or
checkpoint shape.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ProvenanceContractError(Exception):
    """A provenance_v1 run violates the governed contract."""


class MixedProvenanceModeError(Exception):
    """Legacy run carries governed context, or vice versa."""


# ── Contracts ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RunProvenanceContract:
    """Loaded durable provenance contract for a run."""

    run_id: int
    provenance_version: str
    legacy_reason: str | None
    reconciliation_status: str | None
    execution_posture: str | None


@dataclass(frozen=True)
class RunProvenancePosture:
    """Derived operator-facing provenance posture."""

    provenance_version: str
    posture: Literal[
        "legacy_unenforced",
        "pending",
        "blocked",
        "failed",
        "complete",
        "contract_error",
    ]
    reconciliation_status: str | None
    execution_posture: str | None
    legacy_reason: str | None


# ── Contract loading ─────────────────────────────────────────────────


def load_run_provenance_contract(
    session: Session, run_id: int,
) -> RunProvenanceContract:
    """Load the durable provenance contract from the database."""
    from backend.db.models import PipelineRun, RunSearchReconciliation

    run = session.execute(
        select(PipelineRun).where(PipelineRun.id == run_id)
    ).scalar_one_or_none()

    if run is None:
        raise ProvenanceContractError(f"PipelineRun {run_id} not found")

    rsr = session.execute(
        select(RunSearchReconciliation).where(RunSearchReconciliation.run_id == run_id)
    ).scalar_one_or_none()

    return RunProvenanceContract(
        run_id=run_id,
        provenance_version=run.provenance_version,
        legacy_reason=run.legacy_provenance_reason,
        reconciliation_status=rsr.status if rsr else None,
        execution_posture=rsr.execution_posture if rsr else None,
    )


def select_run_execution_mode(
    contract: RunProvenanceContract,
) -> Literal["governed", "legacy", "legacy_read_only"]:
    """Select execution mode from the durable contract.

    - ``provenance_v1`` → ``governed``
    - ``pre_provenance`` + ``legacy_checkpoint``/``explicit_legacy_mode`` → ``legacy``
    - ``pre_provenance`` + ``pre_gating_run``/``imported_legacy_run`` → ``legacy_read_only``
    """
    if contract.provenance_version == "provenance_v1":
        return "governed"

    if contract.provenance_version == "pre_provenance":
        if contract.legacy_reason in ("legacy_checkpoint", "explicit_legacy_mode"):
            return "legacy"
        # pre_gating_run and imported_legacy_run are read-only
        return "legacy_read_only"

    raise ProvenanceContractError(
        f"unknown provenance_version {contract.provenance_version!r} for run {contract.run_id}"
    )


def derive_run_provenance_posture(
    contract: RunProvenanceContract,
) -> RunProvenancePosture:
    """Derive the operator-facing posture from the durable contract."""
    if contract.provenance_version == "pre_provenance":
        return RunProvenancePosture(
            provenance_version="pre_provenance",
            posture="legacy_unenforced",
            reconciliation_status=None,
            execution_posture=None,
            legacy_reason=contract.legacy_reason,
        )

    # provenance_v1
    if contract.reconciliation_status is None:
        return RunProvenancePosture(
            provenance_version="provenance_v1",
            posture="contract_error",
            reconciliation_status=None,
            execution_posture=None,
            legacy_reason=None,
        )

    posture_map = {
        "pending": "pending",
        "blocked": "blocked",
        "failed": "failed",
        "reconciled": "complete",
    }

    return RunProvenancePosture(
        provenance_version="provenance_v1",
        posture=posture_map.get(
            contract.reconciliation_status, "contract_error",
        ),
        reconciliation_status=contract.reconciliation_status,
        execution_posture=contract.execution_posture,
        legacy_reason=None,
    )


# ── Run creation ─────────────────────────────────────────────────────


def create_governed_run_record(
    session: Session,
    *,
    run_id_str: str | None = None,
    domain: str = "AI/NLP",
    status: str = "running",
    config_json: str = "{}",
    **extra_fields,
) -> "PipelineRun":
    """Create a provenance_v1 run and its pending reconciliation ledger.

    Atomic: failure leaves neither record. The reconciliation ledger is
    created in the same transaction so a governed run always has one.
    """
    from backend.db.models import PipelineRun, RunSearchReconciliation

    run = PipelineRun(
        run_id_str=run_id_str,
        domain=domain,
        status=status,
        config_json=config_json,
        stages_completed="[]",
        provenance_version="provenance_v1",
        legacy_provenance_reason=None,
        **extra_fields,
    )
    session.add(run)
    session.flush()  # get run.id

    rsr = RunSearchReconciliation(
        run_id=run.id,
        reconciliation_schema_version="run_reconciliation_v1",
        status="pending",
        reconciliation_attempt_count=0,
    )
    session.add(rsr)
    session.flush()

    return run


def create_legacy_run_record(
    session: Session,
    *,
    legacy_reason: Literal[
        "legacy_checkpoint", "explicit_legacy_mode", "imported_legacy_run",
    ],
    run_id_str: str | None = None,
    domain: str = "AI/NLP",
    status: str = "running",
    config_json: str = "{}",
    **extra_fields,
) -> "PipelineRun":
    """Create a pre_provenance run with an explicit legacy reason.

    No RunSearchReconciliation is created. The legacy reason must be one
    of the runtime-allowed values (not ``pre_gating_run``, which is
    migration-only).
    """
    if legacy_reason == "pre_gating_run":
        raise ValueError("pre_gating_run is migration-only; use explicit_legacy_mode")

    from backend.db.models import PipelineRun

    run = PipelineRun(
        run_id_str=run_id_str,
        domain=domain,
        status=status,
        config_json=config_json,
        stages_completed="[]",
        provenance_version="pre_provenance",
        legacy_provenance_reason=legacy_reason,
        **extra_fields,
    )
    session.add(run)
    session.flush()

    return run
