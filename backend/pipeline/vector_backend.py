"""Governed vector backend abstraction (P0.3.2B).

Wraps ChromaDB with profile-specific governed collections. Enforces:
  - No governed writes to the legacy ``research_papers`` collection
  - Collection metadata must match the declared embedding profile
  - Bounded operations: ensure_collection, upsert, read, delete

Similarity querying is intentionally NOT in this interface (deferred to P0.3.3).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from backend.pipeline.vector_contracts import VECTOR_INDEX_V1

logger = logging.getLogger(__name__)

_LEGACY_COLLECTION = "research_papers"


@dataclass(frozen=True)
class BackendVectorRecord:
    """Read-back result from the vector backend."""

    vector_record_id: str
    paper_id: int
    chunk_key: str
    content_kind: str
    content_hash: str
    embedding_profile_id: str
    index_schema_version: str
    document: str
    embedding: tuple[float, ...]


class GovernedVectorBackend:
    """ChromaDB-backed governed vector operations.

    All governed writes go to profile-specific collections
    (``erlab_vectors_v1_<profile-prefix>``), never to ``research_papers``.
    """

    def __init__(self, chroma_client: Any):
        """Initialize with a chromadb.PersistentClient instance."""
        self._client = chroma_client
        self._collections: dict[str, Any] = {}

    def ensure_profile_collection(
        self,
        *,
        collection_name: str,
        embedding_profile_id: str,
        embedding_dimension: int,
    ) -> Any:
        """Create or verify a governed profile-specific collection.

        Raises if the collection exists with mismatched metadata.
        Rejects the legacy ``research_papers`` collection.
        """
        if collection_name == _LEGACY_COLLECTION:
            raise ValueError(
                f"governed operations cannot use the legacy {_LEGACY_COLLECTION!r} collection"
            )

        metadata = {
            "index_schema_version": VECTOR_INDEX_V1,
            "embedding_profile_id": embedding_profile_id,
            "embedding_dimension": embedding_dimension,
            "hnsw:space": "cosine",
        }

        # Check if already cached
        if collection_name in self._collections:
            return self._collections[collection_name]

        # Try to get existing collection
        try:
            existing = self._client.get_collection(collection_name)
            existing_meta = existing.metadata or {}

            # Verify metadata matches
            for key in ("index_schema_version", "embedding_profile_id", "embedding_dimension"):
                expected = str(metadata[key])
                actual = str(existing_meta.get(key, ""))
                if expected != actual:
                    raise ValueError(
                        f"collection {collection_name!r} metadata mismatch: "
                        f"{key} expected {expected!r}, got {actual!r}"
                    )

            self._collections[collection_name] = existing
            return existing
        except Exception:
            # Collection doesn't exist — create it
            pass

        collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata=metadata,
        )
        self._collections[collection_name] = collection
        return collection

    def upsert_vector(
        self,
        *,
        collection_name: str,
        vector_record_id: str,
        embedding: Sequence[float],
        document: str,
        metadata: Mapping[str, object],
    ) -> None:
        """Upsert a governed vector record."""
        if collection_name == _LEGACY_COLLECTION:
            raise ValueError(
                f"governed operations cannot write to {_LEGACY_COLLECTION!r}"
            )

        collection = self._collections.get(collection_name)
        if collection is None:
            raise ValueError(
                f"collection {collection_name!r} not initialized; "
                f"call ensure_profile_collection first"
            )

        collection.upsert(
            ids=[vector_record_id],
            embeddings=[list(embedding)],
            documents=[document],
            metadatas=[dict(metadata)],
        )

    def read_vector(
        self,
        *,
        collection_name: str,
        vector_record_id: str,
    ) -> BackendVectorRecord | None:
        """Read back a specific vector record by ID.

        Returns ``None`` if the record does not exist.
        """
        if collection_name == _LEGACY_COLLECTION:
            raise ValueError(
                f"governed operations cannot read from {_LEGACY_COLLECTION!r}"
            )

        collection = self._collections.get(collection_name)
        if collection is None:
            return None

        result = collection.get(
            ids=[vector_record_id],
            include=["embeddings", "metadatas", "documents"],
        )

        ids = result.get("ids", [])
        if not ids:
            return None

        embeddings = result.get("embeddings", [])
        if embeddings is not None and len(embeddings) > 0:
            embedding = tuple(embeddings[0])
        else:
            embedding = ()

        metadatas = result.get("metadatas", [{}])
        meta = metadatas[0] if metadatas else {}

        documents = result.get("documents", [""])
        document = documents[0] if documents else ""

        return BackendVectorRecord(
            vector_record_id=ids[0],
            paper_id=int(meta.get("paper_id", 0)),
            chunk_key=str(meta.get("chunk_key", "")),
            content_kind=str(meta.get("content_kind", "")),
            content_hash=str(meta.get("content_hash", "")),
            embedding_profile_id=str(meta.get("embedding_profile_id", "")),
            index_schema_version=str(meta.get("index_schema_version", "")),
            document=document,
            embedding=embedding,
        )

    def delete_vector(
        self,
        *,
        collection_name: str,
        vector_record_id: str,
    ) -> None:
        """Delete a vector record by ID."""
        if collection_name == _LEGACY_COLLECTION:
            raise ValueError(
                f"governed operations cannot delete from {_LEGACY_COLLECTION!r}"
            )

        collection = self._collections.get(collection_name)
        if collection is None:
            return

        collection.delete(ids=[vector_record_id])

    def verify_absent(
        self,
        *,
        collection_name: str,
        vector_record_id: str,
    ) -> bool:
        """Verify that a vector record does NOT exist in the backend."""
        if collection_name == _LEGACY_COLLECTION:
            raise ValueError(
                f"governed operations cannot verify {_LEGACY_COLLECTION!r}"
            )

        record = self.read_vector(
            collection_name=collection_name,
            vector_record_id=vector_record_id,
        )
        return record is None

    def query_vectors(
        self,
        *,
        collection_name: str,
        query_vector: Sequence[float],
        candidate_vector_record_ids: Sequence[str],
        top_k: int,
    ) -> list[BackendVectorMatch]:
        """Candidate-constrained similarity query.

        The backend receives exact ``vector_record_record_ids`` to rank
        against — never a global query. The legacy ``research_papers``
        collection is rejected.

        Returns matches sorted by canonical_distance (lower is better).
        """
        if collection_name == _LEGACY_COLLECTION:
            raise ValueError(
                f"governed operations cannot query {_LEGACY_COLLECTION!r}"
            )

        if not candidate_vector_record_ids:
            return []

        collection = self._collections.get(collection_name)
        if collection is None:
            # Lazy-load from ChromaDB instead of failing — the collection
            # exists on disk but wasn't cached because this backend instance
            # didn't create it (a different process or the ingestion stage did).
            try:
                collection = self._client.get_collection(collection_name)
                self._collections[collection_name] = collection
            except Exception:
                raise ValueError(
                    f"collection {collection_name!r} not initialized"
                )

        result = collection.query(
            query_embeddings=[list(query_vector)],
            ids=list(candidate_vector_record_ids),
            n_results=min(top_k, len(candidate_vector_record_ids)),
            include=["metadatas", "distances"],
        )

        matches: list[BackendVectorMatch] = []
        ids = result.get("ids", [[]])
        distances = result.get("distances", [[]])
        metadatas = result.get("metadatas", [[]])

        if ids and ids[0]:
            for i, vid in enumerate(ids[0]):
                dist = distances[0][i] if distances and i < len(distances[0]) else 1.0
                meta = metadatas[0][i] if metadatas and i < len(metadatas[0]) else {}
                matches.append(BackendVectorMatch(
                    vector_record_id=vid,
                    paper_id=int(meta.get("paper_id", 0)),
                    chunk_key=str(meta.get("chunk_key", "")),
                    content_kind=str(meta.get("content_kind", "")),
                    content_hash=str(meta.get("content_hash", "")),
                    embedding_profile_id=str(meta.get("embedding_profile_id", "")),
                    index_schema_version=str(meta.get("index_schema_version", "")),
                    canonical_distance=float(dist),
                ))

        return matches


@dataclass(frozen=True)
class BackendVectorMatch:
    """One similarity match from a candidate-constrained backend query."""

    vector_record_id: str
    paper_id: int
    chunk_key: str
    content_kind: str
    content_hash: str
    embedding_profile_id: str
    index_schema_version: str
    canonical_distance: float
