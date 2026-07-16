"""Governed vector indexer (P0.3.2C-G).

Orchestrates the full indexing lifecycle:
  - Profile registration with drift detection
  - Registry record creation
  - Atomic indexing claim (single-worker)
  - Embedding validation
  - Backend write + read-back verification
  - Content replacement (stale old only after new is verified)
  - Idempotent replay
  - Verified deletion

The indexer never trusts a backend upsert response alone — it always reads
back and verifies before publishing ``indexed`` eligibility.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from backend.pipeline.vector_backend import BackendVectorRecord, GovernedVectorBackend
from backend.pipeline.vector_contracts import (
    EmbeddingProfileDriftError,
    IndexingAlreadyClaimedError,
    VectorIndexDocument,
    VectorIndexingOutcome,
    VectorIndexRegistryDriftError,
    compute_collection_name,
    compute_content_hash,
    compute_profile_id,
    compute_vector_record_id,
)

logger = logging.getLogger(__name__)

_LEGACY_COLLECTION = "research_papers"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Profile registration ─────────────────────────────────────────────


def register_embedding_profile(
    session: Session,
    *,
    provider: str,
    model_identifier: str,
    dimension: int,
    normalization_policy: str,
    chunking_schema_version: str,
) -> str:
    """Register or verify an embedding profile.

    Same profile_id + identical declaration → replay-safe no-op.
    Same profile_id + different declaration → EmbeddingProfileDriftError.

    Returns the profile_id.
    """
    from backend.db.models import EmbeddingProfile

    profile_id = compute_profile_id(
        provider, model_identifier, dimension,
        normalization_policy, chunking_schema_version,
    )
    collection_name = compute_collection_name(profile_id)

    existing = session.execute(
        select(EmbeddingProfile).where(EmbeddingProfile.profile_id == profile_id)
    ).scalar_one_or_none()

    if existing is not None:
        # Verify replay consistency
        if (existing.provider != provider
            or existing.model_identifier != model_identifier
            or existing.dimension != dimension
            or existing.normalization_policy != normalization_policy
            or existing.chunking_schema_version != chunking_schema_version):
            raise EmbeddingProfileDriftError(
                f"embedding profile {profile_id[:12]}... declaration changed"
            )
        return profile_id

    # Check collection-name collision with a different profile
    collision = session.execute(
        select(EmbeddingProfile).where(
            EmbeddingProfile.collection_name == collection_name,
            EmbeddingProfile.profile_id != profile_id,
        )
    ).scalar_one_or_none()
    if collision is not None:
        raise ValueError(
            f"collection name {collection_name!r} already registered "
            f"by profile {collision.profile_id[:12]}..."
        )

    profile = EmbeddingProfile(
        profile_id=profile_id,
        profile_schema_version="embedding_profile_v1",
        provider=provider,
        model_identifier=model_identifier,
        dimension=dimension,
        normalization_policy=normalization_policy,
        chunking_schema_version=chunking_schema_version,
        collection_name=collection_name,
        verification_status="unverified",
    )
    session.add(profile)
    session.flush()
    return profile_id


# ── Embedding validation ─────────────────────────────────────────────


def validate_embedding(
    embedding: Any, expected_dimension: int,
) -> tuple[bool, str | None]:
    """Validate an embedding vector before backend write.

    Returns (is_valid, failure_code).
    """
    if embedding is None:
        return False, "embedding_empty"

    if not isinstance(embedding, (list, tuple)):
        return False, "embedding_non_numeric"

    if len(embedding) == 0:
        return False, "embedding_empty"

    if len(embedding) != expected_dimension:
        return False, "embedding_dimension_mismatch"

    for v in embedding:
        if isinstance(v, bool):
            return False, "embedding_non_numeric"
        if not isinstance(v, (int, float)):
            return False, "embedding_non_numeric"
        if math.isnan(v) or math.isinf(v):
            return False, "embedding_non_finite"

    if all(v == 0.0 for v in embedding):
        return False, "embedding_zero_vector"

    return True, None


# ── Backend metadata ─────────────────────────────────────────────────


def _build_backend_metadata(doc: VectorIndexDocument) -> dict[str, object]:
    """Build the governed metadata for a backend vector record."""
    return {
        "vector_record_id": compute_vector_record_id(
            doc.paper_id, doc.chunk_key, doc.content_hash, doc.embedding_profile_id,
        ),
        "paper_id": doc.paper_id,
        "chunk_key": doc.chunk_key,
        "content_kind": doc.content_kind,
        "content_hash": doc.content_hash,
        "embedding_profile_id": doc.embedding_profile_id,
        "index_schema_version": "vector_index_v1",
    }


def _verify_readback(
    record: BackendVectorRecord | None,
    doc: VectorIndexDocument,
    expected_dimension: int,
) -> tuple[bool, str]:
    """Verify a read-back backend record against expectations.

    Returns (is_valid, failure_code).
    """
    if record is None:
        return False, "backend_record_missing"

    if record.paper_id != doc.paper_id:
        return False, "metadata_mismatch_paper_id"
    if record.chunk_key != doc.chunk_key:
        return False, "metadata_mismatch_chunk_key"
    if record.content_kind != doc.content_kind:
        return False, "metadata_mismatch_content_kind"
    if record.content_hash != doc.content_hash:
        return False, "metadata_mismatch_content_hash"
    if record.embedding_profile_id != doc.embedding_profile_id:
        return False, "metadata_mismatch_profile"
    if record.index_schema_version != "vector_index_v1":
        return False, "metadata_mismatch_index_schema"
    if len(record.embedding) != expected_dimension:
        return False, "backend_dimension_mismatch"

    return True, ""


# ── Indexing ─────────────────────────────────────────────────────────


async def index_document(
    *,
    session_factory: sessionmaker,
    backend: GovernedVectorBackend,
    embedding_provider: Any,
    profile: dict[str, Any],
    document: VectorIndexDocument,
) -> VectorIndexingOutcome:
    """Index a canonical document under a governed profile.

    Full lifecycle:
      1. Register profile
      2. Create/load registry record
      3. Atomic claim (pending/failed → indexing)
      4. Generate + validate embedding
      5. Backend upsert + read-back verification
      6. Publish indexed state
    """
    from backend.db.models import VectorIndexRecord

    # 1. Register profile
    session = session_factory()
    try:
        profile_id = register_embedding_profile(
            session,
            provider=profile["provider"],
            model_identifier=profile["model_identifier"],
            dimension=profile["dimension"],
            normalization_policy=profile["normalization_policy"],
            chunking_schema_version=profile["chunking_schema_version"],
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    collection_name = compute_collection_name(profile_id)
    vector_record_id = compute_vector_record_id(
        document.paper_id, document.chunk_key,
        document.content_hash, profile_id,
    )

    # 2. Load or create registry record
    session = session_factory()
    try:
        existing = session.execute(
            select(VectorIndexRecord).where(
                VectorIndexRecord.vector_record_id == vector_record_id
            )
        ).scalar_one_or_none()

        if existing is not None:
            # Verify content identity matches
            if (existing.content_hash != document.content_hash
                or existing.paper_id != document.paper_id
                or existing.chunk_key != document.chunk_key):
                raise VectorIndexRegistryDriftError(
                    f"vector_record_id {vector_record_id[:12]}... "
                    f"resolves to different registry content"
                )

            if existing.index_status == "indexed":
                # Idempotent replay — no external calls, no mutation
                return VectorIndexingOutcome(
                    vector_record_id=vector_record_id,
                    paper_id=document.paper_id,
                    chunk_key=document.chunk_key,
                    embedding_profile_id=profile_id,
                    status="already_indexed",
                    attempt_count=existing.attempt_count,
                )

            if existing.index_status == "indexing":
                raise IndexingAlreadyClaimedError(
                    f"vector_record_id {vector_record_id[:12]}... "
                    f"is being indexed by another worker"
                )

            if existing.index_status in ("stale", "deleting", "deleted"):
                raise ValueError(
                    f"vector_record_id {vector_record_id[:12]}... "
                    f"has terminal/historical status {existing.index_status!r}; "
                    f"content changes require a new vector identity"
                )

            # pending or failed — eligible for claim
            record = existing
        else:
            # Create new pending record
            record = VectorIndexRecord(
                vector_record_id=vector_record_id,
                paper_id=document.paper_id,
                chunk_key=document.chunk_key,
                content_kind=document.content_kind,
                content_hash=document.content_hash,
                embedding_profile_id=profile_id,
                collection_name=collection_name,
                index_status="pending",
                attempt_count=0,
            )
            session.add(record)
            session.flush()

        # 3. Atomic claim: pending/failed → indexing
        claim_result = session.execute(
            update(VectorIndexRecord)
            .where(
                VectorIndexRecord.vector_record_id == vector_record_id,
                VectorIndexRecord.index_status.in_(["pending", "failed"]),
            )
            .values(
                index_status="indexing",
                attempt_count=VectorIndexRecord.attempt_count + 1,
                indexing_started_at=_now(),
                failure_code=None,
                failure_detail=None,
            )
        )
        if claim_result.rowcount != 1:
            raise IndexingAlreadyClaimedError(
                f"could not atomically claim {vector_record_id[:12]}..."
            )
        session.commit()
        attempt_count = record.attempt_count
    except (IndexingAlreadyClaimedError, VectorIndexRegistryDriftError):
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    # 4. Generate embedding
    try:
        embedding = await embedding_provider.embed_single(document.content_text)
    except Exception as exc:
        await _mark_failed(session_factory, vector_record_id,
                           "embedding_provider_error", str(exc)[:500])
        raise

    # Validate embedding
    is_valid, failure_code = validate_embedding(embedding, profile["dimension"])
    if not is_valid:
        await _mark_failed(session_factory, vector_record_id, failure_code,
                           f"embedding validation failed: {failure_code}")
        raise ValueError(f"embedding validation failed: {failure_code}")

    # 5. Backend upsert
    try:
        backend.ensure_profile_collection(
            collection_name=collection_name,
            embedding_profile_id=profile_id,
            embedding_dimension=profile["dimension"],
        )
        metadata = _build_backend_metadata(document)
        backend.upsert_vector(
            collection_name=collection_name,
            vector_record_id=vector_record_id,
            embedding=embedding,
            document=document.content_text,
            metadata=metadata,
        )
    except Exception as exc:
        await _mark_failed(session_factory, vector_record_id,
                           "backend_write_failed", str(exc)[:500])
        raise

    # Read-back verification
    readback = backend.read_vector(
        collection_name=collection_name,
        vector_record_id=vector_record_id,
    )
    is_valid, fail_code = _verify_readback(readback, document, profile["dimension"])
    if not is_valid:
        # Best-effort cleanup
        try:
            backend.delete_vector(
                collection_name=collection_name,
                vector_record_id=vector_record_id,
            )
        except Exception:
            pass  # cleanup failure is OK — registry stays failed
        await _mark_failed(session_factory, vector_record_id,
                           "backend_verification_failed", fail_code)
        raise ValueError(f"backend verification failed: {fail_code}")

    # 6. Publish indexed state
    session = session_factory()
    try:
        now = _now()

        # Stale any prior indexed record for same paper/chunk/profile
        session.execute(
            update(VectorIndexRecord)
            .where(
                VectorIndexRecord.paper_id == document.paper_id,
                VectorIndexRecord.chunk_key == document.chunk_key,
                VectorIndexRecord.embedding_profile_id == profile_id,
                VectorIndexRecord.index_status == "indexed",
                VectorIndexRecord.vector_record_id != vector_record_id,
            )
            .values(stale_at=now, index_status="stale")
        )

        # Mark this record indexed
        session.execute(
            update(VectorIndexRecord)
            .where(VectorIndexRecord.vector_record_id == vector_record_id)
            .values(
                index_status="indexed",
                indexed_at=now,
                backend_verified_at=now,
                failure_code=None,
                failure_detail=None,
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return VectorIndexingOutcome(
        vector_record_id=vector_record_id,
        paper_id=document.paper_id,
        chunk_key=document.chunk_key,
        embedding_profile_id=profile_id,
        status="indexed",
        attempt_count=attempt_count,
    )


async def _mark_failed(
    session_factory: sessionmaker,
    vector_record_id: str,
    failure_code: str,
    failure_detail: str,
) -> None:
    """Mark a registry record as failed in a short transaction."""
    from backend.db.models import VectorIndexRecord

    session = session_factory()
    try:
        session.execute(
            update(VectorIndexRecord)
            .where(VectorIndexRecord.vector_record_id == vector_record_id)
            .values(
                index_status="failed",
                failure_code=failure_code,
                failure_detail=failure_detail[:500],
            )
        )
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


# ── Deletion ─────────────────────────────────────────────────────────


async def delete_index_record(
    *,
    session_factory: sessionmaker,
    backend: GovernedVectorBackend,
    vector_record_id: str,
) -> None:
    """Verified deletion lifecycle.

    indexed/stale/failed → deleting → backend delete → verify absent → deleted
    """
    from backend.db.models import VectorIndexRecord

    # Atomic claim: indexed/stale/failed → deleting
    session = session_factory()
    try:
        claim = session.execute(
            update(VectorIndexRecord)
            .where(
                VectorIndexRecord.vector_record_id == vector_record_id,
                VectorIndexRecord.index_status.in_(["indexed", "stale", "failed"]),
            )
            .values(
                index_status="deleting",
                deleting_started_at=_now(),
            )
        )
        if claim.rowcount != 1:
            raise ValueError(
                f"cannot delete {vector_record_id[:12]}... — "
                f"not in a deletable state"
            )

        record = session.execute(
            select(VectorIndexRecord.collection_name).where(
                VectorIndexRecord.vector_record_id == vector_record_id
            )
        ).one()
        collection_name = record[0]
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    # Backend delete
    try:
        backend.delete_vector(
            collection_name=collection_name,
            vector_record_id=vector_record_id,
        )
    except Exception as exc:
        logger.warning("Backend delete failed for %s: %s", vector_record_id[:12], exc)
        # Leave in 'deleting' state
        raise

    # Verify absence
    is_absent = backend.verify_absent(
        collection_name=collection_name,
        vector_record_id=vector_record_id,
    )
    if not is_absent:
        raise ValueError(
            f"backend record {vector_record_id[:12]}... still present after delete"
        )

    # Mark deleted
    session = session_factory()
    try:
        session.execute(
            update(VectorIndexRecord)
            .where(VectorIndexRecord.vector_record_id == vector_record_id)
            .values(
                index_status="deleted",
                deleted_at=_now(),
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
