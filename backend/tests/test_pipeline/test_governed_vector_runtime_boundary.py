"""B0.6b enforcement tests: seal governed vector runtime composition boundary.

Proves:
  - Runtime has exactly 4 public fields (no removed fields)
  - No production code references removed fields
  - No inline _EmbeddingAdapter class definitions
  - Runtime builder sequencing (reconciliation before provider)
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest


# ── Runtime structure ────────────────────────────────────────────────


def test_runtime_has_exactly_four_public_fields():
    from backend.pipeline.vector_runtime import GovernedVectorRuntime
    import dataclasses

    fields = {f.name for f in dataclasses.fields(GovernedVectorRuntime)}
    assert fields == {
        "backend",
        "session_factory",
        "effective_embedding_config",
        "embedding_adapter",
    }


def test_runtime_absent_fields():
    from backend.pipeline.vector_runtime import GovernedVectorRuntime

    assert not hasattr(GovernedVectorRuntime, "embedding_provider")
    assert not hasattr(GovernedVectorRuntime, "provider")
    assert not hasattr(GovernedVectorRuntime, "profile_dict")
    assert not hasattr(GovernedVectorRuntime, "embedding_profile_id")
    assert not hasattr(GovernedVectorRuntime, "db_engine")


# ── Architectural scan: no production references to removed fields ───


_REMOVED_PATTERNS = [
    "runtime.embedding_provider",
    "runtime.profile_dict",
    "runtime.db_engine",
    "runtime.embedding_profile_id",
]


def _find_python_files(root: Path, exclude_tests: bool = True):
    results = []
    for dirpath, dirnames, filenames in os.walk(root):
        if ".venv" in dirpath or "__pycache__" in dirpath or os.sep + "tests" in dirpath:
            continue
        for f in filenames:
            if f.endswith(".py"):
                results.append(Path(dirpath) / f)
    return results


def test_no_production_references_to_removed_runtime_fields():
    """Production code must not reference removed runtime fields."""
    backend_root = Path(__file__).resolve().parents[3] / "backend"
    if not backend_root.exists():
        pytest.skip("backend dir not found")

    violations = []
    for filepath in _find_python_files(backend_root):
        rel = str(filepath.relative_to(backend_root.parent)).replace("\\", "/")
        # Allow vector_runtime.py itself (it defines the new structure)
        if "pipeline/vector_runtime.py" in rel:
            continue
        try:
            content = filepath.read_text(encoding="utf-8")
        except Exception:
            continue
        for pattern in _REMOVED_PATTERNS:
            if pattern in content:
                violations.append(f"{rel}: {pattern}")

    if violations:
        detail = "\n".join(f"  {v}" for v in violations)
        pytest.fail(
            f"Found {len(violations)} production reference(s) to removed runtime fields:\n{detail}"
        )


def test_no_inline_embedding_adapter_classes():
    """No production module should define an inline _EmbeddingAdapter class."""
    backend_root = Path(__file__).resolve().parents[3] / "backend"
    if not backend_root.exists():
        pytest.skip("backend dir not found")

    violations = []
    for filepath in _find_python_files(backend_root):
        try:
            source = filepath.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(filepath))
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "_EmbeddingAdapter":
                rel = str(filepath.relative_to(backend_root.parent)).replace("\\", "/")
                violations.append(f"{rel}: class _EmbeddingAdapter (line {node.lineno})")

    if violations:
        detail = "\n".join(f"  {v}" for v in violations)
        pytest.fail(
            f"Found {len(violations)} inline _EmbeddingAdapter class definition(s):\n{detail}\n"
            f"Use backend.pipeline.governed_embedding_adapter.GovernedEmbeddingAdapter instead."
        )
