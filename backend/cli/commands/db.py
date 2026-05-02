"""``erock db`` — database migration commands via Alembic.

Provides ``erock db upgrade`` and ``erock db downgrade`` subcommands that
wrap the Alembic migration API so developers don't need to install / run
the ``alembic`` CLI directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console

console = Console()

db_app = typer.Typer(
    name="db",
    help="Database migration commands (Alembic wrapper).",
    no_args_is_help=True,
)


def _alembic_cfg():
    """Build an Alembic Config object pointing at the project alembic.ini."""
    from alembic.config import Config

    # Resolve alembic.ini relative to the project root (where backend/ lives).
    project_root = Path(__file__).resolve().parents[3]
    ini_path = project_root / "alembic.ini"
    if not ini_path.exists():
        console.print(f"[red]alembic.ini not found at {ini_path}[/red]")
        raise typer.Exit(1)

    cfg = Config(str(ini_path))
    return cfg


@db_app.command("upgrade")
def db_upgrade(
    revision: str = typer.Argument("head", help="Target revision (default: head)"),
):
    """Apply database migrations (default: up to head)."""
    from alembic import command

    cfg = _alembic_cfg()
    console.print(f"[bold]Running upgrade to '{revision}'…[/bold]")
    command.upgrade(cfg, revision)
    console.print("[green]Upgrade complete.[/green]")


@db_app.command("downgrade")
def db_downgrade(
    revision: str = typer.Argument("-1", help="Target revision (default: -1)"),
):
    """Revert database migrations (default: one step back)."""
    from alembic import command

    cfg = _alembic_cfg()
    console.print(f"[bold]Running downgrade to '{revision}'…[/bold]")
    command.downgrade(cfg, revision)
    console.print("[green]Downgrade complete.[/green]")


@db_app.command("history")
def db_history():
    """Show migration history."""
    from alembic import command

    cfg = _alembic_cfg()
    command.history(cfg)


@db_app.command("current")
def db_current():
    """Show current migration revision."""
    from alembic import command

    cfg = _alembic_cfg()
    command.current(cfg)
