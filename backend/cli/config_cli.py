"""P0.5.9: Configuration inspection and validation commands.

  erock config inspect [--field <id>] [--json]
  erock config explain --field <id>
  erock config validate
  erock config coverage
"""

from __future__ import annotations

import json
import typer
from rich.console import Console
from rich.table import Table

from backend.pipeline.config.field_registry import (
    build_registry,
    validate_registry,
)

console = Console()
config_app = typer.Typer(name="config", no_args_is_help=True)


@config_app.command("inspect")
def inspect_cmd(
    field: str = typer.Option(None, "--field", help="Specific field ID to inspect"),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable output"),
):
    """Inspect configuration field(s)."""
    registry = build_registry()

    if field:
        fc = registry.get(field)
        if fc is None:
            console.print(f"[red]Field not found: {field}[/red]")
            raise typer.Exit(4)
        _print_field(fc, json_output)
    else:
        counts = registry.count_by_materiality()
        if json_output:
            console.print_json(json.dumps({
                "total_fields": len(registry.fields),
                "materiality_counts": counts,
                "material_fields": len(registry.material_fields()),
                "credential_fields": len(registry.credential_fields()),
            }))
        else:
            table = Table(title="Configuration Registry Summary")
            table.add_column("Metric", style="cyan")
            table.add_column("Count")
            table.add_row("Total fields", str(len(registry.fields)))
            table.add_row("Material (public)", str(counts.get("public_material", 0)))
            table.add_row("Informational", str(counts.get("public_informational", 0)))
            table.add_row("Internal", str(counts.get("internal", 0)))
            table.add_row("Credentials", str(len(registry.credential_fields())))
            console.print(table)


@config_app.command("explain")
def explain_cmd(
    field: str = typer.Option(..., "--field", help="Field ID to explain"),
):
    """Explain a configuration field's purpose and contracts."""
    registry = build_registry()
    fc = registry.get(field)
    if fc is None:
        console.print(f"[red]Field not found: {field}[/red]")
        raise typer.Exit(4)

    table = Table(title=f"Field: {field}")
    table.add_column("Property", style="cyan")
    table.add_column("Value")
    table.add_row("canonical_path", fc.canonical_path)
    table.add_row("owner", fc.owner)
    table.add_row("materiality", fc.materiality)
    table.add_row("effect_class", fc.effect_class)
    table.add_row("lifecycle_status", fc.lifecycle_status)
    table.add_row("sensitivity", fc.sensitivity)
    table.add_row("declared_default", fc.declared_default[:80])
    table.add_row("consumers", ", ".join(fc.production_consumers) or "(none)")
    table.add_row("effect_contracts", ", ".join(fc.effect_contract_ids) or "(none)")
    table.add_row("evidence_policy", fc.evidence_policy_id)
    console.print(table)


@config_app.command("validate")
def validate_cmd():
    """Validate the configuration registry."""
    registry = build_registry()
    errors = validate_registry(registry)

    if errors:
        console.print(f"[red]{len(errors)} validation error(s):[/red]")
        for e in errors:
            console.print(f"  [red]•[/red] {e}")
        raise typer.Exit(5)
    else:
        console.print(f"[green]Registry valid: {len(registry.fields)} fields, 0 errors.[/green]")


@config_app.command("coverage")
def coverage_cmd():
    """Report configuration coverage statistics."""
    registry = build_registry()
    material = registry.material_fields()

    table = Table(title="Configuration Coverage")
    table.add_column("Metric", style="cyan")
    table.add_column("Count")
    table.add_row("Total fields", str(len(registry.fields)))
    table.add_row("Material fields", str(len(material)))
    table.add_row("With consumers", str(sum(1 for f in material if f.production_consumers)))
    table.add_row("With effect contracts", str(sum(1 for f in material if f.effect_contract_ids)))
    table.add_row("Deprecated", str(len(registry.deprecated_fields())))
    table.add_row("Unsupported", str(len(registry.unsupported_fields())))
    console.print(table)


def _print_field(fc, json_output: bool):
    if json_output:
        console.print_json(json.dumps({
            "field_id": fc.field_id,
            "canonical_path": fc.canonical_path,
            "owner": fc.owner,
            "materiality": fc.materiality,
            "effect_class": fc.effect_class,
            "lifecycle_status": fc.lifecycle_status,
            "sensitivity": fc.sensitivity,
        }, default=str))
    else:
        table = Table(title=f"Field: {fc.field_id}")
        table.add_column("Property", style="cyan")
        table.add_column("Value")
        table.add_row("owner", fc.owner)
        table.add_row("materiality", fc.materiality)
        table.add_row("effect_class", fc.effect_class)
        table.add_row("sensitivity", fc.sensitivity)
        table.add_row("default", fc.declared_default[:80] if fc.declared_default else "(none)")
        console.print(table)
