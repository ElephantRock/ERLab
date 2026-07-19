"""Capability-bound vector indexer v2 (P0.4A2.3).

Creates ``vector_index_v2`` VectorIndexRecord rows using authorized
embedding receipts from ``VerifiedEmbeddingRuntime``.

Indexing modes:
  pre_capability_production
      Ordinary v1 indexing — NOT this module's concern.
  candidate_binding
      Cutover remediation indexing — writes v2 vectors that are NOT
      eligible for production retrieval until activation.
  active_binding
      Post-activation production indexing — writes v2 vectors that ARE
      eligible.

Indexing sequence:
  resolve indexing posture
  → check profile write guard
  → claim deterministic vector identity (v2)
  → obtain AuthorizedEmbeddingBatch
  → assert receipt binding matches target binding
  → write to binding-specific collection
  → read back and verify
  → publish indexed registry record with binding + check evidence

A refreshed check under the same binding reuses the same vector identity
and avoids an unnecessary embedding when a verified indexed record
already exists.

This module does NOT handle v1 indexing — that remains in
``vector_indexer.py`` unchanged.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from backend.db.models import VectorIndexRecord
from backend.pipeline.capability.verified_embedding_runtime import (
    AuthorizedEmbeddingBatch,
    VerifiedEmbeddingRuntime,
)
from backend.pipeline.vector_backend import GovernedVectorBackend
from backend.pipeline.vector_contracts import (
    EMBEDDING_CONTRACT_CAPABILITY_V1,
    VECTOR_INDEX_V2,
    VectorIndexDocument,
    compute_v2_collection_name,
    compute_vector_record_id_v2,
)

logger = logging.getLogger(__name__)


# ── Indexing modes ────────────────────────────────────────────────────

MODE_PRE_CAPABILITY = "pre_capability_production"
MODE_CANDIDATE = "candidate_binding"
MODE_ACTIVE = "active_binding"


class IndexingError(Exception):
    """Base for v2 indexing failures."""


class WriteGuardFrozen(IndexingError):
    """The profile write guard is frozen — new writes rejected."""


class ReceiptBindingMismatch(IndexingError):
    """The authorized receipt's binding does not match the target binding."""

    def __init__(self, receipt_binding: str, target_binding: str):
        self.receipt_binding = receipt_binding
        self.target_binding = target_binding
        super().__init__(
            f"receipt binding {receipt_binding[:16]}... != target binding "
            f"{target_binding[:16]}..."
        )


