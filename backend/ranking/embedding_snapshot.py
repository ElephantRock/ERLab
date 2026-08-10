"""P1B.2: Immutable embedding snapshot for the ranking benchmark.

Implements Decision 1C: the official benchmark embedding snapshot is generated
ONCE through the governed path (EffectiveEmbeddingConfiguration →
VerifiedEmbeddingRuntime → authorized embeddings) and then frozen. Every
policy comparison runs against the frozen snapshot.

Frozen definition of "deterministic replay" (Decision 1C):

    Given the same benchmark definition, relevance judgments, configuration,
    ranking policy, and embedding-snapshot fingerprint, ranking outputs and
    evaluation metrics must be exactly reproducible. It does NOT mean
    repeated external-provider calls return byte-identical vectors.

Replay integrity (Decision 1C): loading a snapshot MUST FAIL — never silently
regenerate — when any of these conditions holds:

    candidate text hash differs
    query text hash differs
    binding evidence differs
    dimension differs
    normalization contract differs
    vector artifact fingerprint differs
    benchmark fingerprint differs

Snapshot format
---------------
A snapshot is a single JSON file plus a sidecar manifest. The JSON holds
metadata + vectors (tuples of floats). The sidecar ``.fingerprint`` file
holds the canonical SHA-256 over the deterministic payload, so a snapshot
directory is self-verifying.

Layout::

    <snapshot_dir>/
      snapshot.json           # metadata + per-item vectors
      snapshot.fingerprint    # canonical SHA-256 of the deterministic payload

The snapshot.json is written once and is conceptually immutable; the
fingerprint sidecar lets a reader detect any tampering with vectors or
metadata without re-running the provider.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SNAPSHOT_SCHEMA_VERSION = "ranking_embedding_snapshot_v1"


class SnapshotIntegrityError(Exception):
    """Raised when a snapshot fails an integrity check on load."""


# ── Canonical text hashing (must match the benchmark's content_hash scheme) ──


def canonical_text_hash(text: str) -> str:
    """SHA-256 of the exact UTF-8 bytes of the canonical text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def vector_fingerprint(vec: Sequence[float]) -> str:
    """Deterministic fingerprint of a single vector.

    Uses a fixed-precision (9 decimal places) string representation so that
    the fingerprint is stable across JSON round-trips and platforms, while
    still detecting any actual value change.
    """
    return hashlib.sha256(
        "|".join(f"{x:.9f}" for x in vec).encode("ascii")
    ).hexdigest()


# ── Snapshot data model ──────────────────────────────────────────────


@dataclass(frozen=True)
class SnapshotItem:
    """One embedded item (query or candidate).

    ``item_role`` is ``query`` or ``candidate``. ``text`` is the canonical
    embedded text (NOT stored in the on-disk payload — only its hash is — to
    keep the snapshot small and to avoid re-embedding on text drift). The
    in-memory object carries text for convenience; the on-disk form stores
    only the hash.
    """

    item_id: str           # case_id for queries; candidate_id for candidates
    item_role: str         # "query" | "candidate"
    canonical_text: str
    text_hash: str
    vector: tuple[float, ...]
    vector_fingerprint: str


@dataclass(frozen=True)
class EmbeddingSnapshot:
    """An in-memory embedding snapshot."""

    snapshot_schema_version: str
    benchmark_version: str
    benchmark_fingerprint: str
    capability_binding_id: str
    capability_check_id: str
    generation_runtime_fingerprint: str
    provider_kind: str
    provider_model: str
    provider_revision: str | None
    endpoint_identity: str
    deployment_id: str | None
    embedding_contract_version: str
    dimension: int
    normalization_policy: str
    items: tuple[SnapshotItem, ...]
    created_at: str          # ISO 8601 UTC
    # Complete snapshot fingerprint (over the deterministic payload).
    snapshot_fingerprint: str

    def queries(self) -> tuple[SnapshotItem, ...]:
        return tuple(i for i in self.items if i.item_role == "query")

    def candidates(self) -> tuple[SnapshotItem, ...]:
        return tuple(i for i in self.items if i.item_role == "candidate")

    def get(self, item_id: str) -> SnapshotItem | None:
        for i in self.items:
            if i.item_id == item_id:
                return i
        return None


# ── Deterministic payload for fingerprinting ─────────────────────────


