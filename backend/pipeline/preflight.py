"""Pipeline Preflight Check System.

Validates pipeline readiness BEFORE accepting a run request.
Returns structured results so users know exactly what's wrong.

Added: BATCH-172 (post-Phase 10 hardening)
Motivation: The pipeline API could return {"status": "running"} even when
the orchestrator would fail to initialize. This module runs checks first.
"""
from __future__ import annotations

import asyncio
import logging
import os
import socket
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CheckSeverity(str, Enum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


@dataclass
class PreflightResult:
    """Result of a single preflight check."""
    name: str
    severity: CheckSeverity
    message: str
    detail: str = ""
    latency_ms: float = 0.0


@dataclass
class PreflightReport:
    """Complete preflight report for a pipeline run."""
    checks: list[PreflightResult] = field(default_factory=list)
    can_proceed: bool = False
    warnings: int = 0
    errors: int = 0
    fatal: int = 0

    @property
    def summary(self) -> str:
        total = len(self.checks)
        ok = sum(1 for c in self.checks if c.severity == CheckSeverity.OK)
        parts = [f"{ok}/{total} passed"]
        if self.warnings:
            parts.append(f"{self.warnings} warnings")
        if self.errors:
            parts.append(f"{self.errors} errors")
        if self.fatal:
            parts.append(f"{self.fatal} fatal")
        return ", ".join(parts)


async def run_preflight(
    domain: str,
    strategy: str,
    settings: Any = None,
) -> PreflightReport:
    """Run all preflight checks before accepting a pipeline run.

    Returns a PreflightReport with detailed results for each check.
    The caller should only proceed if report.can_proceed is True.
    """
    if settings is None:
        try:
            from backend.config import get_settings
            settings = get_settings()
        except Exception as e:
            report = PreflightReport(can_proceed=False)
            report.checks.append(PreflightResult(
                name="settings_load",
                severity=CheckSeverity.FATAL,
                message="Cannot load settings",
                detail=str(e),
            ))
            report.fatal = 1
            return report

    checks: list[PreflightResult] = []

    # 1. Settings loaded
    checks.append(PreflightResult(
        name="settings",
        severity=CheckSeverity.OK,
        message="Settings loaded successfully",
    ))

    # 2. LLM provider reachable
    checks.append(await _check_llm_provider(settings))

    # 3. Embedding provider reachable
    checks.append(await _check_embedding_provider(settings))

    # 4. Local LLM (LM Studio) if enabled
    checks.append(await _check_local_llm(settings))

    # 5. Database writable
    checks.append(await _check_database(settings))

    # 6. Export directory writable
    checks.append(_check_export_dir(settings))

    # 7. Strategy registered
    checks.append(_check_strategy(strategy))

    # 8. Domain non-empty
    checks.append(_check_domain(domain))

    # Build report
    report = PreflightReport(checks=checks)
    report.warnings = sum(1 for c in checks if c.severity == CheckSeverity.WARNING)
    report.errors = sum(1 for c in checks if c.severity == CheckSeverity.ERROR)
    report.fatal = sum(1 for c in checks if c.severity == CheckSeverity.FATAL)

    # Can proceed if no fatal errors
    report.can_proceed = report.fatal == 0

    return report


async def _check_llm_provider(settings: Any) -> PreflightResult:
    """Check if the primary LLM provider is reachable."""
    import time
    start = time.monotonic()
    try:
        from backend.providers.provider_factory import create_provider
        provider = create_provider()
        # Try a minimal completion
        response = await asyncio.wait_for(
            provider.complete([{"role": "user", "content": "Reply with exactly: OK"}]),
            timeout=15.0,
        )
        latency = (time.monotonic() - start) * 1000
        if response and len(response.strip()) > 0:
            return PreflightResult(
                name="llm_provider",
                severity=CheckSeverity.OK,
                message="LLM provider reachable",
                latency_ms=round(latency, 1),
            )
        else:
            return PreflightResult(
                name="llm_provider",
                severity=CheckSeverity.ERROR,
                message="LLM provider returned empty response",
                latency_ms=round(latency, 1),
            )
    except asyncio.TimeoutError:
        latency = (time.monotonic() - start) * 1000
        return PreflightResult(
            name="llm_provider",
            severity=CheckSeverity.ERROR,
            message=f"LLM provider timed out ({latency/1000:.0f}s)",
            latency_ms=round(latency, 1),
        )
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        return PreflightResult(
            name="llm_provider",
            severity=CheckSeverity.FATAL,
            message=f"LLM provider failed: {type(e).__name__}",
            detail=str(e)[:200],
            latency_ms=round(latency, 1),
        )


async def _check_embedding_provider(settings: Any) -> PreflightResult:
    """Check if the embedding provider can produce vectors."""
    import time
    start = time.monotonic()
    try:
        from backend.pipeline.knowledge.embedding_providers import create_embedding_provider
        provider = create_embedding_provider(
            provider_name=settings.embedding_provider,
            model=settings.embedding_model,
            api_key=settings.openai_api_key,
            base_url=settings.ollama_base_url,
            dimension=settings.embedding_dimension or None,
        )
        vectors = await asyncio.wait_for(
            provider.embed(["test"]),
            timeout=10.0,
        )
        latency = (time.monotonic() - start) * 1000
        if vectors and len(vectors) > 0 and len(vectors[0]) > 0:
            dim = len(vectors[0])
            return PreflightResult(
                name="embedding_provider",
                severity=CheckSeverity.OK,
                message=f"Embedding provider working ({dim}d vectors)",
                latency_ms=round(latency, 1),
            )
        else:
            return PreflightResult(
                name="embedding_provider",
                severity=CheckSeverity.WARNING,
                message="Embedding provider returned empty vectors (pipeline will degrade)",
                latency_ms=round(latency, 1),
            )
    except asyncio.TimeoutError:
        latency = (time.monotonic() - start) * 1000
        return PreflightResult(
            name="embedding_provider",
            severity=CheckSeverity.WARNING,
            message=f"Embedding provider timed out (pipeline will degrade)",
            detail="Vector search will be unavailable; BM25 only",
            latency_ms=round(latency, 1),
        )
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        return PreflightResult(
            name="embedding_provider",
            severity=CheckSeverity.WARNING,
            message=f"Embedding provider failed: {type(e).__name__}",
            detail="Pipeline will run without vector search (BM25 only)",
            latency_ms=round(latency, 1),
        )


async def _check_local_llm(settings: Any) -> PreflightResult:
    """Check if local LM Studio is reachable (if enabled)."""
    if not getattr(settings, 'lmstudio_enabled', False) and not getattr(settings, 'thinking_model', ''):
        return PreflightResult(
            name="local_llm",
            severity=CheckSeverity.OK,
            message="Local LLM not enabled (skipped)",
        )

    import time
    start = time.monotonic()
    base_url = getattr(settings, 'lmstudio_base_url', 'http://localhost:1234/v1')

    try:
        # Check TCP connectivity
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 1234

        _, latency_tcp = _check_tcp(host, port, timeout=3.0)
        elapsed = (time.monotonic() - start) * 1000

        if latency_tcp is not None:
            return PreflightResult(
                name="local_llm",
                severity=CheckSeverity.OK,
                message=f"LM Studio reachable at {host}:{port}",
                latency_ms=round(elapsed, 1),
            )
        else:
            return PreflightResult(
                name="local_llm",
                severity=CheckSeverity.WARNING,
                message=f"LM Studio not reachable at {host}:{port}",
                detail="Pipeline will use cloud LLM for all tasks",
                latency_ms=round(elapsed, 1),
            )
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return PreflightResult(
            name="local_llm",
            severity=CheckSeverity.WARNING,
            message=f"Local LLM check failed: {type(e).__name__}",
            detail="Pipeline will use cloud LLM for all tasks",
            latency_ms=round(elapsed, 1),
        )


async def _check_database(settings: Any) -> PreflightResult:
    """Check if the database is reachable and writable."""
    import time
    start = time.monotonic()
    try:
        from backend.db.database import get_session
        from backend.db.models import PipelineRun
        with get_session() as db:
            # Try a read query
            count = db.query(PipelineRun).count()
            latency = (time.monotonic() - start) * 1000
            return PreflightResult(
                name="database",
                severity=CheckSeverity.OK,
                message=f"Database reachable ({count} existing runs)",
                latency_ms=round(latency, 1),
            )
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        return PreflightResult(
            name="database",
            severity=CheckSeverity.FATAL,
            message=f"Database unreachable: {type(e).__name__}",
            detail=str(e)[:200],
            latency_ms=round(latency, 1),
        )


def _check_export_dir(settings: Any) -> PreflightResult:
    """Check if the export directory is writable."""
    try:
        export_dir = getattr(settings, 'export_dir', 'exports')
        os.makedirs(export_dir, exist_ok=True)
        # Try writing a temp file
        test_path = os.path.join(export_dir, ".preflight_test")
        with open(test_path, 'w') as f:
            f.write("ok")
        os.remove(test_path)
        return PreflightResult(
            name="export_dir",
            severity=CheckSeverity.OK,
            message=f"Export directory writable ({export_dir})",
        )
    except Exception as e:
        return PreflightResult(
            name="export_dir",
            severity=CheckSeverity.ERROR,
            message=f"Export directory not writable",
            detail=str(e)[:200],
        )


def _check_strategy(strategy: str) -> PreflightResult:
    """Check if the requested strategy is registered."""
    try:
        from backend.pipeline.strategies.presets import register_presets
        from backend.pipeline.strategies.registry import StrategyRegistry
        from backend.pipeline.strategies.models import PipelineStrategy

        registry = StrategyRegistry()
        register_presets(registry)

        # Find matching strategy
        for ps in PipelineStrategy:
            if ps.value == strategy:
                config = registry.get(ps)
                return PreflightResult(
                    name="strategy",
                    severity=CheckSeverity.OK,
                    message=f"Strategy '{strategy}' registered ({len(config.stages)} stages)",
                )

        return PreflightResult(
            name="strategy",
            severity=CheckSeverity.FATAL,
            message=f"Unknown strategy: '{strategy}'",
            detail=f"Available: {[s.value for s in PipelineStrategy]}",
        )
    except Exception as e:
        return PreflightResult(
            name="strategy",
            severity=CheckSeverity.ERROR,
            message=f"Strategy check failed: {type(e).__name__}",
            detail=str(e)[:200],
        )


def _check_domain(domain: str) -> PreflightResult:
    """Check if the domain is non-empty."""
    if not domain or not domain.strip():
        return PreflightResult(
            name="domain",
            severity=CheckSeverity.FATAL,
            message="Domain is empty",
        )
    if len(domain) < 3:
        return PreflightResult(
            name="domain",
            severity=CheckSeverity.WARNING,
            message="Domain is very short, results may be poor",
        )
    return PreflightResult(
        name="domain",
        severity=CheckSeverity.OK,
        message=f"Domain: '{domain[:50]}'",
    )


def _check_tcp(host: str, port: int, timeout: float = 3.0) -> tuple[bool, float | None]:
    """Check TCP connectivity. Returns (reachable, latency_ms)."""
    import time
    start = time.monotonic()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True, (time.monotonic() - start) * 1000
    except (socket.error, OSError):
        return False, None
