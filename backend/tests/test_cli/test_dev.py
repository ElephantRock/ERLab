"""Tests for BATCH-08/TASK-01 — erock dev command.

Test IDs: TEST-08-01-01 through TEST-08-01-05
"""
from __future__ import annotations

import sys
import pytest

pytestmark = pytest.mark.skipif(
    sys.version_info >= (3, 14),
    reason="Python 3.14 port detection incompatibility",
)

import os
import signal
import socket
import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# ── Ensure heavy optional deps don't block import ─────────────────────
for _mod in ("chromadb",):
    sys.modules.setdefault(_mod, MagicMock())

from backend.cli.commands.dev import (
    BACKEND_PORT,
    FRONTEND_PORT,
    _build_backend_cmd,
    _build_frontend_cmd,
    _port_in_use,
    dev_command,
)


# ── TEST-08-01-01: Command constructs correct uvicorn subprocess args ─


def test_01_backend_subprocess_args():
    """_build_backend_cmd() must produce the correct uvicorn invocation."""
    cmd = _build_backend_cmd()

    assert cmd[1:] == [
        "-m",
        "uvicorn",
        "backend.api.app:app",
        "--host", "0.0.0.0",
        "--port", str(BACKEND_PORT),
        "--reload",
    ]
    # First element should be the current Python interpreter
    assert cmd[0] == sys.executable


# ── TEST-08-01-02: Command constructs correct npm subprocess args ─────


def test_02_frontend_subprocess_args():
    """_build_frontend_cmd() must produce 'npm run dev'."""
    cmd = _build_frontend_cmd()
    assert cmd == ["npm", "run", "dev"]


# ── TEST-08-01-03: SIGINT handler terminates both child processes ────


def test_03_sigint_terminates_both_processes():
    """Sending KeyboardInterrupt must terminate both child processes (AR-01)."""
    fake_backend = MagicMock(spec=subprocess.Popen)
    fake_backend.poll.return_value = None  # still running
    # First .wait() call (in inner try) raises KeyboardInterrupt;
    # Second .wait() call (in finally cleanup) returns normally.
    fake_backend.wait.side_effect = [KeyboardInterrupt, None]

    fake_frontend = MagicMock(spec=subprocess.Popen)
    fake_frontend.poll.return_value = None

    with patch("backend.cli.commands.dev._port_in_use", return_value=False), \
         patch("backend.cli.commands.dev.subprocess.Popen", side_effect=[fake_backend, fake_frontend]), \
         patch("backend.cli.commands.dev.threading.Thread"), \
         patch("backend.cli.commands.dev.threading.Event"):
        dev_command()

    # Both processes must have been terminated (AR-01)
    fake_backend.terminate.assert_called()
    fake_frontend.terminate.assert_called()


# ── TEST-08-01-04: Port-in-use detected and error reported ───────────


def test_04_port_conflict_detected_and_exits():
    """Command must exit with error when a port is already in use (HB-02)."""
    from click.exceptions import Exit as ClickExit

    # Simulate port 8000 being occupied
    with patch("backend.cli.commands.dev._port_in_use", side_effect=lambda p: p == BACKEND_PORT):
        with pytest.raises((SystemExit, ClickExit)):
            dev_command()


# ── TEST-08-01-05: Both servers start and respond to health check ────


@pytest.mark.slow
@pytest.mark.skipif(
    os.getenv("EROCK_E2E", "").lower() not in ("1", "true", "yes"),
    reason="E2E test requires EROCK_E2E=1 env var and available servers",
)
def test_05_e2e_both_servers_start(tmp_path: Path):
    """E2E: both servers must start and the backend must respond on its port.

    This test actually launches the uvicorn backend and npm frontend as
    subprocesses (if available) and checks that the backend health endpoint
    is reachable.  If npm/vite is not installed the test is skipped for
    the frontend portion but still validates backend startup.
    """
    # Skip in CI or when ports are already occupied
    if _port_in_use(BACKEND_PORT) or _port_in_use(FRONTEND_PORT):
        pytest.skip("Ports 8000 or 3000 already in use — cannot run E2E")

    project_root = Path(__file__).resolve().parents[3]  # backend/tests/test_cli/ → project root
    frontend_dir = project_root / "frontend"

    backend_proc = None
    frontend_proc = None

    try:
        # Start backend
        backend_proc = subprocess.Popen(
            _build_backend_cmd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(project_root),
        )

        # Start frontend (best-effort; skip if npm/vite unavailable)
        if frontend_dir.is_dir():
            try:
                frontend_proc = subprocess.Popen(
                    _build_frontend_cmd(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=str(frontend_dir),
                )
            except FileNotFoundError:
                frontend_proc = None  # npm not found — acceptable in some envs

        # Wait for backend to become ready (up to 15 seconds)
        import httpx

        backend_healthy = False
        for _ in range(30):
            time.sleep(0.5)
            try:
                r = httpx.get(f"http://localhost:{BACKEND_PORT}/health", timeout=2)
                if r.status_code == 200:
                    backend_healthy = True
                    break
            except (httpx.ConnectError, httpx.TimeoutException):
                continue

        assert backend_healthy, (
            f"Backend did not become healthy on port {BACKEND_PORT} within 15s"
        )

    finally:
        # AR-01: clean up both processes
        for proc in (backend_proc, frontend_proc):
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