def _metadata_payload(
    *,
    snapshot_schema_version: str,
    benchmark_version: str,
    benchmark_fingerprint: str,
    capability_binding_id: str,
    capability_check_id: str,
    generation_runtime_fingerprint: str,
    provider_kind: str,
    provider_model: str,
    provider_revision: str | None,
    endpoint_identity: str,
    deployment_id: str | None,
    embedding_contract_version: str,
    dimension: int,
    normalization_policy: str,
    items: Sequence[SnapshotItem],
) -> dict[str, Any]:
    """Build the deterministic dict that the snapshot fingerprint covers.

    DELIBERATELY EXCLUDES:
      - created_at (wall-clock; not deterministic across regenerations)
      - the embedding text itself (only its hash; text drift is caught by
        the hash, and storing text would bloat the fingerprint input)

    INCLUDES (every field that, if changed, must invalidate replay):
      - schema + benchmark versions + benchmark fingerprint
      - full binding evidence (binding id, check id, runtime fingerprint,
        provider/model/revision, endpoint, deployment, contract version,
        dimension, normalization)
      - per-item (item_id, role, text_hash, vector_fingerprint) in sorted
        order so the fingerprint is order-independent
    """
    item_entries = sorted(
        (
            {
                "item_id": i.item_id,
                "item_role": i.item_role,
                "text_hash": i.text_hash,
                "vector_fingerprint": i.vector_fingerprint,
            }
            for i in items
        ),
        key=lambda e: (e["item_role"], e["item_id"]),
    )
    return {
        "snapshot_schema_version": snapshot_schema_version,
        "benchmark_version": benchmark_version,
        "benchmark_fingerprint": benchmark_fingerprint,
        "capability_binding_id": capability_binding_id,
        "capability_check_id": capability_check_id,
        "generation_runtime_fingerprint": generation_runtime_fingerprint,
        "provider_kind": provider_kind,
        "provider_model": provider_model,
        "provider_revision": provider_revision,
        "endpoint_identity": endpoint_identity,
        "deployment_id": deployment_id,
        "embedding_contract_version": embedding_contract_version,
        "dimension": dimension,
        "normalization_policy": normalization_policy,
        "items": item_entries,
    }


def compute_snapshot_fingerprint(
    *,
    snapshot_schema_version: str,
    benchmark_version: str,
    benchmark_fingerprint: str,
    capability_binding_id: str,
    capability_check_id: str,
    generation_runtime_fingerprint: str,
    provider_kind: str,
    provider_model: str,
    provider_revision: str | None,
    endpoint_identity: str,
    deployment_id: str | None,
    embedding_contract_version: str,
    dimension: int,
    normalization_policy: str,
    items: Sequence[SnapshotItem],
) -> str:
    payload = _metadata_payload(
        snapshot_schema_version=snapshot_schema_version,
        benchmark_version=benchmark_version,
        benchmark_fingerprint=benchmark_fingerprint,
        capability_binding_id=capability_binding_id,
        capability_check_id=capability_check_id,
        generation_runtime_fingerprint=generation_runtime_fingerprint,
        provider_kind=provider_kind,
        provider_model=provider_model,
        provider_revision=provider_revision,
        endpoint_identity=endpoint_identity,
        deployment_id=deployment_id,
        embedding_contract_version=embedding_contract_version,
        dimension=dimension,
        normalization_policy=normalization_policy,
        items=items,
    )
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


# ── Writer ───────────────────────────────────────────────────────────


@dataclass
class SnapshotBindingEvidence:
    """Evidence captured from a governed capability binding at generation time."""

    capability_binding_id: str
    capability_check_id: str
    generation_runtime_fingerprint: str
    provider_kind: str
    provider_model: str
    provider_revision: str | None
    endpoint_identity: str
    deployment_id: str | None
    embedding_contract_version: str
    dimension: int
    normalization_policy: str


