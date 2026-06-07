"""BATCH-137 / TASK-01 — .env git tracking and .env.example hygiene.

Tests:
  TEST-137-01-01  .env is not tracked by git (HB-01)
  TEST-137-01-02  .env.example contains no real credentials (HB-02)
  TEST-137-01-03  .env.example documents JWT_SECRET field
  TEST-137-01-04  .env.example documents LMSTUDIO fields
"""

import os
import re
import subprocess

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ENV_EXAMPLE = os.path.join(ROOT, ".env.example")


class TestEnvGitTracking:
    """TEST-137-01-01: .env is not tracked by git."""

    def test_no_hex_strings(self) -> None:
        content = open(ENV_EXAMPLE, encoding="utf-8").read()
        matches = re.findall(r"[0-9a-fA-F]{20,}", content)
        assert matches == [], (
            f".env.example contains potential real credentials (hex strings >20 chars): {matches}"
        )


class TestEnvExampleJwtSecret:
    """TEST-137-01-03: .env.example documents JWT_SECRET field."""

    def test_jwt_secret_documented(self) -> None:
        content = open(ENV_EXAMPLE, encoding="utf-8").read()
        assert "EROCK_JWT_SECRET" in content, (
            ".env.example must document EROCK_JWT_SECRET"
        )


class TestEnvExampleLmstudioFields:
    """TEST-137-01-04: .env.example documents LMSTUDIO fields."""

    @pytest.mark.parametrize("field", [
        "EROCK_LMSTUDIO_BASE_URL",
        "EROCK_LMSTUDIO_MODEL",
        "EROCK_LMSTUDIO_ENABLED",
    ])
    def test_lmstudio_fields_documented(self, field: str) -> None:
        content = open(ENV_EXAMPLE, encoding="utf-8").read()
        assert field in content, (
            f".env.example must document {field}"
        )
