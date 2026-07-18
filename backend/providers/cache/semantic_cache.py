"""ChromaDB-backed semantic similarity cache for LLM responses."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

import chromadb

from backend.providers.cache.base import (
    CacheEntry,
    deserialize_response,
    make_cache_key,
    serialize_response,
)

if TYPE_CHECKING:
    from backend.pipeline.knowledge.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

COLLECTION_NAME = "llm_cache"


class SemanticCache:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        persist_dir: str = "./data/chroma",
        similarity_threshold: float = 0.95,
        ttl_seconds: int = 3600,
        max_size: int = 1000,
        *,
        cache_namespace: str | None = None,
    ) -> None:
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._embedding_service = embedding_service
        self._threshold = similarity_threshold
        self._ttl_seconds = ttl_seconds
        self._max_size = max_size
        # B0.5d: namespace-specific collection prevents cross-runtime cache reuse
        collection_name = f"llm_cache_{cache_namespace[:16]}" if cache_namespace else COLLECTION_NAME
        self._cache_namespace = cache_namespace
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._hits = 0
        self._misses = 0
        # Track created_at timestamps for eviction (not stored in ChromaDB metadata)
        self._timestamps: dict[str, float] = {}

    async def lookup_similar(self, query_text: str) -> CacheEntry | None:
        query_embedding = await self._embedding_service.embed_single(query_text)
        if not query_embedding or all(v == 0.0 for v in query_embedding):
            self._misses += 1
            return None

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=1,
            include=["distances", "documents", "metadatas"],
        )
        if not query_embedding or all(v == 0.0 for v in query_embedding):
            self._misses += 1
            return None

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=1,
            include=["distances", "documents"],
        )

        if not results["ids"][0]:
            self._misses += 1
            return None

        # ChromaDB cosine distance: distance = 1 - similarity
        distance = results["distances"][0][0]
        similarity = 1.0 - distance

        if similarity < self._threshold:
            self._misses += 1
            return None

        doc_id = results["ids"][0][0]

        # TTL check
        ts = self._timestamps.get(doc_id, 0.0)
        if ts and time.time() - ts > self._ttl_seconds:
            self._invalidate(doc_id)
            self._misses += 1
            return None

        # Deserialize response from ChromaDB document
        doc_content = results["documents"][0][0]
        try:
            response = deserialize_response(doc_content)
        except (json.JSONDecodeError, KeyError):
            self._invalidate(doc_id)
            self._misses += 1
            return None

        self._hits += 1
        return CacheEntry(response=response, created_at=ts)

    async def update_similar(self, query_text: str, entry: CacheEntry) -> None:
        embedding = await self._embedding_service.embed_single(query_text)
        if not embedding or all(v == 0.0 for v in embedding):
            return

        doc_id = make_cache_key(query_text)
        doc_content = serialize_response(entry.response)

        self._collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[doc_content],
        )
        self._timestamps[doc_id] = entry.created_at

        if len(self._timestamps) > self._max_size:
            self._evict_oldest()

    def _evict_oldest(self) -> None:
        if not self._timestamps:
            return
        oldest_key = min(self._timestamps, key=lambda k: self._timestamps[k])
        self._invalidate(oldest_key)

    def _invalidate(self, doc_id: str) -> None:
        self._timestamps.pop(doc_id, None)
        try:
            self._collection.delete(ids=[doc_id])
        except Exception:
            logger.debug("Failed to delete cache entry %s from ChromaDB", doc_id[:8])

    def clear(self) -> None:
        self._timestamps.clear()
        try:
            self._client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self._hits = 0
        self._misses = 0

    def stats(self) -> dict[str, int | float]:
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._timestamps),
            "max_size": self._max_size,
            "hit_rate": self._hits / max(1, total),
            "chroma_count": self._collection.count(),
        }
