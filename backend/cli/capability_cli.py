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
