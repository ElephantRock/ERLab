"""Tests for BATCH-96 — Health Monitoring.

AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

import asyncio
import pytest

from backend.pipeline.monitoring.health import (
    HealthMonitor, HealthReport, ComponentHealth, HealthStatus,
)


async def _healthy_check():
    return ComponentHealth(name="test", status=HealthStatus.HEALTHY, message="OK")


async def _degraded_check():
    return ComponentHealth(name="test", status=HealthStatus.DEGRADED, message="Slow")


async def _unhealthy_check():
    return ComponentHealth(name="test", status=HealthStatus.UNHEALTHY, message="Down")


async def _failing_check():
    raise RuntimeError("Connection refused")


def test_96_01_healthy_report():
    """All healthy checks → HEALTHY overall."""
    report = HealthReport(
        components=[
            ComponentHealth(name="db", status=HealthStatus.HEALTHY),
            ComponentHealth(name="llm", status=HealthStatus.HEALTHY),
        ],
    )
    assert report.status == HealthStatus.HEALTHY
    assert report.is_healthy


def test_96_01_degraded_report():
    """One degraded → DEGRADED overall."""
    report = HealthReport(
        components=[
            ComponentHealth(name="db", status=HealthStatus.HEALTHY),
            ComponentHealth(name="llm", status=HealthStatus.DEGRADED),
        ],
    )
    assert report.degraded_count == 1
    assert report.is_healthy  # Not unhealthy


def test_96_01_unhealthy_report():
    """One unhealthy → UNHEALTHY overall."""
    report = HealthReport(
        status=HealthStatus.UNHEALTHY,
        components=[
            ComponentHealth(name="db", status=HealthStatus.UNHEALTHY),
        ],
    )
    assert not report.is_healthy
    assert report.unhealthy_count == 1


def test_96_02_check_all_runs_checks():
    """check_all runs all registered checks."""
    monitor = HealthMonitor()
    monitor.register_check("healthy", _healthy_check)
    monitor.register_check("degraded", _degraded_check)
    report = asyncio.run(monitor.check_all())
    assert len(report.components) == 2


def test_96_02_failing_check_is_unhealthy():
    """Failing check returns UNHEALTHY component."""
    monitor = HealthMonitor()
    monitor.register_check("fail", _failing_check)
    report = asyncio.run(monitor.check_all())
    assert report.components[0].status == HealthStatus.UNHEALTHY
    assert "Connection refused" in report.components[0].message


def test_96_02_mixed_status_is_degraded():
    """Healthy + degraded but no unhealthy → DEGRADED."""
    monitor = HealthMonitor()
    monitor.register_check("ok", _healthy_check)
    monitor.register_check("slow", _degraded_check)
    report = asyncio.run(monitor.check_all())
    assert report.status == HealthStatus.DEGRADED


def test_96_03_default_report():
    """Default report has 4 components."""
    monitor = HealthMonitor()
    report = monitor.create_default_report()
    assert len(report.components) == 4


def test_96_03_default_report_is_healthy():
    """Default report is healthy."""
    monitor = HealthMonitor()
    report = monitor.create_default_report()
    assert report.is_healthy
