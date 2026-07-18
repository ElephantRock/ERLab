"""Entity embedding index for graph-augmented retrieval (P0.4B0.5b).

B0.5b: Uses dedicated KG embedding profile, side-channel runtime namespace,
and namespace-specific ChromaDB collection. Legacy ``kg_entity_embeddings``
collection is quarantined — never queried by the governed path.

All embedding operations flow through ``GovernedEmbeddingAdapter.embed_documents``
and ``embed_query``. No raw provider, no implicit Chroma embedding, no
query_texts.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from backend.pipeline.knowledge.entities import EntityType, KnowledgeEntity
from backend.pipeline.side_channel_embedding import (
    SideChannelEmbeddingError,
    SideChannelEmbeddingRuntime,
    compute_namespace_fingerprint,
    compute_side_channel_collection_name,
    assert_purpose_not_paper,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

LEGACY_COLLECTION_NAME = "kg_entity_embeddings"
KG_ENTITY_CONTENT_CONTRACT_V1 = "kg_entity_content_v1"


@dataclass(frozen=True)
class KnowledgeGraphEmbeddingRebuildResult:
    """Deterministic rebuild evidence for KG embeddings."""
    namespace_fingerprint: str
    source_entity_count: int
    indexed_entity_count: int
    failed_entity_count: int
    collection_name: str
    complete: bool


def build_kg_entity_text(entity: KnowledgeEntity) -> str:
    """Canonical entity text for embedding (P0.4B0.5b).

    Frozen content contract: entity_type + name + properties.
    Excludes volatile fields (timestamps, retrieval scores, traversal order).
    """
    props = " ".join(f"{k}: {v}" for k, v in sorted(entity.properties.items()) if v)
    return f"{entity.entity_type.value} {entity.name} {props}".strip()


def compute_entity_content_hash(entity: KnowledgeEntity) -> str:
    """Deterministic SHA-256 of canonical entity text + content contract version."""
    text = build_kg_entity_text(entity)
    return hashlib.sha256(
        f"{KG_ENTITY_CONTENT_CONTRACT_V1}:{text}".encode()
    ).hexdigest()


def build_kg_collection_metadata(runtime: SideChannelEmbeddingRuntime) -> dict[str, Any]:
    """Build complete metadata for a governed KG collection."""
    cfg = runtime.effective_embedding_config
    return {
        "hnsw:space": "cosine",
        "collection_schema_version": "kg_v2",
        "embedding_purpose": "knowledge_graph_entity",
        "embedding_profile_id": cfg.embedding_profile_id,
        "runtime_namespace_fingerprint": runtime.namespace_fingerprint,
        "provider_kind": cfg.provider_kind,
        "requested_model": cfg.requested_model,
        "sanitized_endpoint_identity": cfg.sanitized_endpoint_identity,
        "expected_dimension": str(cfg.expected_dimension),
        "declared_normalization_policy": cfg.declared_normalization_policy,
        "implemented_postprocessing_policy": cfg.implemented_postprocessing_policy,
        "provider_adapter_contract_version": cfg.provider_adapter_contract_version,
        "governed_adapter_contract_version": cfg.governed_adapter_contract_version,
        "entity_content_contract_version": KG_ENTITY_CONTENT_CONTRACT_V1,
    }


def verify_kg_collection_metadata(
    collection: Any,
    runtime: SideChannelEmbeddingRuntime,
) -> None:
    """Verify collection metadata matches the active KG runtime exactly.

    Raises SideChannelEmbeddingError on mismatch.
    """
    expected = build_kg_collection_metadata(runtime)
    actual = collection.metadata or {}

    for key, expected_val in expected.items():
        actual_val = str(actual.get(key, ""))
        if str(expected_val) != actual_val:
            raise SideChannelEmbeddingError(
                "kg_collection_contract_mismatch",
                f"collection metadata mismatch: {key} expected {str(expected_val)!r}, "
                f"got {actual_val!r}",
            )


class GraphEmbeddingIndex:
    """B0.5b governed KG entity embedding index.

    Uses a SideChannelEmbeddingRuntime with purpose=knowledge_graph_entity.
    Writes and queries through GovernedEmbeddingAdapter (explicit vectors only).
    Legacy kg_entity_embeddings collection is never accessed.
    """

    def __init__(
        self,
        runtime: SideChannelEmbeddingRuntime,
        *,
        chroma_client: Any,
    ) -> None:
        assert_purpose_not_paper(runtime.purpose)
        if runtime.purpose != "knowledge_graph_entity":
            raise SideChannelEmbeddingError(
                "side_channel_purpose_mismatch",
                f"GraphEmbeddingIndex requires purpose 'knowledge_graph_entity', "
                f"got {runtime.purpose!r}",
            )

        self._runtime = runtime
        self._adapter = runtime.embedding_adapter

        # Compute namespace-specific collection name
        collection_name = compute_side_channel_collection_name(
            "kg_entity_embeddings_v2",
            runtime.namespace_fingerprint,
        )
        self._collection_name = collection_name

        expected_metadata = build_kg_collection_metadata(runtime)

        # Try to get existing collection
        try:
            self._collection = chroma_client.get_collection(collection_name)
            # Verify metadata matches
            verify_kg_collection_metadata(self._collection, runtime)
        except SideChannelEmbeddingError:
            raise
        except Exception:
            # Collection doesn't exist — create with full metadata
            self._collection = chroma_client.get_or_create_collection(
                name=collection_name,
                metadata=expected_metadata,
            )

    @property
    def collection_name(self) -> str:
        return self._collection_name

    async def index_entity(self, entity: KnowledgeEntity) -> None:
        """Index a single entity using explicit validated vectors."""
        text = build_kg_entity_text(entity)
        content_hash = compute_entity_content_hash(entity)

        # Generate embedding through governed adapter
        vectors = await self._adapter.embed_documents([text])

        self._collection.upsert(
            ids=[entity.id],
            documents=[text],
            embeddings=[list(vectors[0])],
            metadatas=[{
                "entity_type": entity.entity_type.value,
                "name": entity.name,
                "content_hash": content_hash,
                "namespace_fingerprint": self._runtime.namespace_fingerprint,
                "embedding_purpose": "knowledge_graph_entity",
                "entity_content_contract_version": KG_ENTITY_CONTENT_CONTRACT_V1,
            }],
        )

    async def index_graph(self, kg: Any) -> int:
        """Index all entities from a KnowledgeGraph using explicit vectors."""
        entities = list(kg._entities.values())
        if not entities:
            return 0

        texts = [build_kg_entity_text(e) for e in entities]
        content_hashes = [compute_entity_content_hash(e) for e in entities]

        try:
            vectors = await self._adapter.embed_documents(texts)
        except Exception as e:
            logger.warning("KG embedding batch failed: %s", e)
            return 0

        self._collection.upsert(
            ids=[e.id for e in entities],
            documents=texts,
            embeddings=[list(v) for v in vectors],
            metadatas=[{
                "entity_type": e.entity_type.value,
                "name": e.name,
                "content_hash": ch,
                "namespace_fingerprint": self._runtime.namespace_fingerprint,
                "embedding_purpose": "knowledge_graph_entity",
                "entity_content_contract_version": KG_ENTITY_CONTENT_CONTRACT_V1,
            } for e, ch in zip(entities, content_hashes)],
        )
        logger.info("Indexed %d entities in governed KG collection", len(entities))
        return len(entities)

    async def query_similar(
        self, query: str, n_results: int = 20, entity_type: EntityType | None = None
    ) -> list[dict]:
        """Similarity query using explicit query_embeddings."""
        # Generate query embedding through governed adapter
        query_vector = await self._adapter.embed_query(query)

        where = {"entity_type": entity_type.value} if entity_type else None
        if where is None:
            where = {"embedding_purpose": "knowledge_graph_entity"}

        results = self._collection.query(
            query_embeddings=[list(query_vector)],
            n_results=n_results,
            where=where,
        )

        return self._parse_results(results)

    async def query_by_embedding(
        self, embedding: list[float], n_results: int = 20
    ) -> list[dict]:
        """Query by pre-computed embedding vector."""
        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where={"embedding_purpose": "knowledge_graph_entity"},
        )
        return self._parse_results(results)

    def _parse_results(self, results: dict) -> list[dict]:
        """Parse and validate backend results."""
        items = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        dists = results.get("distances", [[]])[0]
        metas = results.get("metadatas", [[]])[0]

        for eid, doc, dist, meta in zip(ids, docs, dists, metas):
            meta = meta or {}
            # Validate namespace in result
            if meta.get("namespace_fingerprint") != self._runtime.namespace_fingerprint:
                logger.debug("KG result %s has stale namespace — skipping", eid)
                continue
            items.append({
                "id": eid,
                "text": doc,
                "distance": dist,
                "metadata": meta,
            })
        return items


async def rebuild_kg_embeddings(
    runtime: SideChannelEmbeddingRuntime,
    *,
    chroma_client: Any,
    entities: list[KnowledgeEntity],
) -> KnowledgeGraphEmbeddingRebuildResult:
    """Rebuild KG embeddings from canonical entity content.

    Uses the governed adapter — no legacy vectors copied.
    """
    index = GraphEmbeddingIndex(runtime, chroma_client=chroma_client)

    source_count = len(entities)
    indexed = 0
    failed = 0

    for entity in entities:
        try:
            await index.index_entity(entity)
            indexed += 1
        except Exception as e:
            logger.warning("KG entity %s rebuild failed: %s", entity.id, e)
            failed += 1

    complete = (failed == 0) and (indexed + failed == source_count)

    return KnowledgeGraphEmbeddingRebuildResult(
        namespace_fingerprint=runtime.namespace_fingerprint,
        source_entity_count=source_count,
        indexed_entity_count=indexed,
        failed_entity_count=failed,
        collection_name=index.collection_name,
        complete=complete,
    )
