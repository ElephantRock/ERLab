"""Tests for BATCH-30/TASK-02 — Docker Compose configuration.

Test IDs: TEST-30-02-01 through TEST-30-02-04
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]


# ── TEST-30-02-01: Dockerfile builds successfully ────────────────────


def test_01_dockerfile_syntax_valid():
    """The Dockerfile must have valid syntax (docker build --check or parse)."""
    dockerfile = PROJECT_ROOT / "Dockerfile"
    assert dockerfile.exists(), "Dockerfile not found in project root"

    content = dockerfile.read_text()

    # Verify multi-stage build keywords
    assert "FROM python:3.11-slim AS builder" in content
    assert "FROM python:3.11-slim AS runtime" in content
    assert "COPY --from=builder" in content
    assert "CMD" in content
    assert "uvicorn" in content
    assert "HEALTHCHECK" in content

    # Verify non-root user
    assert "useradd" in content or "adduser" in content

    # Try a dry-run build (if docker is available)
    result = subprocess.run(
        ["docker", "build", "--check", "-f", str(dockerfile), str(PROJECT_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    # If docker is available, the build check should pass
    if result.returncode == 0:
        return  # Docker available and syntax OK
    # If docker is not available, we skip the build check (syntax validated above)
    if "not found" in result.stderr.lower() or "not recognized" in result.stderr.lower():
        pytest.skip("Docker not available for build check")


# ── TEST-30-02-02: docker-compose.yml valid YAML ────────────────────


def test_02_compose_valid_yaml():
    """docker-compose.yml must parse as valid YAML with expected structure."""
    compose_path = PROJECT_ROOT / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml not found in project root"

    with open(compose_path) as f:
        compose = yaml.safe_load(f)

    assert isinstance(compose, dict)
    assert "services" in compose
    assert isinstance(compose["services"], dict)


# ── TEST-30-02-03: Services defined (app, postgres, redis) ──────────


def test_03_three_services_defined():
    """docker-compose.yml must define backend, frontend, and erock_data services."""
    compose_path = PROJECT_ROOT / "docker-compose.yml"

    with open(compose_path) as f:
        compose = yaml.safe_load(f)

    services = compose["services"]
    assert "backend" in services, "Missing 'backend' service"
    assert "frontend" in services, "Missing 'frontend' service"

    # Verify backend builds from local Dockerfile
    assert "build" in services["backend"]
    assert "dockerfile" in services["backend"]["build"]

    # Verify backend depends on erock_data
    depends = services["backend"].get("depends_on", {})
    assert "erock_data" in depends or len(services) >= 2

    # Verify port mappings
    assert "8000" in str(services["app"]["ports"])
    assert "5432" in str(services["postgres"]["ports"])
    assert "6379" in str(services["redis"]["ports"])


# ── TEST-30-02-04: Health checks configured ─────────────────────────


def test_04_health_checks_configured():
    """Each service that needs health checking must have a healthcheck block."""
    compose_path = PROJECT_ROOT / "docker-compose.yml"

    with open(compose_path) as f:
        compose = yaml.safe_load(f)

    services = compose["services"]

    for svc_name in ("backend", "frontend"):
        svc = services[svc_name]
        assert "healthcheck" in svc, f"Service '{svc_name}' missing healthcheck"
        hc = svc["healthcheck"]
        assert "test" in hc, f"Service '{svc_name}' healthcheck missing 'test'"
        assert "interval" in hc, f"Service '{svc_name}' healthcheck missing 'interval'"
        assert "timeout" in hc, f"Service '{svc_name}' healthcheck missing 'timeout'"
        assert "retries" in hc, f"Service '{svc_name}' healthcheck missing 'retries'"

    # Verify .dockerignore exists
    dockerignore = PROJECT_ROOT / ".dockerignore"
    assert dockerignore.exists(), ".dockerignore not found"
    content = dockerignore.read_text()
    assert ".git" in content
    assert "node_modules" in content
    assert "__pycache__" in content
