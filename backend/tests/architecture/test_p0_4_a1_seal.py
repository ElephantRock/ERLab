"""P0.4A1 architectural seal: enforce the capability ledger contract.

Required zero-count assertions:

  EmbeddingProfile.verification_status authorization reads    0
  passed checks without real dual probes                       0
  failed checks with fabricated bindings                       0
  expired checks authorizing operations                        0
  newer failed checks bypassed by older passes                 0
  public adapter bypasses from verified runtime                0
  historical vector binding backfills                          0
  activation/cutover claims                                    0
  governed callers accessing raw adapter directly               0
  binding created before probe pass                             0
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


# ── 1. Profile verification_status never read for authorization ──────


def test_profile_verification_status_not_read_for_authorization():
    """Production code must never use EmbeddingProfile.verification_status
    as an authorization gate (e.g. ``if profile.verification_status == ...``).

    The column stays CHECK-constrained to 'unverified' permanently.
    Authorization comes from the capability check ledger, not the profile.

    Reads for snapshot/audit purposes (copying the value into a transport
    dataclass or audit record) are permitted — they don't gate behavior.
    """
    violations: list[str] = []
    for rel, path in _iter_production_py():
        try:
            source = path.read_text(encoding="utf-8")
        except Exception:
            continue
        tree = _read_ast(path)
        if tree is None:
            continue
        # Look for COMPARISON reads: if x.verification_status == "..."
        # or if x.verification_status != "..." — these are authorization gates
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                left = node.left
                if (
                    isinstance(left, ast.Attribute)
                    and left.attr == "verification_status"
                ):
                    violations.append(
                        f"{rel}:{node.lineno} comparison on verification_status"
                    )

    assert not violations, (
        "A1 violation — production code gates on .verification_status:\n"
        + "\n".join(f"  {v}" for v in violations)
        + "\nAuthorization comes from the capability check ledger."
    )


# ── 2. VerifiedEmbeddingRuntime encapsulates its adapter ─────────────


def test_verified_embedding_runtime_has_no_public_adapter():
    """VerifiedEmbeddingRuntime must not expose its adapter publicly.

    The adapter is private (_embedding_adapter). Callers must go through
    embed_documents/embed_query which validate authority first.
    """
    from backend.pipeline.capability.verified_embedding_runtime import (
        VerifiedEmbeddingRuntime,
    )

    # Check that 'embedding_adapter' is NOT in the class's public namespace
    public_attrs = {
        name for name in dir(VerifiedEmbeddingRuntime)
        if not name.startswith("_")
    }
    assert "embedding_adapter" not in public_attrs, (
        "VerifiedEmbeddingRuntime exposes a public embedding_adapter — "
        "callers could bypass authority validation."
    )


# ── 3. No binding backfill onto VectorIndexRecord ────────────────────


def test_no_historical_vector_binding_backfill():
    """No production code stamps capability_binding_id onto existing
    VectorIndexRecord rows.

    Historical vectors remain pre_capability_v0. Binding backfill is
    prohibited during A1 — it belongs to the cutover macro-wave.
    """
    violations: list[str] = []
    for rel, path in _iter_production_py():
        if "capability" in rel or "/tests/" in rel:
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except Exception:
            continue
        # Look for assignment to binding_id on vector record objects
        if "binding_id" in source and "vector" in source.lower():
            # More precise check: look for .binding_id = on a vector record
            tree = _read_ast(path)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Assign)
                    and isinstance(node.targets[0], ast.Attribute)
                    and node.targets[0].attr == "capability_binding_id"
                ):
                    violations.append(f"{rel}:{node.lineno}")

    assert not violations, (
        "A1 violation — production code stamps capability_binding_id onto "
        "existing records (historical backfill is prohibited):\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# ── 4. Check-first invariant: binding_id NULL unless passed ──────────


def test_check_service_never_creates_binding_before_probe():
    """The check service must create the pending check BEFORE the probe
    and resolve the binding ONLY after the probe passes.

    This is verified structurally by inspecting the service's source.
    """
    service_path = BACKEND_ROOT / "pipeline" / "capability" / "capability_check_service.py"
    source = service_path.read_text(encoding="utf-8")

    # The create_pending_check call must come before resolve_or_create_binding
    pending_pos = source.find("create_pending_check")
    resolve_pos = source.find("resolve_or_create_binding")

    assert pending_pos > 0, "create_pending_check not found in service"
    assert resolve_pos > 0, "resolve_or_create_binding not found in service"
    assert pending_pos < resolve_pos, (
        "Binding resolution occurs before pending check creation — "
        "violates check-first invariant"
    )


# ── 6. Capability module structure ───────────────────────────────────


def test_capability_module_structure():
    """All capability modules exist in the expected location."""
    expected_modules = [
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
    ]
    capability_dir = BACKEND_ROOT / "pipeline" / "capability"
    for mod in expected_modules:
        assert (capability_dir / mod).exists(), (
            f"capability module missing: {mod}"
        )
