"""Operator capability CLI commands (P0.4A1.8).

Commands:
  erock capability verify
      Run a fresh dual-probe capability check. Creates check (binding on
      pass, no binding on fail). Prints CheckPublication. Exit 0 on pass,
      1 on fail.

  erock capability status
      Derive the current capability posture from the check ledger.
      Requires the current runtime fingerprint (recomputed from settings).

  erock capability recover-stale
      Run stale-check lease recovery. Prints count abandoned.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from backend.pipeline.capability.capability_check_lifecycle import (
    recover_stale_running_checks,
)
from backend.pipeline.capability.capability_check_service import run_capability_check
from backend.pipeline.capability.capability_identity import (
    compute_runtime_config_fingerprint,
)
from backend.pipeline.capability.capability_status import derive_capability_status

console = Console()
capability_app = typer.Typer(name="capability", no_args_is_help=True)


def _get_session_factory():
    """Build a session factory from the database engine."""
    from backend.db.database import _get_engine
    from sqlalchemy.orm import sessionmaker

    engine = _get_engine()
    return sessionmaker(bind=engine, expire_on_commit=False)


def _build_adapter_and_config():
    """Build the governed adapter and effective config from settings.

    This is the same composition path as vector_runtime, but without
    requiring a verified runtime — the probe itself produces the check.
    """
    from backend.config import get_settings
    from backend.pipeline.knowledge.embedding_providers import (
        create_embedding_provider,
    )
    from backend.pipeline.knowledge.embedding_service import EmbeddingService
    from backend.pipeline.knowledge.embedding_configuration import (
        EmbeddingAdapterCapabilitySnapshot,
        EmbeddingProfileSnapshot,
        EmbeddingRuntimeSettingsSnapshot,
        resolve_effective_embedding_configuration,
    )
    from backend.pipeline.governed_embedding_adapter import GovernedEmbeddingAdapter
    from backend.pipeline.vector_contracts import EMBEDDING_PROFILE_V1
    from backend.db.database import _get_engine
    from sqlalchemy import select
    from backend.db.models import EmbeddingProfile
    from sqlalchemy.orm import sessionmaker

    settings = get_settings()

    # Build a throwaway EmbeddingService to read dimension
    provider = create_embedding_provider(
        provider_name=settings.embedding_provider,
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
        base_url=getattr(settings, "ollama_base_url", None),
        dimension=settings.embedding_dimension or None,
    )
    emb_service = EmbeddingService(provider)
    dimension = emb_service.dimension

    # Build settings snapshot
    from backend.pipeline.knowledge.embedding_configuration import (
        EmbeddingRuntimeSettingsSnapshot,
    )

    endpoint = getattr(settings, "embedding_base_url", None) or getattr(
        settings, "openai_base_url", None
    )

    settings_snapshot = EmbeddingRuntimeSettingsSnapshot(
        provider_kind=settings.embedding_provider,
        requested_model=settings.embedding_model,
        expected_dimension=dimension,
        declared_normalization_policy="none",
        document_task=None,
        query_task=None,
        endpoint=endpoint,
        configured_deployment_id=None,
        deployment_is_explicitly_pinned=False,
    )

    # Resolve profile ID
    from backend.pipeline.vector_indexer import resolve_profile_id

    profile_id = resolve_profile_id(
        provider=settings.embedding_provider,
        model_identifier=settings.embedding_model,
        dimension=dimension,
        normalization_policy="none",
        chunking_schema_version="chunk_v1",
    )

    # Load profile from DB
    engine = _get_engine()
    sf = sessionmaker(bind=engine, expire_on_commit=False)
    with sf() as session:
        profile_row = session.execute(
            select(EmbeddingProfile).where(
                EmbeddingProfile.profile_id == profile_id
            )
        ).scalar_one_or_none()

        if profile_row is None:
            console.print(
                f"[red]Embedding profile {profile_id[:16]}... is not registered.[/red]\n"
                f"Run an ingestion pipeline first to register the profile."
            )
            raise typer.Exit(1)

        profile_snapshot = EmbeddingProfileSnapshot(
            embedding_profile_id=profile_row.profile_id,
            profile_schema_version=profile_row.profile_schema_version,
            provider_kind=profile_row.provider,
            model_identifier=profile_row.model_identifier,
            dimension=profile_row.dimension,
            normalization_policy=profile_row.normalization_policy,
            document_task=None,
            query_task=None,
            verification_status=profile_row.verification_status,
        )

    adapter_snapshot = EmbeddingAdapterCapabilitySnapshot(
        provider_adapter_contract_version="openai_v1",
        governed_adapter_contract_version="governed_v1",
        implemented_postprocessing_policy="none",
        supports_document_embedding=True,
        supports_query_embedding=True,
    )

    effective_config = resolve_effective_embedding_configuration(
        settings=settings_snapshot,
        profile=profile_snapshot,
        adapter=adapter_snapshot,
    )

    # Build the governed adapter
    governed_adapter = GovernedEmbeddingAdapter(
        embedding_service=emb_service,
        provider_kind=effective_config.provider_kind,
        requested_model=effective_config.requested_model,
        configured_dimension=effective_config.expected_dimension,
    )

    return governed_adapter, effective_config, sf


@capability_app.command("verify")
def verify_cmd():
    """Run a fresh capability check against the current provider."""
    try:
        adapter, config, sf = _build_adapter_and_config()
    except Exception as e:
        console.print(f"[red]Failed to build adapter/config:[/red] {e}")
        raise typer.Exit(1)

    console.print("[dim]Running capability dual-probe...[/dim]")

    pub = asyncio.run(
        run_capability_check(sf, adapter, config, check_ttl_seconds=3600)
    )

    table = Table(title="Capability Check Result")
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("check_id", pub.check_id[:32] + "...")
    table.add_row("status", pub.status)
    table.add_row("binding_id", (pub.binding_id[:32] + "...") if pub.binding_id else "(none)")
    if pub.expires_at:
        table.add_row("expires_at", pub.expires_at.isoformat())
    if pub.failure_code:
        table.add_row("failure_code", pub.failure_code)
    console.print(table)

    if pub.status != "passed":
        raise typer.Exit(1)


@capability_app.command("status")
def status_cmd():
    """Show the current capability posture."""
    try:
        adapter, config, sf = _build_adapter_and_config()
    except Exception as e:
        console.print(f"[red]Failed to build config:[/red] {e}")
        raise typer.Exit(1)

    fingerprint = compute_runtime_config_fingerprint(config)

    with sf() as session:
        status = derive_capability_status(
            session,
            embedding_profile_id=config.embedding_profile_id,
            current_runtime_config_fingerprint=fingerprint,
        )

    table = Table(title="Capability Status")
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("derived_status", status.derived_status)
    table.add_row("profile_id", status.embedding_profile_id[:32] + "...")
    table.add_row("fingerprint", (status.runtime_config_fingerprint or "")[:32] + "...")
    if status.latest_check_id:
        table.add_row("latest_check_id", status.latest_check_id[:32] + "...")
        table.add_row("latest_check_status", status.latest_check_status or "")
    if status.latest_check_binding_id:
        table.add_row("binding_id", status.latest_check_binding_id[:32] + "...")
    if status.latest_check_expires_at:
        table.add_row("expires_at", status.latest_check_expires_at.isoformat())
    console.print(table)


@capability_app.command("recover-stale")
def recover_stale_cmd():
    """Abandon checks whose lease has expired."""
    sf = _get_session_factory()
    count = recover_stale_running_checks(sf)

    if count == 0:
        console.print("[green]No stale running checks found.[/green]")
    else:
        console.print(f"[yellow]Recovered {count} stale running check(s) → abandoned.[/yellow]")


# ── A2.8: Cutover operator commands ──────────────────────────────────


@capability_app.command("inspect")
def inspect_cmd(
    profile_id: str = typer.Option(..., help="Embedding profile ID"),
    purpose: str = typer.Option("paper", help="Embedding purpose"),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable output"),
):
    """Inspect the unified lifecycle posture for a profile."""
    from backend.pipeline.capability.lifecycle_service import CapabilityLifecycleService

    sf = _get_session_factory()
    svc = CapabilityLifecycleService(sf)
    posture = svc.inspect(
        embedding_profile_id=profile_id,
        embedding_purpose=purpose,
    )

    if json_output:
        import json as _json
        console.print_json(_json.dumps({
            "operator_report_schema_version": "v1",
            "embedding_profile_id": posture.embedding_profile_id,
            "embedding_purpose": posture.embedding_purpose,
            "readiness_phase": posture.readiness_phase,
            "capability_health_status": posture.capability_health_status,
            "binding_id": posture.binding_id,
            "model_resolution_posture": posture.model_resolution_posture,
            "persistent_activation_eligible": posture.persistent_activation_eligible,
            "active_binding_id": posture.active_binding_id,
            "open_cutover_id": posture.open_cutover_id,
            "cutover_status": posture.cutover_status,
            "source_item_count": posture.source_item_count,
            "indexed_item_count": posture.indexed_item_count,
            "failed_item_count": posture.failed_item_count,
            "write_guard_status": posture.write_guard_status,
            "blocker_codes": list(posture.blocker_codes),
            "next_actions": list(posture.next_actions),
        }))
        return

    table = Table(title=f"Lifecycle Posture — {profile_id[:16]}...")
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("readiness_phase", posture.readiness_phase)
    table.add_row("capability_health_status", posture.capability_health_status)
    table.add_row("binding_id", (posture.binding_id[:32] + "...") if posture.binding_id else "(none)")
    table.add_row("model_resolution_posture", posture.model_resolution_posture or "(none)")
    table.add_row("persistent_activation_eligible", str(posture.persistent_activation_eligible))
    table.add_row("active_binding_id", (posture.active_binding_id[:32] + "...") if posture.active_binding_id else "(none)")
    table.add_row("open_cutover_id", (posture.open_cutover_id[:32] + "...") if posture.open_cutover_id else "(none)")
    table.add_row("cutover_status", posture.cutover_status or "(none)")
    table.add_row("write_guard_status", posture.write_guard_status)
    if posture.blocker_codes:
        table.add_row("blocker_codes", ", ".join(posture.blocker_codes))
    if posture.next_actions:
        table.add_row("next_actions", "; ".join(posture.next_actions))
    console.print(table)


@capability_app.command("cutover-abort")
def cutover_abort_cmd(
    cutover_id: str = typer.Option(..., help="Cutover ID to abort"),
    profile_id: str = typer.Option(..., help="Embedding profile ID"),
):
    """Abort a cutover before activation."""
    from backend.pipeline.capability.lifecycle_service import (
        CapabilityLifecycleService,
        LifecycleError,
    )

    sf = _get_session_factory()
    svc = CapabilityLifecycleService(sf)

    try:
        result = svc.abort_cutover(
            cutover_id=cutover_id,
            embedding_profile_id=profile_id,
        )
        console.print(f"[green]Cutover aborted:[/green] {result.cutover_id[:32]}...")
        console.print(f"[green]Activation rejected:[/green] {result.activation_id[:32] or '(none)'}")
        console.print(f"[green]Guard released:[/green] {result.guard_released}")
    except LifecycleError as e:
        console.print(f"[red]Abort failed:[/red] {e.code}: {e.detail}")
        raise typer.Exit(3)


@capability_app.command("cutover-create")
def cutover_create_cmd(
    binding_id: str = typer.Option(..., help="Target capability binding ID"),
    profile_id: str = typer.Option(..., help="Embedding profile ID"),
    purpose: str = typer.Option("paper", help="Embedding purpose"),
):
    """Create a cutover for a target binding."""
    from backend.pipeline.capability.lifecycle_service import CapabilityLifecycleService

    sf = _get_session_factory()
    svc = CapabilityLifecycleService(sf)

    result = svc.create_cutover(
        embedding_profile_id=profile_id,
        embedding_purpose=purpose,
        target_binding_id=binding_id,
    )

    if result.created:
        console.print(f"[green]Cutover created:[/green] {result.cutover_id[:32]}...")
        console.print(f"[green]Candidate activation:[/green] {result.activation_id[:32]}...")
        console.print("[dim]Run 'erock capability cutover-run' to snapshot and regenerate.[/dim]")
    else:
        console.print(f"[yellow]Existing open cutover returned:[/yellow] {result.cutover_id[:32]}...")
        console.print(f"[yellow]Activation:[/yellow] {result.activation_id[:32]}...")


@capability_app.command("cutover-status")
def cutover_status_cmd(
    cutover_id: str = typer.Option(..., help="Cutover ID"),
):
    """Show cutover status."""
    from backend.db.models import EmbeddingBindingCutover

    sf = _get_session_factory()
    with sf() as session:
        cutover = session.execute(
            select(EmbeddingBindingCutover).where(
                EmbeddingBindingCutover.cutover_id == cutover_id
            )
        ).scalar_one_or_none()

        if cutover is None:
            console.print(f"[red]Cutover {cutover_id[:16]}... not found.[/red]")
            raise typer.Exit(1)

        table = Table(title=f"Cutover {cutover_id[:16]}...")
        table.add_column("Field", style="cyan")
        table.add_column("Value")
        table.add_row("status", cutover.status)
        table.add_row("profile", cutover.embedding_profile_id[:32] + "...")
        table.add_row("target_binding", cutover.target_binding_id[:32] + "...")
        table.add_row("source_count", str(cutover.source_item_count))
        table.add_row("indexed", str(cutover.target_indexed_count))
        table.add_row("failed", str(cutover.target_failed_count))
        if cutover.sealed_at:
            table.add_row("sealed_at", cutover.sealed_at.isoformat())
        if cutover.activated_at:
            table.add_row("activated_at", cutover.activated_at.isoformat())
        console.print(table)


@capability_app.command("cutover-seal")
def cutover_seal_cmd(
    cutover_id: str = typer.Option(..., help="Cutover ID"),
    profile_id: str = typer.Option(..., help="Embedding profile ID"),
):
    """Seal a cutover (freeze writes, verify no drift)."""
    from backend.pipeline.capability.activation_service import seal_cutover

    sf = _get_session_factory()
    sealed, reason = seal_cutover(
        sf, cutover_id=cutover_id,
        embedding_profile_id=profile_id,
    )

    if sealed:
        console.print(f"[green]Cutover {cutover_id[:16]}... sealed.[/green]")
    else:
        console.print(f"[red]Seal failed:[/red] {reason}")
        raise typer.Exit(1)


@capability_app.command("activate-binding")
def activate_binding_cmd(
    cutover_id: str = typer.Option(..., help="Cutover ID"),
    profile_id: str = typer.Option(..., help="Embedding profile ID"),
    binding_id: str = typer.Option(..., help="Target binding ID"),
    activation_id: str = typer.Option(..., help="Candidate activation ID"),
):
    """Execute the atomic activation transaction."""
    from backend.pipeline.capability.activation_service import activate_binding, ActivationError

    sf = _get_session_factory()
    try:
        result = activate_binding(
            sf,
            cutover_id=cutover_id,
            embedding_profile_id=profile_id,
            target_binding_id=binding_id,
            candidate_activation_id=activation_id,
        )
        if result.success:
            console.print(f"[green]Binding activated:[/green] {binding_id[:32]}...")
        else:
            console.print(f"[red]Activation failed:[/red] {result.failure_code}")
            raise typer.Exit(1)
    except ActivationError as e:
        console.print(f"[red]Activation error:[/red] {e.code}: {e.detail}")
        raise typer.Exit(1)


@capability_app.command("active-binding")
def active_binding_cmd(
    profile_id: str = typer.Option(..., help="Embedding profile ID"),
):
    """Show the current active binding for a profile."""
    from backend.pipeline.capability.capability_bound_retrieval import (
        resolve_retrieval_binding_context,
    )

    sf = _get_session_factory()
    with sf() as session:
        ctx = resolve_retrieval_binding_context(session, profile_id)

    table = Table(title="Active Binding")
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("eligibility_contract", ctx.vector_eligibility_contract_version)
    if ctx.active_binding_id:
        table.add_row("active_binding", ctx.active_binding_id[:32] + "...")
        table.add_row("activation_id", (ctx.activation_id or "")[:32] + "...")
        table.add_row("generation", str(ctx.activation_generation))
    else:
        table.add_row("active_binding", "(none — pre-capability)")
    console.print(table)
