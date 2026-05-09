"""BATCH-137 / TASK-03 — Remove hardcoded IP fallbacks.

Tests:
  TEST-137-03-01  No hardcoded non-localhost IPs in backend/pipeline/ and backend/providers/
  TEST-137-03-02  provider_factory reads LMSTUDIO_BASE_URL from settings (no hardcoded IP)
  TEST-137-03-03  config.py lmstudio_base_url default is localhost
"""

import os
import re

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# Regex for private/non-localhost IP ranges
_NON_LOCALHOST_IP_RE = re.compile(
    r"(100\.64\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3})"
)


def _collect_py_files(*dirs: str) -> list[str]:
    """Yield .py files under the given directories, excluding __pycache__ and tests."""
    result = []
    for base_dir in dirs:
        for dirpath, _dirnames, filenames in os.walk(base_dir):
            # Skip __pycache__
            if "__pycache__" in dirpath:
                continue
            # Skip test directories
            if os.path.basename(dirpath) == "tests":
                continue
            for fn in filenames:
                if fn.endswith(".py"):
                    result.append(os.path.join(dirpath, fn))
    return result


class TestNoHardcodedNonLocalhostIPs:
    """TEST-137-03-01: No hardcoded non-localhost IPs in backend code."""

    def test_no_private_ips_in_pipeline_and_providers(self) -> None:
        pipeline_dir = os.path.join(ROOT, "backend", "pipeline")
        providers_dir = os.path.join(ROOT, "backend", "providers")
        py_files = _collect_py_files(pipeline_dir, providers_dir)

        violations = []
        for filepath in py_files:
            content = open(filepath, encoding="utf-8").read()
            for lineno, line in enumerate(content.splitlines(), start=1):
                if _NON_LOCALHOST_IP_RE.search(line):
                    violations.append(f"{filepath}:{lineno}: {line.strip()}")

        assert violations == [], (
            f"Found hardcoded non-localhost IPs:\n" + "\n".join(violations)
        )


class TestProviderFactoryUsesSettings:
    """TEST-137-03-02: provider_factory reads LMSTUDIO_BASE_URL from settings."""

    def test_no_hardcoded_ip_in_provider_factory(self) -> None:
        filepath = os.path.join(ROOT, "backend", "providers", "provider_factory.py")
        content = open(filepath, encoding="utf-8").read()
        # Should NOT contain the old hardcoded IP
        assert "100.64.0.1" not in content, (
            "provider_factory.py still contains hardcoded IP 100.64.0.1"
        )
        # Should use settings.lmstudio_base_url
        assert "settings.lmstudio_base_url" in content, (
            "provider_factory.py should read lmstudio_base_url from settings"
        )


class TestConfigDefaultIsLocalhost:
    """TEST-137-03-03: config.py lmstudio_base_url default is localhost."""

    def test_default_is_localhost(self) -> None:
        import inspect
        from backend.config import Settings

        # Verify the source code default, not the runtime value (which may be
        # overridden by .env). This is the correct check for "config.py default".
        source = inspect.getsource(Settings)
        # Find the line with lmstudio_base_url
        for line in source.splitlines():
            if "lmstudio_base_url" in line and "=" in line:
                assert "localhost" in line or "\"\"" in line, (
                    f"config.py lmstudio_base_url default should use localhost, line: {line.strip()}"
                )
                assert "100.64" not in line, (
                    f"config.py lmstudio_base_url default should NOT contain 100.64, line: {line.strip()}"
                )
                break
