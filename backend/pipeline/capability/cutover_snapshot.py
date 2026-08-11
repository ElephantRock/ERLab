"""Cutover snapshot and canonical regeneration (P0.4A2.5).

For initial paper cutover, snapshots the exact currently eligible P0.3
vector population and regenerates each item under the target capability
binding through canonical content.

The source snapshot is IMMUTABLE. Retry attempts may update item
execution state, but they must not replace the snapshotted identity or
content hash.

Prohibited:
  reading old vector values
  copying legacy embeddings
  using nearest-neighbor results as regeneration input
  fabricating missing canonical content
  changing the source snapshot to hide failures

One unavailable canonical source blocks readiness and is reported
explicitly.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.db.models import (
    EmbeddingBindingCutover,
    EmbeddingBindingCutoverItem,
    VectorIndexRecord,
)
from backend.pipeline.vector_contracts import (
    EMBEDDING_CONTRACT_PRE_CAPABILITY_V0,
    VECTOR_INDEX_V1,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceSnapshotResult:
    """Result of snapshotting the source population."""

    cutover_id: str
    source_item_count: int
    source_snapshot_fingerprint: str


def snapshot_source_population(
    session: Session,
    *,
    cutover_id: str,
    embedding_profile_id: str,
    source_binding_id: str | None = None,
) -> SourceSnapshotResult:
    """Snapshot the currently eligible vector population.

    For initial cutover (source_binding_id=None): snapshots all
    indexed v1 vectors for the profile.

    For binding replacement: snapshots all indexed v2 vectors for the
    profile under the source binding.

    Creates cutover_item rows for each source vector. The snapshot is
    immutable — subsequent retries update item execution state only.
    """
    # Determine source contract version
    if source_binding_id is not None:
        source_contract = "capability_v1"
        source_filter = (
            VectorIndexRecord.embedding_profile_id == embedding_profile_id,
            VectorIndexRecord.index_status == "indexed",
            VectorIndexRecord.index_schema_version == "vector_index_v2",
            VectorIndexRecord.capability_binding_id == source_binding_id,
        )
    else:
        source_contract = EMBEDDING_CONTRACT_PRE_CAPABILITY_V0
        source_filter = (
            VectorIndexRecord.embedding_profile_id == embedding_profile_id,
            VectorIndexRecord.index_status == "indexed",
            VectorIndexRecord.index_schema_version == VECTOR_INDEX_V1,
        )

    source_records = session.execute(
        select(VectorIndexRecord).where(*source_filter).order_by(VectorIndexRecord.vector_record_id)
    ).scalars().all()

    # Compute snapshot fingerprint
    fingerprint_payload = []
    items_to_create = []
    for rec in source_records:
        item_fingerprint = {
            "vector_record_id": rec.vector_record_id,
            "paper_id": rec.paper_id,
            "chunk_key": rec.chunk_key,
            "content_hash": rec.content_hash,
            "embedding_profile_id": rec.embedding_profile_id,
            "source_binding_id": rec.capability_binding_id,
            "source_contract_version": source_contract,
        }
        fingerprint_payload.append(item_fingerprint)

        items_to_create.append(EmbeddingBindingCutoverItem(
            item_id=hashlib.sha256(
                f"{cutover_id}:{rec.vector_record_id}".encode()
            ).hexdigest(),
            cutover_id=cutover_id,
            source_object_type="paper_chunk",
            source_object_id=rec.vector_record_id,
            source_vector_record_id=rec.vector_record_id,
            paper_id=rec.paper_id,
            chunk_key=rec.chunk_key,
            canonical_content_hash=rec.content_hash,
            source_contract_version=source_contract,
            status="pending",
            attempt_count=0,
        ))

    # Deterministic fingerprint over ordered source rows
    import json
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    # Insert items
    for item in items_to_create:
        session.add(item)
    session.flush()

    # Update cutover with snapshot info
    now = datetime.now(UTC)
    session.execute(
        update(EmbeddingBindingCutover).where(
            EmbeddingBindingCutover.cutover_id == cutover_id
        ).values(
            source_snapshot_kind="paper_chunk" if source_binding_id is None else "binding_replacement",
            source_snapshot_fingerprint=fingerprint,
            source_item_count=len(source_records),
            snapshot_completed_at=now,
            status="reindexing",
        )
    )
    session.commit()

    logger.info(
        "cutover snapshot: %d items, fingerprint=%s...",
        len(source_records),
        fingerprint[:16],
    )

    return SourceSnapshotResult(
        cutover_id=cutover_id,
        source_item_count=len(source_records),
        source_snapshot_fingerprint=fingerprint,
    )


def recompute_source_fingerprint(
    session: Session,
    *,
    embedding_profile_id: str,
    source_binding_id: str | None = None,
) -> str:
    """Recompute the source population fingerprint for drift detection.

    Used during seal to verify the source population hasn't changed
    since the snapshot.
    """
    if source_binding_id is not None:
        source_records = session.execute(
            select(VectorIndexRecord.vector_record_id, VectorIndexRecord.paper_id,
                   VectorIndexRecord.chunk_key, VectorIndexRecord.content_hash,
                   VectorIndexRecord.embedding_profile_id, VectorIndexRecord.capability_binding_id)
            .where(
                VectorIndexRecord.embedding_profile_id == embedding_profile_id,
                VectorIndexRecord.index_status == "indexed",
                VectorIndexRecord.index_schema_version == "vector_index_v2",
                VectorIndexRecord.capability_binding_id == source_binding_id,
            )
            .order_by(VectorIndexRecord.vector_record_id)
        ).all()
        source_contract = "capability_v1"
    else:
        source_records = session.execute(
            select(VectorIndexRecord.vector_record_id, VectorIndexRecord.paper_id,
                   VectorIndexRecord.chunk_key, VectorIndexRecord.content_hash,
                   VectorIndexRecord.embedding_profile_id, VectorIndexRecord.capability_binding_id)
            .where(
                VectorIndexRecord.embedding_profile_id == embedding_profile_id,
                VectorIndexRecord.index_status == "indexed",
                VectorIndexRecord.index_schema_version == VECTOR_INDEX_V1,
            )
            .order_by(VectorIndexRecord.vector_record_id)
        ).all()
        source_contract = EMBEDDING_CONTRACT_PRE_CAPABILITY_V0

    fingerprint_payload = [
        {
            "vector_record_id": r.vector_record_id,
            "paper_id": r.paper_id,
            "chunk_key": r.chunk_key,
            "content_hash": r.content_hash,
            "embedding_profile_id": r.embedding_profile_id,
            "source_binding_id": r.capability_binding_id,
            "source_contract_version": source_contract,
        }
        for r in source_records
    ]

    import json
    return hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def get_cutover_item_counts(
    session: Session,
    cutover_id: str,
) -> dict[str, int]:
    """Get item status counts for a cutover."""
    items = session.execute(
        select(EmbeddingBindingCutoverItem.status).where(
            EmbeddingBindingCutoverItem.cutover_id == cutover_id
        )
    ).scalars().all()

    counts: dict[str, int] = {}
    for status in items:
        counts[status] = counts.get(status, 0) + 1
    return counts


def is_cutover_ready_for_seal(
    session: Session,
    cutover_id: str,
) -> tuple[bool, str | None]:
    """Check if all cutover items are indexed or already_indexed.

    Returns (ready, failure_reason).
    """
    counts = get_cutover_item_counts(session, cutover_id)

    total = sum(counts.values())
    done = counts.get("indexed", 0) + counts.get("already_indexed", 0)
    failed = counts.get("failed", 0)
    unavailable = counts.get("content_unavailable", 0)

    if failed > 0:
        return False, f"{failed} item(s) failed"
    if unavailable > 0:
        return False, f"{unavailable} item(s) have unavailable content"
    if done < total:
        return False, f"{done}/{total} items indexed"

    return True, None
