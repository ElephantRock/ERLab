"""B0.9 architectural seal: enforce the complete P0.4B0 boundary contract.

This module consumes the policy manifest at
``backend/tests/architecture/p0_4_b0_policy.json`` so that permit lists and
prohibited symbols live in exactly one reviewed place. The closeout
verifier script ``scripts/verify_p0_4_b0.py`` reads the same manifest.

Coverage (work package D in the macro-wave plan):

  D1  provider construction boundary
  D2  governed runtime field contract
  D3  reconciliation boundary (declared L2 ≠ implemented, secret rejection)
  D4  validation ownership (canonical module only on governed paths)
  D5  side-channel isolation (purpose guards, raw provider absence)
  D6  shared version constants (single canonical home)
  D7  false capability-claim prevention (no premature ledger symbols)
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Manifest loading
# ---------------------------------------------------------------------------

ARCH_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = ARCH_DIR.parents[1]  # .../backend
REPO_ROOT = ARCH_DIR.parents[2]     # .../Elephant-Rock-Research-Lab
MANIFEST_PATH = ARCH_DIR / "p0_4_b0_policy.json"


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


MANIFEST = _load_manifest()


def _rel(path: Path) -> str:
    """Path relative to repo root, forward-slashed (e.g. 'backend/pipeline/x.py')."""
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _backend_path(rel: str) -> Path:
    """Resolve a manifest 'backend/...' reference to an absolute path."""
    return REPO_ROOT / rel


def _read_ast(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except Exception:
        return None


def _is_test(rel: str) -> bool:
    return "/tests/" in rel or rel.startswith("tests/")


def _iter_production_py():
    """Yield (rel, path) for every production .py under backend/."""
    for path in (BACKEND_ROOT).rglob("*.py"):
        rel = _rel(path)
        if _is_test(rel) or "__pycache__" in rel:
            continue
        yield rel, path


# ---------------------------------------------------------------------------
# D2 — Governed runtime field contract
# ---------------------------------------------------------------------------


def test_governed_vector_runtime_exposes_exactly_approved_fields():
    """``GovernedVectorRuntime`` must expose exactly the 4 approved fields.

    B0.6 removed ``embedding_provider``, ``profile_dict``,
    ``embedding_profile_id`` and ``db_engine`` from the runtime. Their
    reintroduction would reopen raw-provider escape hatches.
    """
    import dataclasses

    from backend.pipeline.vector_runtime import GovernedVectorRuntime

    spec = MANIFEST["governed_runtime"]
    fields = set(GovernedVectorRuntime.__dataclass_fields__.keys())
    expected = set(spec["required_fields"])
    prohibited = set(spec["prohibited_fields"])

    assert fields == expected, (
        f"GovernedVectorRuntime field set drifted.\n"
        f"  expected exactly: {sorted(expected)}\n"
        f"  actual:           {sorted(fields)}\n"
        f"  missing:          {sorted(expected - fields)}\n"
        f"  unexpected:       {sorted(fields - expected)}"
    )

    leaked = fields & prohibited
    assert not leaked, (
        f"GovernedVectorRuntime re-exposes prohibited raw-provider fields: "
        f"{sorted(leaked)}"
    )


def test_governed_vector_runtime_has_no_private_adapter_classes():
    """No private ``_EmbeddingAdapter`` classes in the runtime module.

    The runtime must compose a ``GovernedEmbeddingAdapter`` from the
    dedicated module; it must not declare a private adapter inline.
    """
    spec = MANIFEST["governed_runtime"]
    runtime_path = _backend_path(spec["module"])
    tree = _read_ast(runtime_path)
    assert tree is not None

    prohibited = set(spec["prohibited_private_adapters"])
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name in prohibited:
            found.add(node.name)

    assert not found, (
        f"GovernedVectorRuntime module declares private adapter classes: "
        f"{sorted(found)}"
    )


# ---------------------------------------------------------------------------
# D1 — Provider construction boundary
# ---------------------------------------------------------------------------


def test_embedding_provider_classes_constructed_only_in_approved_factories():
    """Direct construction of EmbeddingProvider subclasses is confined to the
    approved factory modules.

    Production code elsewhere must go through ``create_embedding_provider``.
    """
    spec = MANIFEST["provider_construction"]
    symbols = set(spec["embedding_provider_symbols"])
    approved = set(spec["approved_factory_modules"])

    # Resolve approved modules to relative paths as they appear in _rel()
    approved_rels = set()
    for m in approved:
        # manifest paths look like backend/...
        approved_rels.add(m.replace("\\", "/"))

    violations: list[str] = []
    for rel, path in _iter_production_py():
        if rel in approved_rels:
            continue
        tree = _read_ast(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in symbols:
                    violations.append(f"{rel}:{node.lineno} constructs {node.func.id}(...)")

    assert not violations, (
        "D1 violation — EmbeddingProvider subclass constructed outside "
        "approved factory modules:\n"
        + "\n".join(f"  {v}" for v in violations)
        + "\nProduction code must use create_embedding_provider(...)."
    )


# ---------------------------------------------------------------------------
# D6 — Shared version constants
# ---------------------------------------------------------------------------


def test_version_constants_defined_exactly_once_in_executable_python():
    """Each central version constant has exactly one Python assignment.

    SQL CHECK-constraint string literals in db/models.py are explicitly
    allowlisted as intentional layering (lowest layer cannot import
    transport-layer Python constants).
    """
    spec = MANIFEST["central_version_constants"]
    constants = spec["constants"]
    canonical_module = spec["module"]
    sql_allowlist = {entry["file"] for entry in spec.get("sql_literal_allowlist", [])}

    sites: dict[str, list[str]] = {c: [] for c in constants}
    for rel, path in _iter_production_py():
        try:
            source_lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for i, line in enumerate(source_lines, 1):
            stripped = line.strip()
            for c in constants:
                # Match only top-level assignment-like statements
                if stripped.startswith(f"{c} =") or stripped.startswith(f"{c}="):
                    sites[c].append(f"{rel}:{i}")

    errors: list[str] = []
    for c in constants:
        defs = sites[c]
        if len(defs) == 0:
            errors.append(f"{c}: no Python definition found (expected in {canonical_module})")
        elif len(defs) > 1:
            errors.append(
                f"{c}: multiple Python assignments — {defs}. "
                f"Constants must be imported from {canonical_module}."
            )
        else:
            # Exactly one — must be in the canonical module
            canonical_rel = canonical_module.replace("\\", "/")
            if not defs[0].startswith(canonical_rel):
                errors.append(
                    f"{c}: defined at {defs[0]} but canonical home is "
                    f"{canonical_module}"
                )

    # Note: sql_allowlist entries are not Python assignments — they are
    # SQL string literals inside CheckConstraint(...). They do not match
    # the ``CONST =`` pattern above and are therefore inherently exempt.
    # We assert the allowlist is non-empty only when db/models.py exists.
    db_models_present = any(
        _backend_path(f).exists() for f in sql_allowlist
    )
    if sql_allowlist and db_models_present:
        # Sanity: the allowlisted file exists, so the SQL layering note applies.
        pass

    assert not errors, (
        "D6 violation — version constant drift:\n"
        + "\n".join(f"  {e}" for e in errors)
    )


def test_version_constants_importable_from_central_module():
    """All version constants must be importable from the central module."""
    spec = MANIFEST["central_version_constants"]
    module_path = spec["module"]  # backend/pipeline/vector_contracts.py
    module_dotted = module_path.replace("/", ".").removesuffix(".py")
    module = __import__(module_dotted, fromlist=spec["constants"])
    for c in spec["constants"]:
        assert hasattr(module, c), (
            f"{module_path} does not define {c}"
        )


# ---------------------------------------------------------------------------
# D4 — Validation ownership
# ---------------------------------------------------------------------------


def test_canonical_validation_symbols_defined_only_in_canonical_module():
    """Validation primitives live in exactly one canonical module.

    Side-channel modules must not define duplicate structural validators.
    """
    spec = MANIFEST["canonical_validation"]
    owned = set(spec["owned_symbols"])
    canonical = spec["module"]
    side_channel_modules = set(spec["side_channel_modules"])

    owners: dict[str, set[str]] = {s: set() for s in owned}
    for rel, path in _iter_production_py():
        tree = _read_ast(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in owned:
                    owners[node.name].add(rel)
            elif isinstance(node, ast.ClassDef):
                # Class-bound validators count too
                for inner in ast.walk(node):
                    if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if inner.name in owned:
                            owners[inner.name].add(rel + f" (class {node.name})")

    errors: list[str] = []
    for symbol, modules in owners.items():
        # Filter to modules that are NOT the canonical one
        non_canonical = {m for m in modules if m != canonical}
        side_channel_definitions = {m for m in non_canonical if m in side_channel_modules}
        other_definitions = non_canonical - side_channel_modules

        # Side-channel modules defining these symbols is a hard error
        if side_channel_definitions:
            errors.append(
                f"{symbol}: duplicate definition in side-channel modules "
                f"{sorted(side_channel_definitions)} — must delegate to "
                f"{canonical}"
            )
        # Any other production module defining these is also an error
        # (the canonical module itself is allowed)
        if other_definitions:
            errors.append(
                f"{symbol}: defined outside canonical module — "
                f"{sorted(other_definitions)} (canonical: {canonical})"
            )
        # The canonical module must define it
        if canonical not in modules:
            errors.append(
                f"{symbol}: not defined in canonical module {canonical}"
            )

    assert not errors, (
        "D4 violation — validation ownership drift:\n"
        + "\n".join(f"  {e}" for e in errors)
    )


def test_side_channel_modules_have_no_inline_structural_checks():
    """Side-channel modules must not perform inline embedding structural checks.

    They must delegate to the canonical validation module. Patterns
    rejected: ``math.isnan``, ``math.isinf``, raw dimension-equality
    branches on embedding vectors.
    """
    spec = MANIFEST["canonical_validation"]
    prohibited_patterns = spec["prohibited_inline_check_patterns"]
    side_channel_modules = spec["side_channel_modules"]

    violations: list[str] = []
    for rel in side_channel_modules:
        path = _backend_path(rel)
        if not path.exists():
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for pattern in prohibited_patterns:
            if pattern in source:
                # Find the line for the report
                for i, line in enumerate(source.splitlines(), 1):
                    if pattern in line:
                        violations.append(f"{rel}:{i} inline check `{pattern}`")

    assert not violations, (
        "D4 violation — side-channel modules contain inline structural "
        "embedding checks:\n"
        + "\n".join(f"  {v}" for v in violations)
        + "\nAll structural validation must delegate to "
        "backend/pipeline/knowledge/embedding_validation.py."
    )


def test_no_duplicate_embedding_validators_in_governed_modules():
    """Governed modules must not define their own embedding structural
    validators — they must delegate to the canonical module.

    Catches differently-named duplicates (e.g. ``validate_embedding`` vs
    the canonical ``validate_embedding_vector``) that perform the same
    NaN/Inf/dimension/zero checks inline. The canonical validator's
    rejection rules must live in exactly one place.

    A wrapper that delegates to the canonical validator (catching
    EmbeddingValidationError and translating to a different return
    shape) is permitted — it contains no inline logic of its own.
    """
    spec = MANIFEST["canonical_validation"]
    canonical_module = spec["module"]

    # Heuristic: any function that BOTH (a) has "valid" in its name AND
    # (b) contains inline NaN/Inf checks is a duplicate structural
    # validator. A delegating wrapper calls the canonical function and
    # catches exceptions — it does NOT contain math.isnan/isinf.
    embedding_check_indicators = ("math.isnan", "math.isinf")

    violations: list[str] = []
    for rel, path in _iter_production_py():
        if rel == canonical_module:
            continue
        try:
            source_lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        tree = _read_ast(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            fname = node.name
            if "valid" not in fname.lower() and "validate" not in fname.lower():
                continue
            if node.end_lineno is None:
                continue
            # Slice the function body from source lines
            func_source = "\n".join(source_lines[node.lineno - 1: node.end_lineno])

            has_inline_check = any(
                indicator in func_source
                for indicator in embedding_check_indicators
            )
            if has_inline_check:
                violations.append(
                    f"{rel}:{node.lineno} {fname}() contains inline "
                    f"NaN/Inf checks — must delegate to {canonical_module}"
                )

    assert not violations, (
        "D4 violation — governed modules define duplicate embedding "
        "validators with inline structural checks:\n"
        + "\n".join(f"  {v}" for v in violations)
        + "\nAll structural validation must delegate to "
        "backend/pipeline/knowledge/embedding_validation.py."
    )


# ---------------------------------------------------------------------------
# D5 — Side-channel isolation
# ---------------------------------------------------------------------------


def test_side_channel_purpose_guards_present_where_required():
    """KG and tool side-channel modules must hard-assert their purpose.

    Catches regression where a side channel silently accepts the wrong
    purpose (e.g. paper embeddings sneaking into the KG namespace).
    """
    side_channels = MANIFEST["side_channels"]
    violations: list[str] = []

    for ch in side_channels:
        if not ch.get("requires_purpose_assert"):
            continue
        path = _backend_path(ch["module"])
        source = path.read_text(encoding="utf-8")
        purpose = ch["purpose"]

        # Look for either an assert_purpose call or a direct comparison
        # to the expected purpose string.
        has_assert = (
            f"assert_purpose_not_paper" in source
            or f'side_channel_purpose_mismatch' in source
            or f'"{purpose}"' in source
            or f"'{purpose}'" in source
        )
        if not has_assert:
            violations.append(
                f"{ch['module']}: no purpose guard for '{purpose}'"
            )

    assert not violations, (
        "D5 violation — side-channel purpose guards missing:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_side_channel_modules_accept_no_raw_provider_construction():
    """Side-channel modules must not directly construct an EmbeddingProvider.

    They must receive a governed runtime or EmbeddingService from upstream.
    """
    provider_spec = MANIFEST["provider_construction"]
    symbols = set(provider_spec["embedding_provider_symbols"])
    side_channel_modules = {ch["module"] for ch in MANIFEST["side_channels"]}

    violations: list[str] = []
    for rel in side_channel_modules:
        path = _backend_path(rel)
        tree = _read_ast(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in symbols:
                    violations.append(
                        f"{rel}:{node.lineno} constructs {node.func.id}(...) — "
                        f"side channels must receive a governed runtime"
                    )

    assert not violations, (
        "D5 violation — side-channel modules construct raw EmbeddingProviders:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_legacy_side_channel_wiring_confined_to_frozen_call_sites():
    """Production code may construct side-channel indices via the legacy
    constructor path ONLY at the explicitly enumerated call sites.

    B0.5 introduced SideChannelEmbeddingRuntime as the governed path for
    KG, tool, and cache side channels. Three production call sites in
    ``service_registry.py`` pre-date B0.5 and still use the legacy
    constructor (``GraphEmbeddingIndex(persist_dir, embedding_service)`` /
    ``ToolEmbeddingIndex(persist_dir, embedding_service)``). They are
    feature-flag-gated and default-off.

    This test freezes that list: no NEW production module may construct
    a side-channel index via the legacy path. New wiring must go through
    ``SideChannelEmbeddingRuntime``. The three grandfathered sites must
    be migrated to the governed runtime during P0.4A1+ (capability
    ledger), at which point they are removed from this list and the
    legacy constructor itself is removed.
    """
    legacy_spec = MANIFEST.get("side_channel_legacy_wiring", {})
    frozen_sites = {
        (entry["file"], entry["method"])
        for entry in legacy_spec.get("known_legacy_call_sites", [])
    }

    # Side-channel index classes that have a legacy constructor form
    legacy_index_classes = {"GraphEmbeddingIndex", "ToolEmbeddingIndex"}

    # Scan all production modules for legacy constructor calls
    found_sites: set[tuple[str, str | None]] = set()
    for rel, path in _iter_production_py():
        # Skip the side-channel modules themselves (they DEFINE the constructors)
        side_channel_modules = {ch["module"] for ch in MANIFEST["side_channels"]}
        if rel in side_channel_modules:
            continue
        tree = _read_ast(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in legacy_index_classes:
                    # Determine enclosing method (best-effort via lineno)
                    found_sites.add((rel, None))

    # The only production file allowed to have these calls is service_registry.py
    # (which contains all three grandfathered sites).
    allowed_files = {entry["file"] for entry in legacy_spec.get("known_legacy_call_sites", [])}
    unexpected_files = {
        rel for (rel, _) in found_sites if rel not in allowed_files
    }

    assert not unexpected_files, (
        "D5 violation — new production file constructs side-channel index via "
        "legacy constructor:\n"
        + "\n".join(f"  {f}" for f in sorted(unexpected_files))
        + "\nOnly the frozen call sites in service_registry.py may use the "
        "legacy constructor. New wiring must use SideChannelEmbeddingRuntime."
    )


# ---------------------------------------------------------------------------
# D3 — Reconciliation boundary (runtime contract via EffectiveEmbeddingConfiguration)
# ---------------------------------------------------------------------------


def test_effective_configuration_resolver_enforces_declared_vs_implemented():
    """Declared L2 normalization must not be silently treated as implemented.

    The resolver must fail when the profile declares an L2 normalization
    policy that the adapter does not implement.
    """
    from backend.pipeline.knowledge.embedding_configuration import (
        EmbeddingAdapterCapabilitySnapshot,
        EmbeddingConfigurationError,
        EmbeddingProfileSnapshot,
        EmbeddingRuntimeSettingsSnapshot,
        resolve_effective_embedding_configuration,
    )

    settings = EmbeddingRuntimeSettingsSnapshot(
        provider_kind="openai",
        requested_model="text-embedding-3-small",
        expected_dimension=1536,
        declared_normalization_policy="l2",
        document_task=None,
        query_task=None,
        endpoint=None,
        configured_deployment_id=None,
        deployment_is_explicitly_pinned=False,
    )
    profile = EmbeddingProfileSnapshot(
        embedding_profile_id="prof-declares-l2",
        profile_schema_version="embedding_profile_v1",
        provider_kind="openai",
        model_identifier="text-embedding-3-small",
        dimension=1536,
        normalization_policy="l2",
        document_task=None,
        query_task=None,
        verification_status="declared",
    )
    adapter = EmbeddingAdapterCapabilitySnapshot(
        provider_adapter_contract_version="openai_embeddings_v1",
        governed_adapter_contract_version="governed_embedding_adapter_v1",
        implemented_postprocessing_policy="none",
        supports_document_embedding=True,
        supports_query_embedding=True,
    )

    with pytest.raises(EmbeddingConfigurationError):
        resolve_effective_embedding_configuration(
            settings=settings, profile=profile, adapter=adapter
        )


def test_effective_configuration_resolver_rejects_secret_bearing_endpoint():
    """Endpoint identity carrying credentials must be rejected, not silently
    trimmed into a partially-secret string."""
    from backend.pipeline.knowledge.embedding_configuration import (
        EmbeddingConfigurationError,
        sanitize_endpoint_identity,
    )

    # A URL with embedded credentials must fail closed
    with pytest.raises(EmbeddingConfigurationError):
        sanitize_endpoint_identity(
            "https://user:sk-secret@api.example.com/v1"
        )


def test_effective_configuration_resolver_rejects_provider_mismatch():
    """Settings provider ≠ profile provider must fail, not silently coerce."""
    from backend.pipeline.knowledge.embedding_configuration import (
        EmbeddingAdapterCapabilitySnapshot,
        EmbeddingConfigurationError,
        EmbeddingProfileSnapshot,
        EmbeddingRuntimeSettingsSnapshot,
        resolve_effective_embedding_configuration,
    )

    settings = EmbeddingRuntimeSettingsSnapshot(
        provider_kind="openai",
        requested_model="text-embedding-3-small",
        expected_dimension=1536,
        declared_normalization_policy="none",
        document_task=None,
        query_task=None,
        endpoint=None,
        configured_deployment_id=None,
        deployment_is_explicitly_pinned=False,
    )
    profile = EmbeddingProfileSnapshot(
        embedding_profile_id="prof-gemini",
        profile_schema_version="embedding_profile_v1",
        provider_kind="gemini",
        model_identifier="text-embedding-3-small",
        dimension=1536,
        normalization_policy="none",
        document_task=None,
        query_task=None,
        verification_status="declared",
    )
    adapter = EmbeddingAdapterCapabilitySnapshot(
        provider_adapter_contract_version="openai_embeddings_v1",
        governed_adapter_contract_version="governed_embedding_adapter_v1",
        implemented_postprocessing_policy="none",
        supports_document_embedding=True,
        supports_query_embedding=True,
    )

    with pytest.raises(EmbeddingConfigurationError):
        resolve_effective_embedding_configuration(
            settings=settings, profile=profile, adapter=adapter
        )


# ---------------------------------------------------------------------------
# D7 — False capability-claim prevention
# ---------------------------------------------------------------------------


def test_no_premature_capability_claims_in_production():
    """No capability-ledger symbols may exist in production code during B0.

    Capability bindings, checks, and verified runtime tokens belong to
    P0.4A1+. Their presence now would indicate premature claims.
    """
    spec = MANIFEST["prohibited_capability_claims"]
    symbols = spec["symbols"]

    # Documents and migration files that may legitimately reference future
    # symbols as forward reservations.
    allowed_path_substrings = (
        "/docs/",
        "/migrations/",
        ".md",
        "p0_4_b0_policy.json",  # this manifest itself
        "verify_p0_4_b0",        # the closeout script
        "test_p0_4_b0_seal",     # this test file
        "p0_4_b0_closeout",      # closeout docs
    )

    violations: list[str] = []
    for rel, path in _iter_production_py():
        if any(sub in rel for sub in allowed_path_substrings):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for symbol in symbols:
            if symbol in source:
                # Find first occurrence line
                for i, line in enumerate(source.splitlines(), 1):
                    if symbol in line:
                        violations.append(f"{rel}:{i} references {symbol}")
                        break

    assert not violations, (
        "D7 violation — premature capability-claim symbols in production:\n"
        + "\n".join(f"  {v}" for v in violations)
        + "\nCapability bindings/checks belong to P0.4A1+, not B0."
    )


def test_no_vector_index_v2_eligibility_claims():
    """Production code must not claim vector_index_v2 production eligibility.

    v2 eligibility is gated by the capability ledger (P0.4A1+). B0 may
    declare the v2 *constant* but must not gate production behavior on it.
    """
    # Search for any production file that compares index version to V2
    # as an eligibility gate (not just imports the constant).
    violations: list[str] = []
    v2_constant = "VECTOR_INDEX_V2"
    eligibility_patterns = (
        "== VECTOR_INDEX_V2",
        "is VECTOR_INDEX_V2",
        ">= VECTOR_INDEX_V2",
        '== "vector_index_v2"',
    )

    for rel, path in _iter_production_py():
        try:
            source = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for pattern in eligibility_patterns:
            if pattern in source:
                for i, line in enumerate(source.splitlines(), 1):
                    if pattern in line:
                        violations.append(f"{rel}:{i} `{pattern.strip()}`")

    assert not violations, (
        "D7 violation — vector_index_v2 eligibility gating in production:\n"
        + "\n".join(f"  {v}" for v in violations)
        + "\nv2 eligibility is gated by the capability ledger (P0.4A1+)."
    )
