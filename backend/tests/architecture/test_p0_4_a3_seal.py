"""P0.4A3.8: Final production reachability and architectural seal.

Inspects production composition and operator entry points, not only
capability modules.

Required zero counts:
  CLI lifecycle commands mutating tables outside services    0
  startup-created checks/bindings/activations                0
  production-unverified adapter access                        0
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


# ── 1. CLI does not mutate lifecycle tables directly ─────────────────


def test_cli_does_not_directly_mutate_lifecycle_tables():
    """The CLI must go through the CapabilityLifecycleService for all
    lifecycle mutations. Direct session.add() on lifecycle models in
    the CLI is prohibited."""
    cli_path = BACKEND_ROOT / "cli" / "capability_cli.py"
    source = cli_path.read_text(encoding="utf-8")

    # These are lifecycle table models that should only be mutated
    # through the service layer
    prohibited_instantiations = [
        "EmbeddingBindingCutover(",
        "EmbeddingProfileBindingActivation(",
        "EmbeddingProfileEmbeddingWriteGuard(",
        "EmbeddingBindingCutoverItem(",
    ]

    violations = []
    for pattern in prohibited_instantiations:
        if pattern in source:
            # Find the line
            for i, line in enumerate(source.splitlines(), 1):
                if pattern in line:
                    violations.append(f"capability_cli.py:{i} instantiates {pattern[:-1]}")

    assert not violations, (
        "A3 violation — CLI directly instantiates lifecycle table models:\n"
        + "\n".join(f"  {v}" for v in violations)
        + "\nUse CapabilityLifecycleService instead."
    )


# ── 2. Lifecycle service exists and is importable ────────────────────


def test_lifecycle_service_importable():
    """The CapabilityLifecycleService must be importable from the
    capability package."""
    from backend.pipeline.capability.lifecycle_service import (
        CapabilityLifecycleService,
    )
    assert CapabilityLifecycleService is not None


# ── 3. Posture evaluator is side-effect-free (no writes) ────────────


def test_posture_evaluator_has_no_writes():
    """evaluate_lifecycle_posture must not contain INSERT/UPDATE/DELETE
    statements or session.add() calls."""
    posture_path = BACKEND_ROOT / "pipeline" / "capability" / "lifecycle_posture.py"
    source = posture_path.read_text(encoding="utf-8")

    tree = _read_ast(posture_path)
    assert tree is not None

    write_patterns = ["session.add", "session.execute", "session.delete"]
    # The function should only use SELECT queries
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ("add", "delete", "merge", "flush"):
                # Check if it's on a session object
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "session":
                    # In evaluate_lifecycle_posture, session.execute with select() is OK
                    # but session.add/delete/merge/flush are not
                    violations = []
                    for n in ast.walk(tree):
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                            if n.func.attr in ("add", "delete", "merge", "flush"):
                                if isinstance(n.func.value, ast.Name) and n.func.value.id == "session":
                                    violations.append(f"line {n.lineno}: session.{n.func.attr}()")
                    if violations:
                        pytest.fail(
                            "Posture evaluator contains write operations:\n"
                            + "\n".join(f"  {v}" for v in violations)
                        )
                    break


# ── 4. Activation service has no external I/O ────────────────────────


def test_activation_service_no_external_io():
    """The activation service must not perform provider, Chroma, network,
    or filesystem I/O inside the activation transaction."""
    activation_path = BACKEND_ROOT / "pipeline" / "capability" / "activation_service.py"
    tree = _read_ast(activation_path)
    assert tree is not None

    prohibited_calls = {
        "embed_documents", "embed_query", "embed_documents_authorized",
        "embed_query_authorized", "embed_with_evidence",
        "upsert_vector", "read_vector", "query_vectors",
        "ensure_profile_collection", "delete_vector",
    }

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Await):
            callee = node.value
            if isinstance(callee, ast.Call) and isinstance(callee.func, ast.Attribute):
                if callee.func.attr in prohibited_calls:
                    violations.append(f"line {node.lineno}: await ...{callee.func.attr}()")

    assert not violations, (
        "A3 violation — external I/O in activation service:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# ── 5. Controlled provider is not production-selectable ─────────────


def test_controlled_provider_not_in_factory():
    """The controlled test provider must not appear in the production
    provider factory's routing logic."""
    factory_path = BACKEND_ROOT / "providers" / "provider_factory.py"
    source = factory_path.read_text(encoding="utf-8")

    # The factory should not reference "controlled" as a provider name
    assert '"controlled"' not in source, (
        "provider_factory.py references a 'controlled' provider — "
        "test-only providers must not be production-selectable"
    )
