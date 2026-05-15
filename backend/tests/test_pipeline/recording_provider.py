"""RecordingProvider — LLM provider that records all calls for functional testing.

Wraps a real LLM provider and records every complete() and structured_output()
call. After a test, you can assert on:
- Number of calls made
- Arguments passed to each call
- Whether the call succeeded

Phase F: Functional Test Harness
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RecordedCall:
    """A single recorded LLM call."""
    method: str  # "complete" or "structured_output"
    args: dict = field(default_factory=dict)
    response: Any = None
    error: str | None = None
    succeeded: bool = True


class RecordingProvider:
    """Wraps an LLM provider and records all calls.

    Usage in tests:
        real_provider = get_thinking_provider(settings)
        recorder = RecordingProvider(real_provider)
        # ... run pipeline with recorder ...
        assert len(recorder.calls) == 3
        assert recorder.calls[0].method == "structured_output"
        assert all(c.succeeded for c in recorder.calls)
    """

    def __init__(self, inner: Any):
        self._inner = inner
        self.calls: list[RecordedCall] = []

    # Pass through provider properties
    @property
    def provider_name(self) -> str:
        return getattr(self._inner, "provider_name", "recording")

    @property
    def base_url(self) -> str:
        return getattr(self._inner, "base_url", getattr(self._inner, "_base_url", ""))

    @property
    def model(self) -> str:
        return getattr(self._inner, "model", getattr(self._inner, "_model", ""))

    async def complete(self, **kwargs) -> str:
        """Record and forward complete() call."""
        call = RecordedCall(method="complete", args=kwargs)
        try:
            result = await self._inner.complete(**kwargs)
            call.response = result[:200] if isinstance(result, str) else result
            call.succeeded = True
            return result
        except Exception as e:
            call.error = str(e)
            call.succeeded = False
            raise
        finally:
            self.calls.append(call)

    async def structured_output(self, **kwargs) -> dict:
        """Record and forward structured_output() call."""
        call = RecordedCall(method="structured_output", args=kwargs)
        try:
            result = await self._inner.structured_output(**kwargs)
            call.response = result
            call.succeeded = True
            return result
        except Exception as e:
            call.error = str(e)
            call.succeeded = False
            raise
        finally:
            self.calls.append(call)

    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def succeeded_count(self) -> int:
        return sum(1 for c in self.calls if c.succeeded)

    @property
    def failed_count(self) -> int:
        return sum(1 for c in self.calls if not c.succeeded)

    def calls_by_method(self, method: str) -> list[RecordedCall]:
        return [c for c in self.calls if c.method == method]

    def clear(self) -> None:
        """Clear recorded calls."""
        self.calls.clear()


def assert_call_counts(
    recorder: RecordingProvider,
    *,
    total_min: int = 0,
    total_max: int = 999,
    structured_min: int = 0,
    complete_min: int = 0,
    fail_max: int = 0,
) -> list[str]:
    """Assert on recording call counts. Returns list of violations."""
    violations = []
    if recorder.call_count < total_min:
        violations.append(f"Too few calls: {recorder.call_count} < {total_min}")
    if recorder.call_count > total_max:
        violations.append(f"Too many calls: {recorder.call_count} > {total_max}")
    if recorder.succeeded_count < structured_min + complete_min:
        violations.append(f"Too few successful calls: {recorder.succeeded_count}")
    if recorder.failed_count > fail_max:
        violations.append(f"Too many failures: {recorder.failed_count} > {fail_max}")

    structured = len(recorder.calls_by_method("structured_output"))
    if structured < structured_min:
        violations.append(f"Too few structured_output calls: {structured} < {structured_min}")

    complete = len(recorder.calls_by_method("complete"))
    if complete < complete_min:
        violations.append(f"Too few complete calls: {complete} < {complete_min}")

    return violations
