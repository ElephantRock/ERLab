"""Pipeline health monitoring.

Checks subsystem health: database, embedding provider, LLM provider,
search sources. Returns structured health report.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """Health status of a single component."""
    name: str
    status: HealthStatus
    latency_ms: float = 0.0
    message: str = ""
    details: dict = field(default_factory=dict)


@dataclass
class HealthReport:
    """Complete system health report."""
    status: HealthStatus = HealthStatus.HEALTHY
    components: list[ComponentHealth] = field(default_factory=list)
    checked_at: str = ""

    @property
    def is_healthy(self) -> bool:
        return self.status != HealthStatus.UNHEALTHY

    @property
    def degraded_count(self) -> int:
        return sum(1 for c in self.components if c.status == HealthStatus.DEGRADED)

    @property
    def unhealthy_count(self) -> int:
        return sum(1 for c in self.components if c.status == HealthStatus.UNHEALTHY)


class HealthMonitor:
    """Monitors pipeline subsystem health.

    Checks: database, embedding provider, LLM provider, search sources.
    Each check runs independently with its own timeout.
    """

    def __init__(self) -> None:
        self._checks: dict[str, callable] = {}

    def register_check(self, name: str, check_fn: callable) -> None:
        """Register a health check function.

        check_fn should return ComponentHealth.
        """
        self._checks[name] = check_fn

    async def check_all(self) -> HealthReport:
        """Run all health checks and return a report."""
        import asyncio
        from datetime import datetime

        components: list[ComponentHealth] = []

        for name, check_fn in self._checks.items():
            try:
                start = time.monotonic()
                result = await asyncio.wait_for(
                    check_fn() if asyncio.iscoroutinefunction(check_fn) else asyncio.to_thread(check_fn),
                    timeout=5.0,
                )
                if not isinstance(result, ComponentHealth):
                    result = ComponentHealth(name=name, status=HealthStatus.HEALTHY)
                result.latency_ms = (time.monotonic() - start) * 1000
                components.append(result)
            except Exception as e:
                components.append(ComponentHealth(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=str(e),
                ))

        # Determine overall status
        overall = HealthStatus.HEALTHY
        if any(c.status == HealthStatus.UNHEALTHY for c in components):
            overall = HealthStatus.UNHEALTHY
        elif any(c.status == HealthStatus.DEGRADED for c in components):
            overall = HealthStatus.DEGRADED

        return HealthReport(
            status=overall,
            components=components,
            checked_at=datetime.utcnow().isoformat(),
        )

    def create_default_report(self) -> HealthReport:
        """Create a default report without running checks."""
        return HealthReport(
            status=HealthStatus.HEALTHY,
            components=[
                ComponentHealth(name="database", status=HealthStatus.HEALTHY, message="Not checked"),
                ComponentHealth(name="embedding_provider", status=HealthStatus.HEALTHY, message="Not checked"),
                ComponentHealth(name="llm_provider", status=HealthStatus.HEALTHY, message="Not checked"),
                ComponentHealth(name="search_sources", status=HealthStatus.HEALTHY, message="Not checked"),
            ],
            checked_at="",
        )
