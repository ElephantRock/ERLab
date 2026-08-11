"""``erock dev`` — start both backend and frontend dev servers concurrently.

Launches uvicorn (port 8000) and npm run dev (port 3000) as managed
subprocesses.  Streams stdout/stderr with coloured [BACKEND] / [FRONTEND]
prefixes, detects port conflicts, and ensures both child processes are
terminated on Ctrl+C or any exit path (AR-01).
"""

from __future__ import annotations

import socket
import subprocess
import sys
import threading
from pathlib import Path

import typer
from rich.console import Console

console = Console()

BACKEND_PORT = 8000
FRONTEND_PORT = 3000

BACKEND_HOST = "0.0.0.0"

# ANSI colours for log prefixes
BACKEND_PREFIX = "\033[94m[BACKEND]\033[0m"   # blue
FRONTEND_PREFIX = "\033[92m[FRONTEND]\033[0m"  # green

# ── Helpers ──────────────────────────────────────────────────────────


def _port_in_use(port: int) -> bool:
    """Return *True* when *port* is already bound on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _stream_lines(
    process: subprocess.Popen,
    prefix: str,
    stop_event: threading.Event,
) -> None:
    """Read lines from *process* stdout+stderr and print with *prefix*."""
    import io

    stream = process.stdout
    if stream is None:
        return
    # Wrap binary stream for text reading; don't close the underlying fd
    text_stream = io.TextIOWrapper(stream, encoding="utf-8", errors="replace", write_through=True)
    try:
        while not stop_event.is_set():
            line = text_stream.readline()
            if not line:
                break
            print(f"{prefix} {line}", end="", flush=True)
    finally:
        pass  # don't close text_stream — the Popen owns the fd


def _build_backend_cmd() -> list[str]:
    """Return the uvicorn subprocess argument list."""
    return [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.api.app:app",
        "--host", BACKEND_HOST,
        "--port", str(BACKEND_PORT),
        "--reload",
    ]


def _build_frontend_cmd() -> list[str]:
    """Return the npm frontend subprocess argument list."""
    return [
        "npm",
        "run",
        "dev",
    ]


# ── Main command ─────────────────────────────────────────────────────


def dev_command() -> None:
    """Start backend and frontend development servers concurrently.

    * Launches uvicorn on port 8000 and ``npm run dev`` on port 3000.
    * Streams combined output with [BACKEND] / [FRONTEND] prefixes.
    * Detects port conflicts before starting (HB-02).
    * Cleans up both child processes on Ctrl+C (AR-01).
    """

    # ── Port conflict detection (HB-02) ──────────────────────────
    conflicts: list[int] = []
    for port in (BACKEND_PORT, FRONTEND_PORT):
        if _port_in_use(port):
            conflicts.append(port)

    if conflicts:
        parts = ", ".join(f"port {p}" for p in conflicts)
        console.print(
            f"[red]Error:[/red] {parts} already in use.\n"
            f"Free the port(s) before running [bold]erock dev[/bold]."
        )
        raise typer.Exit(1)

    # ── Resolve the frontend directory ────────────────────────────
    # Assume the command is run from the project root (where backend/ lives).
    project_root = Path.cwd()
    frontend_dir = project_root / "frontend"

    # ── Launch subprocesses ───────────────────────────────────────
    backend_proc: subprocess.Popen | None = None
    frontend_proc: subprocess.Popen | None = None
    stop_event = threading.Event()

    try:
        backend_proc = subprocess.Popen(
            _build_backend_cmd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(project_root),
        )

        frontend_proc = subprocess.Popen(
            _build_frontend_cmd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(frontend_dir),
        )

        # Print startup URLs
        console.print(
            f"\n[bold green]Starting development servers…[/bold green]\n"
            f"  Backend:   [bold]http://localhost:{BACKEND_PORT}[/bold]\n"
            f"  Frontend:  [bold]http://localhost:{FRONTEND_PORT}[/bold]\n"
        )

        # ── Stream output via threads ─────────────────────────────
        bt = threading.Thread(
            target=_stream_lines,
            args=(backend_proc, BACKEND_PREFIX, stop_event),
            daemon=True,
        )
        ft = threading.Thread(
            target=_stream_lines,
            args=(frontend_proc, FRONTEND_PREFIX, stop_event),
            daemon=True,
        )
        bt.start()
        ft.start()

        # ── Wait for Ctrl+C or child exit ─────────────────────────
        try:
            backend_proc.wait()
        except KeyboardInterrupt:
            console.print("\n[yellow]Ctrl+C received — shutting down…[/yellow]")

    finally:
        # ── AR-01: terminate both processes ────────────────────────
        stop_event.set()
        for proc in (backend_proc, frontend_proc):
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=3)
                except Exception:
                    proc.kill()

        console.print("[green]Both servers stopped.[/green]")
