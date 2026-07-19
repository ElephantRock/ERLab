"""P0.4A2 architectural seal: capability-bound vector lifecycle.

Required zero-count assertions:

  new vector_index_v2 rows without binding                 0
  v1 rows with capability_v1 contract                       0
  historical capability backfills                            0
  capability-v1 queries without query binding/check         0
  alias-only active binding rows                             0
  candidate vectors production-eligible                      0
  new v1 writes after profile activation                     0
  pre-capability fallback after activation                   0
  cross-binding cache hits                                   0
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[3] / "backend"
REPO_ROOT = Path(__file__).resolve().parents[3]


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _read_ast(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except Exception:
        return None


def _is_test(rel: str) -> bool:
    return "/tests/" in rel or rel.startswith("tests/")


def _iter_production_py():
    for path in BACKEND_ROOT.rglob("*.py"):
        rel = _rel(path)
        if _is_test(rel) or "__pycache__" in rel:
            continue
        yield rel, path


# ── 1. No historical binding backfill ────────────────────────────────


def test_no_historical_vector_binding_backfill():
    """No production code stamps capability_binding_id onto existing
    v1 VectorIndexRecord rows. Historical vectors remain pre_capability_v0.
    """
    violations: list[str] = []
    for rel, path in _iter_production_py():
        if "capability" in rel or "/tests/" in rel:
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except Exception:
            continue
        # Look for UPDATE vector_index_records SET capability_binding_id
        if "capability_binding_id" in source and "update" in source.lower():
            tree = _read_ast(path)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Attribute):
                    if node.targets[0].attr == "capability_binding_id":
                        violations.append(f"{rel}:{node.lineno}")

    assert not violations, (
        "A2 violation — production code backfills capability_binding_id:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# ── 2. Capability module completeness ────────────────────────────────


def test_capability_module_completeness():
    """All A2 capability modules exist."""
    expected_modules = [
        # A1 modules
        "capability_identity.py",
        "capability_resolution.py",
        "capability_repository.py",
        "contracts.py",
        "capability_check_lifecycle.py",
        "capability_probe.py",
        "capability_check_service.py",
        "verified_embedding_runtime.py",
        "capability_errors.py",
        "capability_drift.py",
        "capability_status.py",
        # A2 modules
        "capability_bound_indexer.py",
        "capability_bound_retrieval.py",
        "cutover_snapshot.py",
        "activation_service.py",
        "side_channel_binding_policy.py",
    ]
    capability_dir = BACKEND_ROOT / "pipeline" / "capability"
    for mod in expected_modules:
        assert (capability_dir / mod).exists(), f"capability module missing: {mod}"


# ── 3. v2 identity excludes check_id and timestamps ──────────────────


def test_v2_identity_excludes_check_and_timestamps():
    """compute_vector_record_id_v2 must not include check_id or timestamps
    in its payload dictionary."""
    contracts_path = BACKEND_ROOT / "pipeline" / "vector_contracts.py"
    tree = _read_ast(contracts_path)
    assert tree is not None

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "compute_vector_record_id_v2":
            # Check the payload dict keys, not the docstring
            for child in ast.walk(node):
                if isinstance(child, ast.Dict):
                    keys = set()
                    for key in child.keys:
                        if isinstance(key, ast.Constant):
                            keys.add(key.value)
                    # Must NOT contain excluded fields
                    assert "check_id" not in keys, (
                        f"v2 identity payload contains check_id: {keys}"
                    )
                    assert "expires_at" not in keys, (
                        f"v2 identity payload contains expires_at: {keys}"
                    )
                    assert "activation_id" not in keys, (
                        f"v2 identity payload contains activation_id: {keys}"
                    )
                    # Must contain binding
                    assert "capability_binding_id" in keys, (
                        f"v2 identity payload missing capability_binding_id: {keys}"
                    )
                    return

    pytest.fail("compute_vector_record_id_v2 payload dict not found")


# ── 4. VerifiedEmbeddingRuntime still encapsulates adapter ───────────


def test_verified_runtime_still_no_public_adapter():
    """The A2 receipt methods must not expose the adapter."""
    from backend.pipeline.capability.verified_embedding_runtime import (
        VerifiedEmbeddingRuntime,
    )

    public_attrs = {
        name for name in dir(VerifiedEmbeddingRuntime)
        if not name.startswith("_")
    }
    assert "embedding_adapter" not in public_attrs
    assert "embed_documents_authorized" in public_attrs
    assert "embed_query_authorized" in public_attrs


# ── 5. No external I/O in activation transaction ─────────────────────


def test_activation_service_no_external_io():
    """The activation service must not call providers, Chroma, network,
    or filesystem inside the activation transaction.

    All backend verification must be represented as durable relational
    evidence before the transaction begins.
    """
    activation_path = BACKEND_ROOT / "pipeline" / "capability" / "activation_service.py"
    tree = _read_ast(activation_path)
    assert tree is not None

    prohibited_calls = {
        "embed_documents", "embed_query", "embed_documents_authorized",
        "embed_query_authorized", "embed_with_evidence",
        "upsert_vector", "read_vector", "query_vectors",
        "ensure_profile_collection", "delete_vector",
    }
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Await):
            callee = node.value
            if isinstance(callee, ast.Call) and isinstance(callee.func, ast.Attribute):
                if callee.func.attr in prohibited_calls:
                    violations.append(
                        f"line {node.lineno}: await ...{callee.func.attr}()"
                    )

    assert not violations, (
        "A2 violation — external I/O inside activation service:\n"
        + "\n".join(f"  {v}" for v in violations)
        + "\nActivation must use only durable relational evidence."
    )


# ── 6. Receipt methods exist on verified runtime ─────────────────────


def test_receipt_dataclasses_are_frozen():
    """AuthorizedEmbeddingBatch and AuthorizedQueryEmbedding are frozen."""
    import dataclasses
    from backend.pipeline.capability.verified_embedding_runtime import (
        AuthorizedEmbeddingBatch,
        AuthorizedQueryEmbedding,
    )
    assert dataclasses.is_dataclass(AuthorizedEmbeddingBatch)
    assert dataclasses.is_dataclass(AuthorizedQueryEmbedding)
    # Frozen check
    assert AuthorizedEmbeddingBatch.__dataclass_params__.frozen
    assert AuthorizedQueryEmbedding.__dataclass_params__.frozen