@dataclass(frozen=True)
class V2IndexingOutcome:
    """Result of a v2 indexing operation."""

    status: str  # indexed | already_indexed | failed
    vector_record_id: str
    capability_binding_id: str
    generation_capability_check_id: str
    collection_name: str
    failure_code: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def index_document_v2(
    *,
    session_factory: sessionmaker,
    backend: GovernedVectorBackend,
    verified_runtime: VerifiedEmbeddingRuntime,
    profile_id: str,
    document: VectorIndexDocument,
    target_binding_id: str,
    mode: str = MODE_CANDIDATE,
) -> V2IndexingOutcome:
    """Index a document under a capability binding (v2).

    Uses the verified runtime's ``embed_documents_authorized`` to obtain
    an ``AuthorizedEmbeddingBatch`` and asserts the receipt binding
    matches the target binding.

    Creates a ``vector_index_v2`` VectorIndexRecord with
    ``embedding_contract_version='capability_v1'``, non-NULL
    ``capability_binding_id`` and ``generation_capability_check_id``.

    The collection is binding-specific: ``compute_v2_collection_name``.
    """
    from backend.db.models import EmbeddingProfileEmbeddingWriteGuard

    # 1. Compute v2 vector identity
    v2_id = compute_vector_record_id_v2(
        paper_id=document.paper_id,
        chunk_key=document.chunk_key,
        content_hash=document.content_hash,
        embedding_profile_id=profile_id,
        capability_binding_id=target_binding_id,
    )

    collection_name = compute_v2_collection_name(target_binding_id)

    # 2. Check for existing indexed record (idempotent replay)
    with session_factory() as session:
        existing = session.execute(
            select(VectorIndexRecord).where(
                VectorIndexRecord.vector_record_id == v2_id,
                VectorIndexRecord.index_status == "indexed",
                VectorIndexRecord.capability_binding_id == target_binding_id,
            )
        ).scalar_one_or_none()

        if existing is not None:
            logger.debug(
                "v2 vector already indexed: %s...", v2_id[:16]
            )
            return V2IndexingOutcome(
                status="already_indexed",
                vector_record_id=v2_id,
                capability_binding_id=target_binding_id,
                generation_capability_check_id=existing.generation_capability_check_id or "",
                collection_name=collection_name,
            )
    session.close()

    # 3. Check write guard (active mode requires open guard)
    if mode == MODE_ACTIVE:
        with session_factory() as session:
            guard = session.execute(
                select(EmbeddingProfileEmbeddingWriteGuard).where(
                    EmbeddingProfileEmbeddingWriteGuard.embedding_profile_id == profile_id,
                    EmbeddingProfileEmbeddingWriteGuard.embedding_purpose == "paper",
                )
            ).scalar_one_or_none()

            if guard is not None and guard.state == "frozen":
                raise WriteGuardFrozen(
                    f"profile {profile_id[:16]}... write guard is frozen "
                    f"(cutover={guard.cutover_id[:16] if guard.cutover_id else 'none'}...)"
                )

    # 4. Create pending v2 record
    with session_factory() as session:
        existing_pending = session.execute(
            select(VectorIndexRecord).where(
                VectorIndexRecord.vector_record_id == v2_id,
            )
        ).scalar_one_or_none()

        if existing_pending is None:
            record = VectorIndexRecord(
                vector_record_id=v2_id,
                paper_id=document.paper_id,
                chunk_key=document.chunk_key,
                content_kind=document.content_kind,
                content_hash=document.content_hash,
                embedding_profile_id=profile_id,
                collection_name=collection_name,
                index_schema_version=VECTOR_INDEX_V2,
                embedding_contract_version=EMBEDDING_CONTRACT_CAPABILITY_V1,
                capability_binding_id=target_binding_id,
                index_status="pending",
                attempt_count=0,
            )
            session.add(record)
            session.flush()
        session.commit()

    # 5. Atomically claim
    now = _now()
    with session_factory() as session:
        claim_result = session.execute(
            update(VectorIndexRecord)
            .where(
                VectorIndexRecord.vector_record_id == v2_id,
                VectorIndexRecord.index_status.in_(["pending", "failed"]),
            )
            .values(
                index_status="indexing",
                attempt_count=VectorIndexRecord.attempt_count + 1,
                indexing_started_at=now,
                failure_code=None,
                failure_detail=None,
            )
        )
        session.commit()

        if claim_result.rowcount != 1:
            # Already being indexed by another worker
            current = session.execute(
                select(VectorIndexRecord.index_status).where(
                    VectorIndexRecord.vector_record_id == v2_id
                )
            ).scalar_one_or_none()

            if current == "indexed":
                return V2IndexingOutcome(
                    status="already_indexed",
                    vector_record_id=v2_id,
                    capability_binding_id=target_binding_id,
                    generation_capability_check_id="",
                    collection_name=collection_name,
                )
            raise IndexingError(
                f"could not claim v2 vector {v2_id[:16]}... (status={current})"
            )

    # 6. Obtain authorized embedding
    try:
        receipt: AuthorizedEmbeddingBatch = (
            await verified_runtime.embed_documents_authorized(
                [document.content_text]
            )
        )
    except Exception as exc:
        await _mark_v2_failed(session_factory, v2_id, "embedding_error", str(exc)[:500])
        return V2IndexingOutcome(
            status="failed",
            vector_record_id=v2_id,
            capability_binding_id=target_binding_id,
            generation_capability_check_id="",
            collection_name=collection_name,
            failure_code="embedding_error",
        )

    # 7. Assert receipt binding matches target
    if receipt.capability_binding_id != target_binding_id:
        await _mark_v2_failed(
            session_factory, v2_id, "receipt_binding_mismatch",
            f"receipt={receipt.capability_binding_id[:16]}... target={target_binding_id[:16]}...",
        )
        raise ReceiptBindingMismatch(
            receipt.capability_binding_id, target_binding_id
        )

    embedding = list(receipt.embeddings[0]) if receipt.embeddings else []

    # 8. Write to binding-specific collection
    try:
        backend.ensure_profile_collection(
            collection_name=collection_name,
            embedding_profile_id=profile_id,
            embedding_dimension=len(embedding),
        )
        backend.upsert_vector(
            collection_name=collection_name,
            vector_id=v2_id,
            embedding=embedding,
            document_text=document.content_text,
            metadata={
                "vector_record_id": v2_id,
                "paper_id": str(document.paper_id),
                "chunk_key": document.chunk_key,
                "content_kind": document.content_kind,
                "content_hash": document.content_hash,
                "embedding_profile_id": profile_id,
                "index_schema_version": VECTOR_INDEX_V2,
                "capability_binding_id": target_binding_id,
            },
        )
    except Exception as exc:
        await _mark_v2_failed(session_factory, v2_id, "backend_write_error", str(exc)[:500])
        return V2IndexingOutcome(
            status="failed",
            vector_record_id=v2_id,
            capability_binding_id=target_binding_id,
            generation_capability_check_id=receipt.capability_check_id,
            collection_name=collection_name,
            failure_code="backend_write_error",
        )

    # 9. Publish indexed
    now = _now()
    with session_factory() as session:
        session.execute(
            update(VectorIndexRecord)
            .where(
                VectorIndexRecord.vector_record_id == v2_id,
                VectorIndexRecord.index_status == "indexing",
            )
            .values(
                index_status="indexed",
                indexed_at=now,
                backend_verified_at=now,
                generation_capability_check_id=receipt.capability_check_id,
                failure_code=None,
                failure_detail=None,
            )
        )
        session.commit()

    logger.info(
        "v2 vector indexed: %s... (binding=%s..., check=%s...)",
        v2_id[:16],
        target_binding_id[:16],
        receipt.capability_check_id[:16],
    )

    return V2IndexingOutcome(
        status="indexed",
        vector_record_id=v2_id,
        capability_binding_id=target_binding_id,
        generation_capability_check_id=receipt.capability_check_id,
        collection_name=collection_name,
    )


async def _mark_v2_failed(
    session_factory: sessionmaker,
    v2_id: str,
    failure_code: str,
    failure_detail: str,
) -> None:
    """Mark a v2 record as failed."""
    now = _now()
    with session_factory() as session:
        session.execute(
            update(VectorIndexRecord)
            .where(
                VectorIndexRecord.vector_record_id == v2_id,
                VectorIndexRecord.index_status == "indexing",
            )
            .values(
                index_status="failed",
                failure_code=failure_code,
                failure_detail=failure_detail[:500],
            )
        )
        session.commit()
