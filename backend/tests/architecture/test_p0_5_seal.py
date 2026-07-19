"""P0.5.10: Production seal for configuration-effectiveness enforcement.

AST scans for configuration anti-patterns and verifies that the
registry covers every accepted Settings field.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[3] / "backend"
REPO_ROOT = Path(__file__).resolve().parents[3]


def _read_ast(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except Exception:
        return None


# ── 1. Registry covers every Settings field ──────────────────────────


def test_registry_covers_every_settings_field():
    """Every accepted Settings field must be in the registry."""
    from backend.config import Settings
    from backend.pipeline.config.field_registry import build_registry

    registry = build_registry()
    settings_names = set(Settings.model_fields.keys())
    registry_paths = {f.canonical_path for f in registry.fields.values()}
    missing = settings_names - registry_paths
    assert not missing, f"Missing from registry: {sorted(missing)[:10]}"


# ── 2. Registry validation passes ────────────────────────────────────


def test_registry_validation_clean():
    from backend.pipeline.config.field_registry import build_registry, validate_registry

    registry = build_registry()
    errors = validate_registry(registry)
    assert not errors, f"Registry validation errors:\n" + "\n".join(errors)


# ── 3. Config CLI exists and is wired ─────────────────────────────────


def test_config_cli_wired():
    """The config_cli must be importable and registered."""
    from backend.cli.config_cli import config_app
    assert config_app is not None

    # Check it's wired into main
    main_path = BACKEND_ROOT / "cli" / "main.py"
    source = main_path.read_text(encoding="utf-8")
    assert "config_app" in source, "config_cli not wired into main.py"
    assert "config_cli" in source


# ── 4. No getattr(settings, "field", fallback) for registered fields ──


def test_no_hardcoded_fallbacks_for_material_fields():
    """Material fields must not have getattr-with-fallback in production
    code outside the config package. The Settings model owns the default —
    no second default owner may exist."""
    from backend.pipeline.config.field_registry import build_registry

    registry = build_registry()
    material_paths = {f.canonical_path for f in registry.material_fields()}

    violations: list[str] = []
    for py_file in (BACKEND_ROOT).rglob("*.py"):
        rel = str(py_file.relative_to(REPO_ROOT)).replace("\\", "/")
        if "/tests/" in rel or "/config/" in rel or "__pycache__" in rel:
            continue
        if rel.endswith("config.py"):
            continue

        try:
            source = py_file.read_text(encoding="utf-8")
        except Exception:
            continue

        tree = _read_ast(py_file)
        if tree is None:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "getattr" and len(node.args) >= 3:
                    if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                        field_name = node.args[1].value
                        if field_name in material_paths:
                            violations.append(
                                f"{rel}:{node.lineno} getattr(..., \"{field_name}\", <fallback>)"
                            )

    assert not violations, (
        "Material fields with hard-coded fallback defaults in production:\n"
        + "\n".join(f"  {v}" for v in violations[:30])
    )


# ── 5. Effective domain configs are importable ───────────────────────


def test_effective_domain_configs_importable():
    """The effective domain configurations must be importable."""
    from backend.pipeline.config.effective_configurations import (
        EffectiveDomainConfigurations,
        build_effective_domain_configurations,
    )
    assert EffectiveDomainConfigurations is not None
    assert build_effective_domain_configurations is not None


# ── 6. No os.environ reads outside source adapters ───────────────────


def test_no_direct_os_environ_in_production():
    """Production code must not read os.environ directly outside
    config.py and source adapters."""
    violations: list[str] = []
    for py_file in BACKEND_ROOT.rglob("*.py"):
        rel = str(py_file.relative_to(REPO_ROOT)).replace("\\", "/")
        if "/tests/" in rel or "__pycache__" in rel:
            continue
        if rel.endswith("config.py") or rel.endswith("config_cli.py"):
            continue
        if "sandboxing" in rel or "mcp/transport" in rel:
            continue  # legitimate subprocess env passing

        try:
            source = py_file.read_text(encoding="utf-8")
        except Exception:
            continue

        if "os.environ" in source or "os.getenv" in source:
            for i, line in enumerate(source.splitlines(), 1):
                if "os.environ" in line or "os.getenv" in line:
                    violations.append(f"{rel}:{i}")

    assert not violations, (
        "Direct os.environ/os.getenv reads in production:\n"
        + "\n".join(f"  {v}" for v in violations[:20])
    )
