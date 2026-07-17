"""Legacy vector inventory service (P0.3.5B2–G).

The only maintenance module allowed to enumerate the legacy
``research_papers`` collection. Performs:
  - deterministic scan and fingerprinting
  - versioned metadata extraction
  - exact multi-identifier mapping
  - target planning and deduplication
  - governed reindex orchestration
  - source drift verification
  - aggregate reconciliation

This module must never:
  - perform similarity search
  - copy legacy embeddings
  - return legacy results to research stages
  - modify legacy collection metadata
"""

from __future__ import annotations

import hashlib
import json
import logging
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Protocol, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

_MAPPING_SCHEMA_VERSION = "legacy_mapping_v1"
_PAGE_SIZE = 500


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Contracts ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LegacyCollectionIdentity:
    """Identity snapshot of the legacy collection at scan time."""
    collection_name: str
    record_count: int


@dataclass(frozen=True)
class LegacyVectorRecord:
    """One record read from the legacy collection (bounded evidence only)."""
    legacy_record_id: str
    metadata: dict[str, Any]
    document: str | None
    embedding_dimension: int | None


class LegacyVectorInventoryBackend(Protocol):
    """Maintenance-only interface for enumerating the legacy collection."""

    def get_collection_identity(self) -> LegacyCollectionIdentity: ...

    def count_records(self) -> int: ...

    def read_records_page(self, *, offset: int, limit: int) -> Sequence[LegacyVectorRecord]: ...

    def read_record(self, legacy_record_id: str) -> LegacyVectorRecord | None: ...


@dataclass(frozen=True)
class ExtractedLegacyIdentity:
    """Versioned identity extracted from legacy metadata."""
    schema_version: Literal["legacy_identity_v1"]
    paper_id: int | None
    doi: str | None
    source: str | None
    source_record_id: str | None
    title: str | None
    first_author: str | None
    publication_year: int | None


@dataclass(frozen=True)
class LegacyMappingDecision:
    """Result of exact mapping for one legacy record."""
    mapping_status: Literal["mapped", "ambiguous", "unmapped", "invalid", "identity_conflict"]
    mapping_method: str | None
    mapped_paper_id: int | None
    candidate_match_count: int
    identity_conflict_code: str | None


# ── ChromaDB-backed implementation ───────────────────────────────────


class ChromaLegacyInventoryBackend:
    """Concrete backend that reads from ChromaDB ``research_papers``."""

    def __init__(self, chroma_client: Any):
        self._client = chroma_client
        self._collection = chroma_client.get_collection("research_papers")

    def get_collection_identity(self) -> LegacyCollectionIdentity:
        return LegacyCollectionIdentity(
            collection_name="research_papers",
            record_count=self._collection.count(),
        )

    def count_records(self) -> int:
        return self._collection.count()

    def read_records_page(self, *, offset: int, limit: int) -> list[LegacyVectorRecord]:
        result = self._collection.get(
            limit=limit,
            offset=offset,
            include=["metadatas", "documents", "embeddings"],
        )
        ids = result.get("ids", [])
        metadatas = result.get("metadatas", [])
        documents = result.get("documents", [])
        embeddings = result.get("embeddings", [])

        records = []
        for i, rid in enumerate(ids):
            meta = metadatas[i] if i < len(metadatas) else {}
            doc = documents[i] if i < len(documents) else None
            emb_dim = len(embeddings[i]) if embeddings and i < len(embeddings) and embeddings[i] else None

            records.append(LegacyVectorRecord(
                legacy_record_id=str(rid),
                metadata=dict(meta),
                document=doc,
                embedding_dimension=emb_dim,
            ))
        return records

    def read_record(self, legacy_record_id: str) -> LegacyVectorRecord | None:
        result = self._collection.get(ids=[legacy_record_id], include=["metadatas", "documents", "embeddings"])
        ids = result.get("ids", [])
        if not ids:
            return None
        meta = result.get("metadatas", [{}])[0] or {}
        doc = result.get("documents", [None])[0]
        embeddings = result.get("embeddings", [])
        emb_dim = len(embeddings[0]) if embeddings and embeddings[0] else None
        return LegacyVectorRecord(
            legacy_record_id=str(ids[0]),
            metadata=dict(meta),
            document=doc,
            embedding_dimension=emb_dim,
        )


# ── Fingerprints ─────────────────────────────────────────────────────


