"""Transport-neutral vector retrieval scope contracts (P0.3.1).

These contracts define how a governed vector retrieval declares its scope,
how that scope is resolved into an authoritative paper set, and what
metadata is recorded for audit. The actual backend query engine is P0.3.3.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from typing import Literal, Sequence


# ── Domain identity ──────────────────────────────────────────────────


def derive_domain_scope_key(domain: str) -> str:
    """Compute a deterministic domain scope key.

    Normalization: NFKC + casefold + whitespace collapse.
    Different phrasings are NOT equivalent — this is exact normalized reuse,
    not semantic domain matching.
    """
    normalized = unicodedata.normalize("NFKC", domain)
    normalized = " ".join(normalized.strip().casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# ── Embedding profile ────────────────────────────────────────────────


@dataclass(frozen=True)
class EmbeddingProfileRef:
    """Declarative embedding profile identity.

    P0.3 proves profile isolation, not embedding health. The profile remains
    unverified until P0.4 performs the model-resolution handshake.
    """

    provider: str
    model_identifier: str
    dimension: int
    normalization_policy: str
    chunking_schema_version: str

    @property
    def profile_id(self) -> str:
        """Canonical SHA-256 of the profile identity."""
        canonical = json.dumps(
            {
                "provider": self.provider,
                "model_identifier": self.model_identifier,
                "dimension": self.dimension,
                "normalization_policy": self.normalization_policy,
                "chunking_schema_version": self.chunking_schema_version,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode()).hexdigest()


# ── Scope contracts ──────────────────────────────────────────────────


@dataclass(frozen=True)
class VectorRetrievalScope:
    """Declared scope for a governed vector retrieval.

    The scope declares *which* papers a retrieval may search, *not* the
    query itself. The resolver converts this into a concrete allowed-paper set.
    """

    schema_version: Literal["vector_scope_v1"]
    mode: Literal[
        "current_run_only",
        "same_domain_prior_runs",
        "global_library",
        "selected_papers",
    ]
    run_id: int
    embedding_profile_id: str
    selected_paper_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class ResolvedVectorScope:
    """Immutable snapshot of a resolved vector retrieval scope.

    The allowed_paper_ids are the authoritative set of papers the retrieval
    may search. indexed_paper_ids are the subset that have verified governed
    vector records.
    """

    schema_version: Literal["resolved_vector_scope_v1"]
    mode: str
    run_id: int
    embedding_profile_id: str

    allowed_paper_ids: tuple[int, ...]
    allowed_paper_count: int

    indexed_paper_ids: tuple[int, ...]
    indexed_paper_count: int

    eligible_vector_record_count: int
    scope_fingerprint: str


def compute_scope_fingerprint(
    run_id: int,
    mode: str,
    embedding_profile_id: str,
    allowed_paper_ids: Sequence[int],
    indexed_paper_ids: Sequence[int],
    domain_scope_key: str | None = None,
) -> str:
    """Compute a deterministic SHA-256 scope fingerprint."""
    data = {
        "run_id": run_id,
        "mode": mode,
        "domain_scope_key": domain_scope_key,
        "embedding_profile_id": embedding_profile_id,
        "allowed_paper_ids": sorted(allowed_paper_ids),
        "indexed_paper_ids": sorted(indexed_paper_ids),
    }
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


# ── Retrieval request and result ─────────────────────────────────────


@dataclass(frozen=True)
class ScopedVectorRetrievalRequest:
    """Request for a scoped vector retrieval."""

    schema_version: Literal["vector_retrieval_v1"]
    run_id: int
    stage_name: str
    retrieval_key: str
    scope: VectorRetrievalScope
    query_vector: tuple[float, ...]
    top_k: int
    allow_partial_index_coverage: bool = False


@dataclass(frozen=True)
class ScopedVectorResult:
    """One ranked result from a scoped vector retrieval."""

    vector_record_id: str
    paper_id: int
    chunk_key: str
    content_kind: str
    raw_score: float
    rank: int


# ── Vector document and identity (P0.3.2) ────────────────────────────


@dataclass(frozen=True)
class VectorIndexDocument:
    """Deterministic canonical paper chunk for governed indexing."""

    schema_version: Literal["vector_document_v1"]

    paper_id: int
    chunk_key: str
    content_kind: Literal[
        "title_abstract",
        "abstract",
        "full_text_chunk",
        "metadata",
    ]
    content_text: str
    content_hash: str

    embedding_profile_id: str


@dataclass(frozen=True)
class VectorIndexingOutcome:
    """Result of a governed indexing operation."""

    vector_record_id: str
    paper_id: int
    chunk_key: str
    embedding_profile_id: str
    status: Literal["indexed", "already_indexed"]
    attempt_count: int


def compute_content_hash(content_text: str) -> str:
    """SHA-256 of the exact normalized text supplied to the embedding provider."""
    return hashlib.sha256(content_text.encode("utf-8")).hexdigest()


def compute_vector_record_id(
    paper_id: int,
    chunk_key: str,
    content_hash: str,
    embedding_profile_id: str,
) -> str:
    """Deterministic vector identity from canonical JSON."""
    payload = {
        "schema": "vector_index_v1",
        "paper_id": paper_id,
        "chunk_key": chunk_key,
        "content_hash": content_hash,
        "embedding_profile_id": embedding_profile_id,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def compute_profile_id(
    provider: str,
    model_identifier: str,
    dimension: int,
    normalization_policy: str,
    chunking_schema_version: str,
) -> str:
    """Canonical embedding profile ID from canonical JSON."""
    payload = {
        "schema": "embedding_profile_v1",
        "provider": provider,
        "model_identifier": model_identifier,
        "dimension": dimension,
        "normalization_policy": normalization_policy,
        "chunking_schema_version": chunking_schema_version,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def compute_collection_name(embedding_profile_id: str) -> str:
    """Derive the deterministic governed collection name."""
    return f"erlab_vectors_v1_{embedding_profile_id[:24]}"


# ── Exceptions ───────────────────────────────────────────────────────


class VectorScopeError(Exception):
    """Base class for vector scope errors."""


class VectorScopeDriftError(VectorScopeError):
    """Scope fingerprint changed on replay."""


class VectorRetrievalDriftError(VectorScopeError):
    """Retrieval input fingerprint changed on replay."""


class IndexCoverageIncomplete(VectorScopeError):
    """Allowed papers exist but some are not indexed under the requested profile."""

    def __init__(self, allowed: int, indexed: int):
        self.allowed = allowed
        self.indexed = indexed
        super().__init__(
            f"index coverage incomplete: {indexed}/{allowed} papers indexed"
        )


class MixedVectorModeError(VectorScopeError):
    """Governed run used legacy unscoped query, or vice versa."""


class EmbeddingProfileDriftError(VectorScopeError):
    """Same profile ID with different declaration fields."""


class VectorIndexRegistryDriftError(VectorScopeError):
    """Same vector_record_id resolves to different registry content."""


class IndexingAlreadyClaimedError(VectorScopeError):
    """Another worker has already claimed the indexing for this vector."""


class RetrievalAlreadyClaimedError(VectorScopeError):
    """Another worker has already claimed the retrieval event."""


# ── Retrieval snapshot and outcome contracts (P0.3.3) ────────────────


@dataclass(frozen=True)
class EligibleVectorSnapshot:
    """One eligible indexed vector record in a retrieval's candidate set."""

    vector_record_id: str
    paper_id: int
    chunk_key: str
    content_kind: str
    collection_name: str
    embedding_profile_id: str


@dataclass(frozen=True)
class ScopedVectorRetrievalOutcome:
    """Result of a governed scoped vector retrieval."""

    retrieval_event_id: int
    status: Literal["success", "replayed"]
    coverage_status: Literal["empty_scope", "complete", "partial", "none"]
    allowed_paper_count: int
    indexed_paper_count: int
    eligible_vector_record_count: int
    results: tuple["ScopedVectorResult", ...]
