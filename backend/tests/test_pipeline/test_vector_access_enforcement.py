"""Architectural test: prohibits direct production Chroma access (P0.3.4H).

Only allowlisted modules may access ChromaDB directly:
  vector_backend.py, vector_indexer.py, scoped_vector_service.py,
  knowledge/vector_store.py (legacy compat), explicit maintenance tools.

All other production modules must go through the governed boundaries.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

# Modules allowed to import chromadb or access collections directly
_ALLOWLIST_PATTERNS = [
    "pipeline/vector_backend.py",
    "pipeline/vector_indexer.py",
    "pipeline/scoped_vector_service.py",
    "pipeline/vector_runtime.py",  # central composition root (constructs chromadb client)
    "pipeline/knowledge/vector_store.py",  # legacy compat layer
    "pipeline/knowledge/graph_embeddings.py",  # KG entity embeddings (not paper corpus)
    "pipeline/tools/tool_index.py",  # tool capability index (not paper corpus)
    "providers/cache/semantic_cache.py",  # LLM response cache (not paper corpus)
    "pipeline/legacy_vector_inventory.py",  # P0.3.5 maintenance inventory (allowed to read research_papers)
    "tests/",  # test code
    "__pycache__",
    ".venv",
]


def _is_allowlisted(path: str) -> bool:
    # Normalize to forward slashes for cross-platform matching
    normalized = path.replace("\\", "/")
    return any(pat in normalized for pat in _ALLOWLIST_PATTERNS)


def _find_python_files(root: Path) -> list[Path]:
    """Find all .py files under root, excluding venv, __pycache__, and tests."""
    results = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip venv, __pycache__, and test directories
        if ".venv" in dirpath or "__pycache__" in dirpath or os.sep + "tests" in dirpath:
            continue
        for f in filenames:
            if f.endswith(".py"):
                results.append(Path(dirpath) / f)
    return results


def _check_imports(filepath: Path) -> list[str]:
    """Check if a file imports chromadb directly. Returns list of violations."""
    violations = []
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except Exception:
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "chromadb":
                    violations.append(f"direct import: chromadb (line {node.lineno})")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("chromadb"):
                violations.append(f"from import: {node.module} (line {node.lineno})")

    return violations


def test_no_direct_chromadb_imports_in_production():
    """No production module outside the allowlist may import chromadb."""
    backend_root = Path(__file__).resolve().parents[3] / "backend"

    if not backend_root.exists():
        pytest.skip("backend dir not found")

    violations: list[str] = []

    for filepath in _find_python_files(backend_root):
        rel = str(filepath.relative_to(backend_root.parent))
        if _is_allowlisted(rel):
            continue
        file_violations = _check_imports(filepath)
        for v in file_violations:
            violations.append(f"{rel}: {v}")

    if violations:
        detail = "\n".join(f"  {v}" for v in violations)
        pytest.fail(
            f"Direct chromadb imports found in {len(violations)} production file(s):\n{detail}\n"
            f"Production code must use backend/pipeline/vector_backend.py or "
            f"backend/pipeline/scoped_vector_service.py instead."
        )
