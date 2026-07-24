"""P1E.0 — Allowlisted P1B snapshot decoding.

Reviewer correction #2: the audit must access the P1B snapshot through a
cal+dev allowlist applied BEFORE item materialization. The full snapshot file
may be hashed as opaque bytes, but its held-out entries must never be decoded
or inspected.

This module provides ``load_snapshot_filtered``: it reads the on-disk
``snapshot.json``, reuses the original
``backend.ranking.embedding_snapshot`` integrity primitives
(``compute_snapshot_fingerprint`` and ``vector_fingerprint``) to verify the
SNAPSHOT-LEVEL fingerprint over the full deterministic payload (so a tampered
file is still caught), but then constructs ``SnapshotItem`` objects ONLY for
IDs in ``allowed_item_ids``. Items not in the allowlist are never decoded —
their vectors are never read into memory.

The original ``load_snapshot`` is left untouched (P1B/P1D keep their existing
behavior).

Integrity model
---------------
Two layers of verification:

1. FILE-LEVEL (opaque): the SHA-256 of the raw ``snapshot.json`` bytes is
   reported. Any change to the file — including held-out entries — changes
   this hash.

2. SNAPSHOT-LEVEL (deterministic payload): the original
   ``compute_snapshot_fingerprint`` is recomputed over the FULL item list as
   recorded on disk (using each item's stored ``vector_fingerprint`` — NOT by
   decoding the vector floats). This catches metadata/vector tampering
   without materializing vectors. It must match the embedded
   ``snapshot_fingerprint`` field and the sidecar.

3. ITEM-LEVEL (decoded items only): for every ALLOWED item, the decoded
   vector's ``vector_fingerprint`` must match its stored fingerprint. Held-out
   items never reach this check because they are never decoded.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from backend.ranking.embedding_snapshot import (
    SNAPSHOT_SCHEMA_VERSION,
    EmbeddingSnapshot,
    SnapshotIntegrityError,
    SnapshotItem,
    compute_snapshot_fingerprint,
    vector_fingerprint,
)


def _opaque_file_hash(path: Path) -> str:
    """SHA-256 of the raw file bytes — catches ANY change, without decoding."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_snapshot_filtered(
    snapshot_dir: Path,
    *,
    allowed_item_ids: frozenset[str],
    expected_benchmark_fingerprint: str,
    expected_benchmark_version: str,
) -> tuple[EmbeddingSnapshot, dict]:
    """Load the P1B snapshot, decoding ONLY allowed items.

    Returns ``(snapshot, integrity_report)``. The snapshot's ``items`` contain
    only allowed IDs. The integrity_report records the opaque file hash, the
    full-payload snapshot fingerprint, and per-decode counters so the audit
    can prove held-out vectors were never decoded.

    Raises ``SnapshotIntegrityError`` on any integrity failure, including an
    attempt to decode a held-out item.
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
    opaque_hash = _opaque_file_hash(json_path)

    # ── Layer 1: schema version ──
    schema_version = payload.get("snapshot_schema_version")
    if schema_version != SNAPSHOT_SCHEMA_VERSION:
        raise SnapshotIntegrityError(
            f"snapshot_schema_version mismatch: {schema_version!r} != {SNAPSHOT_SCHEMA_VERSION!r}"
        )

    # ── Layer 1: benchmark version + fingerprint ──
    if payload.get("benchmark_version") != expected_benchmark_version:
        raise SnapshotIntegrityError("benchmark_version mismatch")
    if payload.get("benchmark_fingerprint") != expected_benchmark_fingerprint:
        raise SnapshotIntegrityError("benchmark_fingerprint mismatch")

    dimension = int(payload["dimension"])
    normalization = payload["normalization_policy"]

    # ── Layer 2: full-payload snapshot fingerprint using STORED vector_fingerprints.
    # Build SnapshotItem-like records for the fingerprint computation using the
    # STORED vector_fingerprint only — we do NOT decode vector floats here, so
    # held-out vectors are never materialized even for the fingerprint check.
    fp_items = []
    for raw in payload.get("items", []):
        fp_items.append(
            SnapshotItem(
                item_id=raw["item_id"],
                item_role=raw["item_role"],
                canonical_text="",
                text_hash=raw["text_hash"],
                vector=(),  # empty: not used by the fingerprint payload
                vector_fingerprint=raw.get("vector_fingerprint", ""),
            )
        )
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
        items=fp_items,
    )
    if recomputed_snapshot_fp != payload.get("snapshot_fingerprint"):
        raise SnapshotIntegrityError(
            "snapshot_fingerprint mismatch (metadata or stored vector_fingerprints were modified)"
        )
    if recomputed_snapshot_fp != sidecar_fp:
        raise SnapshotIntegrityError("sidecar fingerprint mismatch")

    # ── Layer 3: decode ONLY allowed items ──
    allowed = frozenset(allowed_item_ids)
    items: list[SnapshotItem] = []
    decoded_query_ids: list[str] = []
    decoded_candidate_ids: list[str] = []
    skipped_ids: list[str] = []
    for raw in payload.get("items", []):
        iid = raw["item_id"]
        if iid not in allowed:
            skipped_ids.append(iid)
            continue  # NEVER decode — vector floats never read
        vec = tuple(float(x) for x in raw["vector"])
        if len(vec) != dimension:
            raise SnapshotIntegrityError(
                f"item {iid}: vector dimension {len(vec)} != metadata dimension {dimension}"
            )
        recomputed_vfp = vector_fingerprint(vec)
        if recomputed_vfp != raw.get("vector_fingerprint"):
            raise SnapshotIntegrityError(f"item {iid}: vector_fingerprint mismatch (vector modified)")
        items.append(
            SnapshotItem(
                item_id=iid,
                item_role=raw["item_role"],
                canonical_text="",
                text_hash=raw["text_hash"],
                vector=vec,
                vector_fingerprint=recomputed_vfp,
            )
        )
        if raw["item_role"] == "query":
            decoded_query_ids.append(iid)
        elif raw["item_role"] == "candidate":
            decoded_candidate_ids.append(iid)

    snapshot = EmbeddingSnapshot(
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

    report = {
        "opaque_file_sha256": opaque_hash,
        "snapshot_fingerprint": recomputed_snapshot_fp,
        "sidecar_fingerprint": sidecar_fp,
        "dimension": dimension,
        "decoded_query_count": len(decoded_query_ids),
        "decoded_candidate_count": len(decoded_candidate_ids),
        "skipped_count": len(skipped_ids),  # held-out items, never decoded
        "decoded_query_ids": sorted(decoded_query_ids),
        "decoded_candidate_ids": sorted(decoded_candidate_ids),
    }
    return snapshot, report