def write_snapshot(
    snapshot_dir: Path,
    *,
    benchmark_version: str,
    benchmark_fingerprint: str,
    binding: SnapshotBindingEvidence,
    items: Sequence[SnapshotItem],
    created_at: datetime | None = None,
) -> Path:
    """Write an immutable snapshot to ``snapshot_dir``.

    The snapshot fingerprint is computed from the deterministic payload
    (excluding wall-clock ``created_at``) and written to both snapshot.json
    (under ``snapshot_fingerprint``) and a sidecar ``snapshot.fingerprint``.

    Returns the path to snapshot.json.

    Raises if ``snapshot_dir`` already contains a snapshot (refuses to
    overwrite an approved snapshot — call clear_snapshot_dir first).
    """
    snapshot_dir = Path(snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    json_path = snapshot_dir / "snapshot.json"
    fp_path = snapshot_dir / "snapshot.fingerprint"
    if json_path.exists() or fp_path.exists():
        raise SnapshotIntegrityError(
            f"snapshot already exists in {snapshot_dir}; refusing to overwrite "
            f"an approved snapshot. Remove it explicitly first."
        )

    ts = (created_at or datetime.now(UTC)).isoformat()

    snapshot_fp = compute_snapshot_fingerprint(
        snapshot_schema_version=SNAPSHOT_SCHEMA_VERSION,
        benchmark_version=benchmark_version,
        benchmark_fingerprint=benchmark_fingerprint,
        capability_binding_id=binding.capability_binding_id,
        capability_check_id=binding.capability_check_id,
        generation_runtime_fingerprint=binding.generation_runtime_fingerprint,
        provider_kind=binding.provider_kind,
        provider_model=binding.provider_model,
        provider_revision=binding.provider_revision,
        endpoint_identity=binding.endpoint_identity,
        deployment_id=binding.deployment_id,
        embedding_contract_version=binding.embedding_contract_version,
        dimension=binding.dimension,
        normalization_policy=binding.normalization_policy,
        items=items,
    )

    # On-disk payload. Vectors are stored as lists of floats (JSON-native).
    # Text is NOT stored — only text_hash — to keep the snapshot compact and
    # to make text drift detectable only via the hash mismatch.
    payload = {
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "benchmark_version": benchmark_version,
        "benchmark_fingerprint": benchmark_fingerprint,
        "capability_binding_id": binding.capability_binding_id,
        "capability_check_id": binding.capability_check_id,
        "generation_runtime_fingerprint": binding.generation_runtime_fingerprint,
        "provider_kind": binding.provider_kind,
        "provider_model": binding.provider_model,
        "provider_revision": binding.provider_revision,
        "endpoint_identity": binding.endpoint_identity,
        "deployment_id": binding.deployment_id,
        "embedding_contract_version": binding.embedding_contract_version,
        "dimension": binding.dimension,
        "normalization_policy": binding.normalization_policy,
        "created_at": ts,
        "snapshot_fingerprint": snapshot_fp,
        "items": [
            {
                "item_id": i.item_id,
                "item_role": i.item_role,
                "text_hash": i.text_hash,
                "vector": list(i.vector),
                "vector_fingerprint": i.vector_fingerprint,
            }
            for i in items
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    fp_path.write_text(snapshot_fp, encoding="utf-8")
    return json_path


# ── Reader ───────────────────────────────────────────────────────────


def load_snapshot(
    snapshot_dir: Path,
    *,
    expected_benchmark_fingerprint: str,
    expected_benchmark_version: str,
) -> EmbeddingSnapshot:
    """Load and fully verify an embedding snapshot.

    Performs every Decision 1C replay-must-fail check:

      1. snapshot.json + snapshot.fingerprint both present
      2. sidecar fingerprint matches snapshot_fingerprint field
      3. recomputed fingerprint over the deterministic payload matches
      4. benchmark_fingerprint matches expected_benchmark_fingerprint
      5. benchmark_version matches expected_benchmark_version
      6. every item's vector_fingerprint matches its stored vector
      7. dimension is consistent across all items and metadata
      8. normalization policy is non-empty
      9. capability binding evidence is complete (binding_id, check_id,
         runtime_fingerprint, provider, model, dimension, normalization,
         contract version all present)

    Raises ``SnapshotIntegrityError`` on any failure. NEVER silently
    regenerates a missing or mismatched vector.
    """
    snapshot_dir = Path(snapshot_dir)
    json_path = snapshot_dir / "snapshot.json"
    fp_path = snapshot_dir / "snapshot.fingerprint"

    if not json_path.exists():
        raise SnapshotIntegrityError(f"missing {json_path}")
    if not fp_path.exists():
        raise SnapshotIntegrityError(f"missing {fp_path}")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    sidecar_fp = fp_path.read_text(encoding="utf-8").strip()

    # Check 1: schema version
    schema_version = payload.get("snapshot_schema_version")
    if schema_version != SNAPSHOT_SCHEMA_VERSION:
        raise SnapshotIntegrityError(
            f"snapshot_schema_version mismatch: {schema_version!r} != {SNAPSHOT_SCHEMA_VERSION!r}"
        )

    # Check 2: benchmark version + fingerprint (text drift is caught here)
    if payload.get("benchmark_version") != expected_benchmark_version:
        raise SnapshotIntegrityError(
            f"benchmark_version mismatch: {payload.get('benchmark_version')!r} "
            f"!= {expected_benchmark_version!r}"
        )
    if payload.get("benchmark_fingerprint") != expected_benchmark_fingerprint:
        raise SnapshotIntegrityError(
            "benchmark_fingerprint mismatch: snapshot was generated for a "
            "different benchmark freeze"
        )

    # Check 3: capability binding evidence completeness
    binding_fields = (
        "capability_binding_id",
        "capability_check_id",
        "generation_runtime_fingerprint",
        "provider_kind",
        "provider_model",
        "embedding_contract_version",
        "endpoint_identity",
        "dimension",
        "normalization_policy",
    )
    missing_binding = [f for f in binding_fields if not payload.get(f)]
    if missing_binding:
        raise SnapshotIntegrityError(
            f"incomplete binding evidence; missing/empty: {missing_binding}"
        )

    dimension = int(payload["dimension"])
    normalization = payload["normalization_policy"]

    # Check 4: every item's vector_fingerprint matches its stored vector,
    # and dimensions are consistent.
    items: list[SnapshotItem] = []
    for raw in payload.get("items", []):
        vec = tuple(float(x) for x in raw["vector"])
        if len(vec) != dimension:
            raise SnapshotIntegrityError(
                f"item {raw.get('item_id')}: vector dimension {len(vec)} != "
                f"metadata dimension {dimension}"
            )
        recomputed_vfp = vector_fingerprint(vec)
        if recomputed_vfp != raw.get("vector_fingerprint"):
            raise SnapshotIntegrityError(
                f"item {raw.get('item_id')}: vector_fingerprint mismatch "
                f"(stored vector was modified)"
            )
        items.append(
            SnapshotItem(
                item_id=raw["item_id"],
                item_role=raw["item_role"],
                canonical_text="",  # text not stored on disk
                text_hash=raw["text_hash"],
                vector=vec,
                vector_fingerprint=recomputed_vfp,
            )
        )

    # Check 5: recompute the canonical snapshot fingerprint over the
    # deterministic payload and confirm it matches both the embedded field
    # and the sidecar file.
    recomputed_snapshot_fp = compute_snapshot_fingerprint(
        snapshot_schema_version=schema_version,
        benchmark_version=payload["benchmark_version"],
        benchmark_fingerprint=payload["benchmark_fingerprint"],
        capability_binding_id=payload["capability_binding_id"],
        capability_check_id=payload["capability_check_id"],
        generation_runtime_fingerprint=payload["generation_runtime_fingerprint"],
        provider_kind=payload["provider_kind"],
        provider_model=payload["provider_model"],
        provider_revision=payload.get("provider_revision"),
        endpoint_identity=payload["endpoint_identity"],
        deployment_id=payload.get("deployment_id"),
        embedding_contract_version=payload["embedding_contract_version"],
        dimension=dimension,
        normalization_policy=normalization,
        items=items,
    )
    embedded_fp = payload.get("snapshot_fingerprint")
    if recomputed_snapshot_fp != embedded_fp:
        raise SnapshotIntegrityError(
            "snapshot_fingerprint mismatch: recomputed fingerprint does not "
            "match the embedded field (metadata or vectors were modified)"
        )
    if recomputed_snapshot_fp != sidecar_fp:
        raise SnapshotIntegrityError(
            "sidecar fingerprint mismatch: snapshot.fingerprint does not "
            "match the recomputed snapshot fingerprint"
        )

    return EmbeddingSnapshot(
        snapshot_schema_version=schema_version,
        benchmark_version=payload["benchmark_version"],
        benchmark_fingerprint=payload["benchmark_fingerprint"],
        capability_binding_id=payload["capability_binding_id"],
        capability_check_id=payload["capability_check_id"],
        generation_runtime_fingerprint=payload["generation_runtime_fingerprint"],
        provider_kind=payload["provider_kind"],
        provider_model=payload["provider_model"],
        provider_revision=payload.get("provider_revision"),
        endpoint_identity=payload["endpoint_identity"],
        deployment_id=payload.get("deployment_id"),
        embedding_contract_version=payload["embedding_contract_version"],
        dimension=dimension,
        normalization_policy=normalization,
        items=tuple(items),
        created_at=payload.get("created_at", ""),
        snapshot_fingerprint=recomputed_snapshot_fp,
    )


def clear_snapshot_dir(snapshot_dir: Path) -> None:
    """Explicitly remove an existing snapshot (must be intentional)."""
    snapshot_dir = Path(snapshot_dir)
    for fn in ("snapshot.json", "snapshot.fingerprint"):
        p = snapshot_dir / fn
        if p.exists():
            p.unlink()
