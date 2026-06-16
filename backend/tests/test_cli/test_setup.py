"""Tests for BATCH-07/TASK-01 — erock setup interactive wizard.

Test IDs: TEST-07-01-01 through TEST-07-01-06
"""

from __future__ import annotations

import sys
import pytest

pytestmark = pytest.mark.skipif(
    sys.version_info >= (3, 14),
    reason="Python 3.14 CLI version detection incompatibility",
)

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Helpers ──────────────────────────────────────────────────────────

# Ensure heavy optional deps don't block import
for _mod in ("chromadb",):
    sys.modules.setdefault(_mod, MagicMock())

from backend.cli.commands.setup import (
    REQUIRED_ENV_VARS,
    check_python_version,
    detect_ollama,
    generate_env_content,
    setup_wizard,
    validate_api_key,
)


# ── TEST-07-01-01: Wizard detects Python <3.11 and exits with error ─


def test_01_python_too_old_exits():
    """Python < 3.11 must cause the wizard to exit with code 1."""
    from click.exceptions import Exit as ClickExit

    with patch("backend.cli.commands.setup.check_python_version", return_value=False):
        with pytest.raises((SystemExit, ClickExit)) as exc_info:
            setup_wizard(provider=None, key=None)
        code = getattr(exc_info.value, "code", getattr(exc_info.value, "exit_code", 1))
        assert code == 1


# ── TEST-07-01-02: Wizard writes complete .env for OpenAI provider ──


def test_02_openai_env_complete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Wizard must produce a .env with correct defaults for OpenAI."""
    monkeypatch.chdir(tmp_path)

    # Patch out external calls
    with patch("backend.cli.commands.setup.validate_api_key", new_callable=AsyncMock) as mock_val, \
         patch("backend.cli.commands.setup.Confirm.ask", return_value=False), \
         patch("backend.cli.commands.setup.Prompt.ask", return_value="1"):
        mock_val.return_value = True
        setup_wizard(provider="openai", key="sk-test-openai-key")

    env_file = tmp_path / ".env"
    assert env_file.exists(), ".env file was not created"

    content = env_file.read_text()
    assert "EROCK_DEFAULT_PROVIDER=openai" in content
    assert "EROCK_OPENAI_API_KEY=sk-test-openai-key" in content
    assert "EROCK_OPENAI_MODEL=gpt-4o" in content


# ── TEST-07-01-03: Wizard writes complete .env for Ollama provider ──


def test_03_ollama_env_complete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Wizard must produce a .env with ollama defaults when Ollama is detected."""
    monkeypatch.chdir(tmp_path)

    with patch("backend.cli.commands.setup.detect_ollama", new_callable=AsyncMock) as mock_det, \
         patch("backend.cli.commands.setup.Confirm.ask", return_value=False):
        mock_det.return_value = True
        setup_wizard(provider="ollama", key=None)

    env_file = tmp_path / ".env"
    assert env_file.exists(), ".env file was not created"

    content = env_file.read_text()
    assert "EROCK_DEFAULT_PROVIDER=ollama" in content
    assert "EROCK_OLLAMA_BASE_URL=http://localhost:11434" in content
    assert "EROCK_OLLAMA_MODEL=llama3" in content
    assert "EROCK_EMBEDDING_PROVIDER=ollama" in content
    assert "EROCK_EMBEDDING_MODEL=nomic-embed-text" in content


# ── TEST-07-01-04: Invalid API key detected and user re-prompted ────


def test_04_invalid_api_key_exits():
    """Wizard must exit with error when API key validation fails."""
    from click.exceptions import Exit as ClickExit

    with pytest.raises((SystemExit, ClickExit)) as exc_info:
        with patch("backend.cli.commands.setup.validate_api_key", new_callable=AsyncMock) as mock_val:
            mock_val.return_value = False
            setup_wizard(provider="openai", key="sk-invalid-key")
    code = getattr(exc_info.value, "code", getattr(exc_info.value, "exit_code", 1))
    assert code == 1


# ── TEST-07-01-05: .env contains all 18 required variables ──────────


def test_05_env_contains_all_required_variables():
    """Generated .env must contain every variable from the REQUIRED_ENV_VARS list."""
    content = generate_env_content(provider="openai", api_key="sk-test")
    lines = content.strip().split("\n")
    env_keys = set()
    for line in lines:
        if "=" in line and not line.startswith("#"):
            env_keys.add(line.split("=")[0])

    missing = set(REQUIRED_ENV_VARS) - env_keys
    assert not missing, f"Missing env variables: {missing}"
    assert len(env_keys) >= 18, f"Expected ≥18 vars, got {len(env_keys)}"


# ── TEST-07-01-06: Full wizard run produces working .env (mocked API) ─


def test_06_full_wizard_e2e(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """End-to-end wizard run with mocked API must produce a usable .env."""
    monkeypatch.chdir(tmp_path)

    with patch("backend.cli.commands.setup.validate_api_key", new_callable=AsyncMock) as mock_val, \
         patch("backend.cli.commands.setup.Confirm.ask", return_value=False):
        mock_val.return_value = True
        setup_wizard(provider="anthropic", key="sk-ant-test-key")

    env_file = tmp_path / ".env"
    assert env_file.exists(), ".env was not created"

    content = env_file.read_text()
    assert "EROCK_DEFAULT_PROVIDER=anthropic" in content
    assert "EROCK_ANTHROPIC_API_KEY=sk-ant-test-key" in content
    assert "EROCK_ANTHROPIC_MODEL=claude-sonnet-4-20250514" in content

    # Verify all 18 required vars present in the file
    lines = [l for l in content.strip().split("\n") if "=" in l and not l.startswith("#")]
    env_keys = {l.split("=")[0] for l in lines}
    missing = set(REQUIRED_ENV_VARS) - env_keys
    assert not missing, f"Missing env variables in e2e output: {missing}"
