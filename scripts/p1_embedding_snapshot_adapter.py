"""Shared TEI snapshot adapter for P1D and P1E.

Single, production-independent definition of
``tei_snapshot_to_embedding_snapshot``. Used by:

  - P1D exact-parity comparison (``scripts/p1d_p1b_evaluator_comparison.py``)
  - P1E benchmark discrimination audit
    (``scripts/p1e_benchmark_discrimination_audit.py``)

This is NOT ranking or metric logic — it only re-shapes the TEI snapshot JSON
into the ``EmbeddingSnapshot`` dataclass that the original P1B evaluator
consumes. Keeping one shared definition prevents the two consumers from
drifting apart.

Held-out isolation (P1E only):
    When ``allowed_item_ids`` is provided, items NOT in the allowlist are
    filtered BEFORE ``SnapshotItem`` construction — they are never decoded.
    This guarantees the audit never materializes held-out query vectors or
    held-out-only candidate vectors. The allowlist is the union of the 44
    cal+dev query IDs and the candidate IDs referenced exclusively by those
    44 cases.

Usage:
    # P1D (preserves the original unfiltered behavior):
    tei_snapshot_to_embedding_snapshot(payload)

    # P1E (filtered before materialization):
    tei_snapshot_to_embedding_snapshot(payload, allowed_item_ids=allow)
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.ranking.embedding_snapshot import EmbeddingSnapshot, SnapshotItem


def tei_snapshot_to_embedding_snapshot(
    payload: dict | Path,
    *,
    allowed_item_ids: frozenset[str] | None = None,
) -> EmbeddingSnapshot:
    """Convert TEI snapshot JSON -> EmbeddingSnapshot (the P1B evaluator input).

    Parameters
    ----------
    payload
        Either the decoded TEI snapshot dict, or a Path to the JSON file.
    allowed_item_ids
        Optional allowlist applied BEFORE item construction. When set, any
        query/candidate whose ID is not in the set is skipped entirely — its
        vector is never decoded. ``None`` preserves the original P1D behavior
        (load every item).
    """
    if isinstance(payload, Path):
        with open(payload) as f:
            raw = json.load(f)
    else:
        raw = payload

    allow = frozenset(allowed_item_ids) if allowed_item_ids is not None else None

    items: list[SnapshotItem] = []
    # ── queries: filter before decode ──
    for qid, data in raw["queries"].items():
        if allow is not None and qid not in allow:
            continue  # held-out query: vector never decoded
        items.append(SnapshotItem(
            item_id=qid,
            item_role="query",
            canonical_text="",  # not used by the scorer
            text_hash=data["text_hash"],
            vector=tuple(data["vector"]),
            vector_fingerprint="",  # recomputed by callers that need it
        ))
    # ── candidates: filter before decode ──
    for cid, data in raw["candidates"].items():
        if allow is not None and cid not in allow:
            continue  # held-out-only candidate: vector never decoded
        items.append(SnapshotItem(
            item_id=cid,
            item_role="candidate",
            canonical_text="",
            text_hash=data["text_hash"],
            vector=tuple(data["vector"]),
            vector_fingerprint="",
        ))

    return EmbeddingSnapshot(
        snapshot_schema_version="embedding_snapshot_v1",
        benchmark_version=raw.get("benchmark_fingerprint", "v2"),
        benchmark_fingerprint="",
        capability_binding_id="tei_direct",
        capability_check_id="tei_direct",
        generation_runtime_fingerprint="",
        provider_kind="tei",
        provider_model=raw["embedding_profile"]["model"],
        provider_revision=raw["embedding_profile"].get("tei_sha"),
        endpoint_identity="http://127.0.0.1:9090",
        deployment_id=None,
        embedding_contract_version="",
        dimension=raw["embedding_profile"]["dimension"],
        normalization_policy="l2",
        items=tuple(items),
        created_at="",
        snapshot_fingerprint="",
    )