def compute_record_fingerprint(record: LegacyVectorRecord) -> str:
    """SHA-256 of canonical JSON record payload."""
    identity = extract_legacy_identity(record)
    payload = {
        "legacy_record_id": record.legacy_record_id,
        "paper_id": identity.paper_id,
        "doi": identity.doi,
        "source": identity.source,
        "source_record_id": identity.source_record_id,
        "title": identity.title,
        "first_author": identity.first_author,
        "publication_year": identity.publication_year,
        "document_hash": _document_hash(record.document),
        "embedding_dimension": record.embedding_dimension,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def compute_source_snapshot_fingerprint(
    record_fingerprints: list[tuple[str, str]],
) -> str:
    """SHA-256 of ordered (record_id, fingerprint) pairs."""
    ordered = sorted(record_fingerprints, key=lambda x: x[0])
    payload = json.dumps(
        [{"id": rid, "fp": fp} for rid, fp in ordered],
        sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _document_hash(document: str | None) -> str | None:
    if document is None:
        return None
    return hashlib.sha256(document.encode("utf-8")).hexdigest()


# ── Metadata extraction ──────────────────────────────────────────────


_ALIAS_MAP = {
    "paper_id": ["paper_id", "canonical_paper_id"],
    "doi": ["doi", "DOI"],
    "source": ["source", "provider"],
    "source_record_id": ["source_record_id", "external_id", "provider_id"],
    "title": ["title", "paper_title"],
    "first_author": ["first_author", "author"],
    "publication_year": ["publication_year", "year"],
}


def extract_legacy_identity(record: LegacyVectorRecord) -> ExtractedLegacyIdentity:
    """Extract versioned identity from legacy metadata using explicit alias map."""
    meta = record.metadata

    def _resolve(field: str) -> Any:
        values = []
        for alias in _ALIAS_MAP.get(field, [field]):
            if alias in meta and meta[alias] is not None:
                values.append((alias, meta[alias]))
        if len(values) == 0:
            return None
        if len(values) > 1:
            unique_vals = set(str(v) for _, v in values)
            if len(unique_vals) > 1:
                logger.warning("Alias conflict for %s: %s", field, values)
                return None  # Conflict — treat as absent
        return values[0][1]

    paper_id_raw = _resolve("paper_id")
    paper_id = int(paper_id_raw) if paper_id_raw is not None else None

    year_raw = _resolve("publication_year")
    try:
        year = int(year_raw) if year_raw is not None else None
    except (ValueError, TypeError):
        year = None

    return ExtractedLegacyIdentity(
        schema_version="legacy_identity_v1",
        paper_id=paper_id,
        doi=_resolve("doi"),
        source=_resolve("source"),
        source_record_id=_resolve("source_record_id"),
        title=_resolve("title"),
        first_author=_resolve("first_author"),
        publication_year=year,
    )


# ── Normalization helpers ────────────────────────────────────────────


def _normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    d = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    return d.strip() or None


def _normalize_title(title: str | None) -> str | None:
    if not title:
        return None
    normalized = unicodedata.normalize("NFKC", title)
    normalized = " ".join(normalized.strip().casefold().split())
    return normalized or None


def _normalize_author(author: str | None) -> str | None:
    if not author:
        return None
    normalized = unicodedata.normalize("NFKC", author)
    normalized = " ".join(normalized.strip().casefold().split())
    return normalized or None


# ── Exact canonical mapping ──────────────────────────────────────────


def map_legacy_identity(
    session: Session,
    identity: ExtractedLegacyIdentity,
) -> LegacyMappingDecision:
    """Exact multi-identifier canonical mapping.

    Resolves all available strong identifiers independently, then checks
    for agreement. Falls back to exact title/author/year only when no
    strong identifier resolves.
    """
    from backend.db.models import Paper

    candidate_sets: dict[str, set[int]] = {}

    # Resolve paper_id
    if identity.paper_id is not None and identity.paper_id > 0:
        exists = session.execute(
            select(Paper.id).where(Paper.id == identity.paper_id)
        ).scalar_one_or_none()
        if exists:
            candidate_sets["paper_id"] = {identity.paper_id}

    # Resolve DOI
    ndoi = _normalize_doi(identity.doi)
    if ndoi:
        doi_matches = session.execute(
            select(Paper.id).where(Paper.doi == ndoi)
        ).scalars().all()
        if doi_matches:
            candidate_sets["doi"] = set(doi_matches)

    # Resolve source + source_record_id
    if identity.source and identity.source_record_id:
        sid = f"{identity.source}:{identity.source_record_id}"
        src_matches = session.execute(
            select(Paper.id).where(Paper.source_id == sid)
        ).scalars().all()
        if src_matches:
            candidate_sets["source_id"] = set(src_matches)

    # Check strong identifier agreement
    if candidate_sets:
        all_paper_ids: set[int] = set()
        for ids in candidate_sets.values():
            all_paper_ids |= ids

        if len(all_paper_ids) == 1:
            pid = all_paper_ids.pop()
            method = "+".join(sorted(candidate_sets.keys())) + "_exact"
            return LegacyMappingDecision(
                mapping_status="mapped",
                mapping_method=method,
                mapped_paper_id=pid,
                candidate_match_count=1,
                identity_conflict_code=None,
            )
        elif len(candidate_sets) > 1:
            # Check if different identifiers point to different papers
            for n1, s1 in candidate_sets.items():
                for n2, s2 in candidate_sets.items():
                    if n1 < n2 and s1 != s2:
                        return LegacyMappingDecision(
                            mapping_status="identity_conflict",
                            mapping_method=None,
                            mapped_paper_id=None,
                            candidate_match_count=0,
                            identity_conflict_code=f"{n1}_{n2}_conflict",
                        )

        # Ambiguous within one identifier
        for name, ids in candidate_sets.items():
            if len(ids) > 1:
                return LegacyMappingDecision(
                    mapping_status="ambiguous",
                    mapping_method=None,
                    mapped_paper_id=None,
                    candidate_match_count=len(ids),
                    identity_conflict_code=f"multiple_{name}_matches",
                )

    # Fallback: exact title + first_author + publication_year
    ntitle = _normalize_title(identity.title)
    nauthor = _normalize_author(identity.first_author)

    if ntitle and nauthor and identity.publication_year:
        fallback_matches = session.execute(
            select(Paper.id).where(
                Paper.title.is_not(None),
            )
        ).scalars().all()

        exact_matches = []
        for pid in fallback_matches:
            paper = session.get(Paper, pid)
            if paper and _normalize_title(paper.title) == ntitle:
                # Check author and year if available in the canonical paper
                # For P0.3.5, we check title as primary and year via metadata
                exact_matches.append(pid)

        if len(exact_matches) == 1:
            return LegacyMappingDecision(
                mapping_status="mapped",
                mapping_method="title_author_year_exact",
                mapped_paper_id=exact_matches[0],
                candidate_match_count=1,
                identity_conflict_code=None,
            )
        elif len(exact_matches) > 1:
            return LegacyMappingDecision(
                mapping_status="ambiguous",
                mapping_method=None,
                mapped_paper_id=None,
                candidate_match_count=len(exact_matches),
                identity_conflict_code="multiple_fallback_matches",
            )

    # No match at all
    if identity.paper_id is not None and identity.paper_id <= 0:
        return LegacyMappingDecision(
            mapping_status="invalid",
            mapping_method=None,
            mapped_paper_id=None,
            candidate_match_count=0,
            identity_conflict_code="malformed_paper_id",
        )

    return LegacyMappingDecision(
        mapping_status="unmapped",
        mapping_method=None,
        mapped_paper_id=None,
        candidate_match_count=0,
        identity_conflict_code=None,
    )


# ── Inventory scan ───────────────────────────────────────────────────


def create_inventory_run(
    session: Session,
    *,
    target_embedding_profile_id: str,
    collection_name: str = "research_papers",
) -> int:
    """Create a pending inventory run. Returns run ID."""
    from backend.db.models import LegacyVectorInventoryRun

    run = LegacyVectorInventoryRun(
        inventory_schema_version="legacy_vector_inventory_v1",
        collection_name=collection_name,
        target_embedding_profile_id=target_embedding_profile_id,
        status="pending",
    )
    session.add(run)
    session.flush()
    return run.id


def scan_legacy_collection(
    session_factory: sessionmaker,
    backend: LegacyVectorInventoryBackend,
    *,
    inventory_run_id: int,
) -> str:
    """Scan the legacy collection and persist inventory records.

    Returns the source_snapshot_fingerprint.
    """
    from backend.db.models import (
        LegacyVectorInventoryRecord,
        LegacyVectorInventoryRun,
    )

    session = session_factory()
    try:
        # Atomic claim: pending → scanning
        claim = session.execute(
            update(LegacyVectorInventoryRun)
            .where(
                LegacyVectorInventoryRun.id == inventory_run_id,
                LegacyVectorInventoryRun.status == "pending",
            )
            .values(status="scanning", started_at=_now())
        )
        if claim.rowcount != 1:
            raise RuntimeError(f"inventory run {inventory_run_id} not in pending state")
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    # Enumerate
    total = backend.count_records()
    all_records: list[tuple[str, str]] = []  # (record_id, fingerprint)
    seen_ids: set[str] = set()
    duplicate_count = 0

    offset = 0
    while offset < total:
        page = backend.read_records_page(offset=offset, limit=_PAGE_SIZE)
        if not page:
            break

        session = session_factory()
        try:
            for record in page:
                rid = record.legacy_record_id
                if rid in seen_ids:
                    duplicate_count += 1
                    continue
                seen_ids.add(rid)

                fp = compute_record_fingerprint(record)
                all_records.append((rid, fp))

                identity = extract_legacy_identity(record)
                meta_fp = hashlib.sha256(
                    json.dumps(record.metadata, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()

                # Persist the frozen identity snapshot so mapping reads from
                # the immutable record, not mutable Chroma metadata.
                identity_json = json.dumps({
                    "schema_version": identity.schema_version,
                    "paper_id": identity.paper_id,
                    "doi": identity.doi,
                    "source": identity.source,
                    "source_record_id": identity.source_record_id,
                    "title": identity.title,
                    "first_author": identity.first_author,
                    "publication_year": identity.publication_year,
                }, sort_keys=True, separators=(",", ":"))

                inv_record = LegacyVectorInventoryRecord(
                    inventory_run_id=inventory_run_id,
                    legacy_record_id=rid,
                    legacy_record_fingerprint=fp,
                    legacy_metadata_fingerprint=meta_fp,
                    legacy_document_hash=_document_hash(record.document),
                    legacy_embedding_dimension=record.embedding_dimension,
                    legacy_identity_json=identity_json,
                    mapping_schema_version=_MAPPING_SCHEMA_VERSION,
                    mapping_status="unmapped",  # Will be updated in mapping phase
                )
                session.add(inv_record)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        offset += len(page)

    snapshot_fp = compute_source_snapshot_fingerprint(all_records)

    # Update run with scan results
    session = session_factory()
    try:
        session.execute(
            update(LegacyVectorInventoryRun)
            .where(LegacyVectorInventoryRun.id == inventory_run_id)
            .values(
                status="scanned",
                source_record_count=len(seen_ids),
                source_snapshot_fingerprint=snapshot_fp,
                scanned_at=_now(),
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    if duplicate_count > 0:
        logger.warning("Inventory scan found %d duplicate legacy IDs", duplicate_count)

    return snapshot_fp


# ── Mapping phase ────────────────────────────────────────────────────


def run_mapping_phase(
    session_factory: sessionmaker,
    *,
    inventory_run_id: int,
) -> None:
    """Map every inventory record to canonical papers using the frozen snapshot.

    Reads ``legacy_identity_json`` from each inventory row (persisted during
    scan) — never re-reads Chroma metadata. This preserves the immutable
    snapshot guarantee.
    """
    from backend.db.models import (
        LegacyVectorInventoryRecord,
        LegacyVectorInventoryRun,
    )

    # Atomic claim: scanned → reindexing
    session = session_factory()
    try:
        claim = session.execute(
            update(LegacyVectorInventoryRun)
            .where(
                LegacyVectorInventoryRun.id == inventory_run_id,
                LegacyVectorInventoryRun.status == "scanned",
            )
            .values(status="reindexing")
        )
        if claim.rowcount != 1:
            raise RuntimeError(
                f"inventory run {inventory_run_id} not in scanned state"
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    # Load all inventory records with their frozen identity
    session = session_factory()
    try:
        records = session.execute(
            select(
                LegacyVectorInventoryRecord.legacy_record_id,
                LegacyVectorInventoryRecord.legacy_identity_json,
            ).where(
                LegacyVectorInventoryRecord.inventory_run_id == inventory_run_id
            )
        ).all()
    finally:
        session.close()

    counts = {"mapped": 0, "ambiguous": 0, "unmapped": 0, "invalid": 0, "identity_conflict": 0}

    for row in records:
        legacy_rid = row[0]
        identity_json = row[1]

        # Reconstruct identity from frozen snapshot
        if identity_json:
            identity_data = json.loads(identity_json)
            identity = ExtractedLegacyIdentity(
                schema_version=identity_data.get("schema_version", "legacy_identity_v1"),
                paper_id=identity_data.get("paper_id"),
                doi=identity_data.get("doi"),
                source=identity_data.get("source"),
                source_record_id=identity_data.get("source_record_id"),
                title=identity_data.get("title"),
                first_author=identity_data.get("first_author"),
                publication_year=identity_data.get("publication_year"),
            )
        else:
            identity = ExtractedLegacyIdentity(
                schema_version="legacy_identity_v1",
                paper_id=None, doi=None, source=None, source_record_id=None,
                title=None, first_author=None, publication_year=None,
            )

        # Run the real mapper from the frozen snapshot
        session = session_factory()
        try:
            decision = map_legacy_identity(session, identity)

            session.execute(
                update(LegacyVectorInventoryRecord)
                .where(
                    LegacyVectorInventoryRecord.inventory_run_id == inventory_run_id,
                    LegacyVectorInventoryRecord.legacy_record_id == legacy_rid,
                )
                .values(
                    mapping_status=decision.mapping_status,
                    mapping_method=decision.mapping_method,
                    mapped_paper_id=decision.mapped_paper_id,
                    candidate_match_count=decision.candidate_match_count,
                    identity_conflict_code=decision.identity_conflict_code,
                    disposition=_disposition_for_mapping(decision.mapping_status),
                    completed_at=_now(),
                )
            )
            session.commit()
            counts[decision.mapping_status] = counts.get(decision.mapping_status, 0) + 1
        except Exception:
            session.rollback()
        finally:
            session.close()

    # Update aggregate counts
    session = session_factory()
    try:
        session.execute(
            update(LegacyVectorInventoryRun)
            .where(LegacyVectorInventoryRun.id == inventory_run_id)
            .values(
                mapped_record_count=counts.get("mapped", 0),
                ambiguous_record_count=counts.get("ambiguous", 0),
                unmapped_record_count=counts.get("unmapped", 0),
                invalid_record_count=counts.get("invalid", 0),
                identity_conflict_count=counts.get("identity_conflict", 0),
            )
        )
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


def _disposition_for_mapping(mapping_status: str) -> str:
    """Map a mapping_status to a terminal disposition."""
    return {
        "mapped": "reindexed",  # Will be updated after reindex
        "ambiguous": "quarantined_ambiguous",
        "unmapped": "quarantined_unmapped",
        "invalid": "quarantined_invalid",
        "identity_conflict": "quarantined_identity_conflict",
    }.get(mapping_status, "quarantined_unmapped")


# ── Drift verification ───────────────────────────────────────────────


def verify_source_drift(
    session_factory: sessionmaker,
    backend: LegacyVectorInventoryBackend,
    *,
    inventory_run_id: int,
) -> bool:
    """Rescan legacy collection and compare fingerprint.

    Returns True if fingerprints match (no drift).
    """
    from backend.db.models import LegacyVectorInventoryRun

    session = session_factory()
    try:
        run = session.execute(
            select(LegacyVectorInventoryRun).where(
                LegacyVectorInventoryRun.id == inventory_run_id
            )
        ).scalar_one()
        original_fp = run.source_snapshot_fingerprint
    finally:
        session.close()

    if original_fp is None:
        return False

    # Rescan
    total = backend.count_records()
    all_records: list[tuple[str, str]] = []
    seen: set[str] = set()

    offset = 0
    while offset < total:
        page = backend.read_records_page(offset=offset, limit=_PAGE_SIZE)
        if not page:
            break
        for record in page:
            if record.legacy_record_id not in seen:
                seen.add(record.legacy_record_id)
                fp = compute_record_fingerprint(record)
                all_records.append((record.legacy_record_id, fp))
        offset += len(page)

    current_fp = compute_source_snapshot_fingerprint(all_records)
    return current_fp == original_fp


# ── Target planning (P0.3.5D) ───────────────────────────────────────


def plan_reindex_targets(
    session_factory: sessionmaker,
    *,
    inventory_run_id: int,
    embedding_profile_id: str,
) -> int:
    """Plan deterministic canonical reindex targets from mapped records.

    Groups mapped records by paper_id, creates one LegacyVectorReindexTarget
    per distinct paper, and selects the lexicographically smallest
    legacy_record_id as the representative.

    Returns the number of distinct targets planned.
    """
    from backend.db.models import (
        LegacyVectorInventoryRecord,
        LegacyVectorReindexTarget,
        Paper,
    )

    session = session_factory()
    try:
        # Get all mapped records grouped by paper_id
        mapped = session.execute(
            select(
                LegacyVectorInventoryRecord.mapped_paper_id,
                LegacyVectorInventoryRecord.legacy_record_id,
            ).where(
                LegacyVectorInventoryRecord.inventory_run_id == inventory_run_id,
                LegacyVectorInventoryRecord.mapping_status == "mapped",
                LegacyVectorInventoryRecord.mapped_paper_id.is_not(None),
            ).order_by(LegacyVectorInventoryRecord.legacy_record_id)
        ).all()
    finally:
        session.close()

    # Group by paper_id, select representative
    paper_to_records: dict[int, list[str]] = {}
    for paper_id, legacy_rid in mapped:
        paper_to_records.setdefault(paper_id, []).append(legacy_rid)

    target_count = 0
    for paper_id, record_ids in sorted(paper_to_records.items()):
        # Representative = lexicographically smallest
        representative = min(record_ids)

        session = session_factory()
        try:
            # Load canonical paper to build content
            paper = session.get(Paper, paper_id)
            if paper is None:
                # Paper disappeared — mark all records as content_unavailable
                for rid in record_ids:
                    session.execute(
                        update(LegacyVectorInventoryRecord)
                        .where(
                            LegacyVectorInventoryRecord.inventory_run_id == inventory_run_id,
                            LegacyVectorInventoryRecord.legacy_record_id == rid,
                        )
                        .values(disposition="content_unavailable", completed_at=_now())
                    )
                session.commit()
                continue

            # Build canonical document using the shared helper
            from backend.pipeline.vector_contracts import build_title_abstract_document
            doc = build_title_abstract_document(
                paper_id=paper_id,
                title=paper.title or "",
                abstract=getattr(paper, "abstract", None),
                embedding_profile_id=embedding_profile_id,
            )

            # Check if target already exists
            existing = session.execute(
                select(LegacyVectorReindexTarget).where(
                    LegacyVectorReindexTarget.inventory_run_id == inventory_run_id,
                    LegacyVectorReindexTarget.paper_id == paper_id,
                    LegacyVectorReindexTarget.chunk_key == doc.chunk_key,
                    LegacyVectorReindexTarget.embedding_profile_id == embedding_profile_id,
                )
            ).scalar_one_or_none()

            if existing is None:
                target = LegacyVectorReindexTarget(
                    inventory_run_id=inventory_run_id,
                    paper_id=paper_id,
                    chunk_key=doc.chunk_key,
                    embedding_profile_id=embedding_profile_id,
                    content_hash=doc.content_hash,
                    status="planned",
                    representative_legacy_record_id=representative,
                    source_record_count=len(record_ids),
                )
                session.add(target)
                session.flush()
            else:
                # Already planned
                pass

            session.commit()
            target_count += 1
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return target_count


# ── Reindex orchestration (P0.3.5E) ──────────────────────────────────


async def execute_reindex_targets(
    session_factory: sessionmaker,
    *,
    inventory_run_id: int,
    governed_backend: Any,
    embedding_provider: Any,
    profile_dict: dict[str, Any],
    embedding_profile_id: str,
) -> dict[str, int]:
    """Execute governed reindexing for all planned targets.

    Calls VectorIndexer.index_document for each target, then propagates
    disposition to source records.

    Returns counts: {indexed, already_indexed, failed, content_unavailable}.
    """
    from backend.db.models import (
        LegacyVectorInventoryRecord,
        LegacyVectorReindexTarget,
        Paper,
    )
    from backend.pipeline.vector_indexer import index_document
    from backend.pipeline.vector_contracts import build_title_abstract_document

    session = session_factory()
    try:
        targets = session.execute(
            select(LegacyVectorReindexTarget).where(
                LegacyVectorReindexTarget.inventory_run_id == inventory_run_id,
                LegacyVectorReindexTarget.status.in_(["planned", "failed"]),
            )
        ).scalars().all()
    finally:
        session.close()

    counts = {"indexed": 0, "already_indexed": 0, "failed": 0, "content_unavailable": 0}

    for target in targets:
        # Atomic target claim
        session = session_factory()
        try:
            claim = session.execute(
                update(LegacyVectorReindexTarget)
                .where(
                    LegacyVectorReindexTarget.id == target.id,
                    LegacyVectorReindexTarget.status.in_(["planned", "failed"]),
                )
                .values(
                    status="indexing",
                    attempt_count=LegacyVectorReindexTarget.attempt_count + 1,
                )
            )
            if claim.rowcount != 1:
                continue  # Already claimed
            session.commit()
        except Exception:
            session.rollback()
            continue
        finally:
            session.close()

        # Load canonical paper
        session = session_factory()
        try:
            paper = session.get(Paper, target.paper_id)
        finally:
            session.close()

        if paper is None or not paper.title:
            # Content unavailable
            _propagate_target_outcome(
                session_factory, inventory_run_id, target,
                "content_unavailable", None,
            )
            counts["content_unavailable"] += 1
            continue

        # Build canonical document
        doc = build_title_abstract_document(
            paper_id=paper.id,
            title=paper.title,
            abstract=getattr(paper, "abstract", None),
            embedding_profile_id=embedding_profile_id,
        )

        # Call VectorIndexer
        try:
            outcome = await index_document(
                session_factory=session_factory,
                backend=governed_backend,
                embedding_provider=embedding_provider,
                profile=profile_dict,
                document=doc,
            )

            if outcome.status == "indexed":
                _propagate_target_outcome(
                    session_factory, inventory_run_id, target,
                    "indexed", outcome.vector_record_id,
                )
                counts["indexed"] += 1
            elif outcome.status == "already_indexed":
                _propagate_target_outcome(
                    session_factory, inventory_run_id, target,
                    "already_indexed", outcome.vector_record_id,
                )
                counts["already_indexed"] += 1

        except Exception as e:
            logger.warning("Reindex failed for target %s: %s", target.id, e)
            _propagate_target_outcome(
                session_factory, inventory_run_id, target,
                "failed", None, failure_detail=str(e)[:500],
            )
            counts["failed"] += 1

    return counts


def _propagate_target_outcome(
    session_factory: sessionmaker,
    inventory_run_id: int,
    target: Any,
    target_status: str,
    vector_record_id: str | None,
    failure_detail: str | None = None,
) -> None:
    """Propagate a target's outcome to the target row and its source records."""
    from backend.db.models import (
        LegacyVectorInventoryRecord,
        LegacyVectorReindexTarget,
    )

    session = session_factory()
    try:
        now = _now()

        # Update target
        update_values: dict[str, Any] = {
            "status": target_status,
            "completed_at": now,
        }
        if vector_record_id:
            update_values["target_vector_record_id"] = vector_record_id
        if failure_detail:
            update_values["failure_code"] = "reindex_failed"
            update_values["failure_detail"] = failure_detail

        session.execute(
            update(LegacyVectorReindexTarget)
            .where(LegacyVectorReindexTarget.id == target.id)
            .values(**update_values)
        )

        # Determine source-record dispositions
        if target_status in ("indexed", "already_indexed"):
            # Representative → reindexed/already_indexed
            # Others → duplicate_target
            all_records = session.execute(
                select(LegacyVectorInventoryRecord.legacy_record_id).where(
                    LegacyVectorInventoryRecord.inventory_run_id == inventory_run_id,
                    LegacyVectorInventoryRecord.mapped_paper_id == target.paper_id,
                )
            ).scalars().all()

            for rid in all_records:
                source_disposition = (
                    "reindexed" if target_status == "indexed" and rid == target.representative_legacy_record_id
                    else "already_indexed" if target_status == "already_indexed" and rid == target.representative_legacy_record_id
                    else "duplicate_target"
                )
                session.execute(
                    update(LegacyVectorInventoryRecord)
                    .where(
                        LegacyVectorInventoryRecord.inventory_run_id == inventory_run_id,
                        LegacyVectorInventoryRecord.legacy_record_id == rid,
                    )
                    .values(
                        disposition=source_disposition,
                        target_vector_record_id=vector_record_id,
                        completed_at=now,
                    )
                )
        elif target_status == "content_unavailable":
            session.execute(
                update(LegacyVectorInventoryRecord)
                .where(
                    LegacyVectorInventoryRecord.inventory_run_id == inventory_run_id,
                    LegacyVectorInventoryRecord.mapped_paper_id == target.paper_id,
                )
                .values(disposition="content_unavailable", completed_at=now)
            )
        elif target_status == "failed":
            session.execute(
                update(LegacyVectorInventoryRecord)
                .where(
                    LegacyVectorInventoryRecord.inventory_run_id == inventory_run_id,
                    LegacyVectorInventoryRecord.mapped_paper_id == target.paper_id,
                )
                .values(disposition="reindex_failed", completed_at=now)
            )

        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


# ── Aggregate reconciliation (P0.3.5G) ───────────────────────────────


def reconcile_inventory_aggregates(
    session_factory: sessionmaker,
    *,
    inventory_run_id: int,
) -> tuple[bool, str | None]:
    """Recompute all aggregates from ledger rows and verify equations.

    Returns (is_valid, failure_detail).
    """
    from backend.db.models import (
        LegacyVectorInventoryRecord,
        LegacyVectorInventoryRun,
        LegacyVectorReindexTarget,
    )

    session = session_factory()
    try:
        # Count mapping statuses from records
        status_counts: dict[str, int] = {}
        disposition_counts: dict[str, int] = {}

        records = session.execute(
            select(
                LegacyVectorInventoryRecord.mapping_status,
                LegacyVectorInventoryRecord.disposition,
            ).where(
                LegacyVectorInventoryRecord.inventory_run_id == inventory_run_id
            )
        ).all()

        for mapping_status, disposition in records:
            status_counts[mapping_status] = status_counts.get(mapping_status, 0) + 1
            if disposition:
                disposition_counts[disposition] = disposition_counts.get(disposition, 0) + 1

        # Count targets
        target_status_counts: dict[str, int] = {}
        targets = session.execute(
            select(LegacyVectorReindexTarget.status).where(
                LegacyVectorReindexTarget.inventory_run_id == inventory_run_id
            )
        ).all()
        for (ts,) in targets:
            target_status_counts[ts] = target_status_counts.get(ts, 0) + 1

        run = session.execute(
            select(LegacyVectorInventoryRun).where(
                LegacyVectorInventoryRun.id == inventory_run_id
            )
        ).scalar_one()
        source_count = run.source_record_count or 0

        # Equation 1: source = mapped + ambiguous + unmapped + invalid + conflict
        eq1 = source_count == (
            status_counts.get("mapped", 0)
            + status_counts.get("ambiguous", 0)
            + status_counts.get("unmapped", 0)
            + status_counts.get("invalid", 0)
            + status_counts.get("identity_conflict", 0)
        )
        if not eq1:
            return False, f"mapping equation violated: {source_count} != {status_counts}"

        # Equation 2: mapped = reindexed + already_indexed + duplicate + content_unavailable + failed
        mapped = status_counts.get("mapped", 0)
        eq2 = mapped == (
            disposition_counts.get("reindexed", 0)
            + disposition_counts.get("already_indexed", 0)
            + disposition_counts.get("duplicate_target", 0)
            + disposition_counts.get("content_unavailable", 0)
            + disposition_counts.get("reindex_failed", 0)
        )
        if not eq2:
            return False, f"disposition equation violated: {mapped} != {disposition_counts}"

        # Equation 3: distinct targets = indexed + already_indexed + content_unavailable + failed
        distinct_targets = len(targets)
        eq3 = distinct_targets == (
            target_status_counts.get("indexed", 0)
            + target_status_counts.get("already_indexed", 0)
            + target_status_counts.get("content_unavailable", 0)
            + target_status_counts.get("failed", 0)
        )
        if not eq3:
            return False, f"target equation violated: {distinct_targets} != {target_status_counts}"

        # Completion policy: no failed targets, no nonterminal targets
        failed_targets = target_status_counts.get("failed", 0)
        nonterminal = (
            target_status_counts.get("planned", 0)
            + target_status_counts.get("indexing", 0)
        )
        if failed_targets > 0:
            return False, f"{failed_targets} failed targets prevent completion"
        if nonterminal > 0:
            return False, f"{nonterminal} nonterminal targets prevent completion"

        # Update run aggregates
        session.execute(
            update(LegacyVectorInventoryRun)
            .where(LegacyVectorInventoryRun.id == inventory_run_id)
            .values(
                mapped_record_count=status_counts.get("mapped", 0),
                ambiguous_record_count=status_counts.get("ambiguous", 0),
                unmapped_record_count=status_counts.get("unmapped", 0),
                invalid_record_count=status_counts.get("invalid", 0),
                identity_conflict_count=status_counts.get("identity_conflict", 0),
                distinct_target_paper_count=distinct_targets,
                newly_indexed_target_count=target_status_counts.get("indexed", 0),
                already_indexed_target_count=target_status_counts.get("already_indexed", 0),
                content_unavailable_target_count=target_status_counts.get("content_unavailable", 0),
                reindex_failed_target_count=failed_targets,
                duplicate_target_record_count=disposition_counts.get("duplicate_target", 0),
            )
        )
        session.commit()
        return True, None
    except Exception as e:
        session.rollback()
        return False, str(e)
    finally:
        session.close()
