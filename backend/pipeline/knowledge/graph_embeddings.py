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
    assert_purpose_not_paper,
    compute_side_channel_collection_name,
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
        arg1: Any = None,
        arg2: Any = None,
        *,
        chroma_client: Any = None,
        client: Any = None,
        collection_name: str | None = None,
    ) -> None:
        """Initialize the KG embedding index.

        B0.5b governed path:
            GraphEmbeddingIndex(runtime, chroma_client=client)

        Legacy path:
            GraphEmbeddingIndex(persist_dir, embedding_service, client=...)
            GraphEmbeddingIndex(persist_dir, embedding_service, collection_name=...)
        """
        # Detect which path: if arg1 is a SideChannelEmbeddingRuntime, governed
        if isinstance(arg1, SideChannelEmbeddingRuntime):
            self._init_governed(arg1, chroma_client)
        else:
            # Legacy: arg1=persist_dir, arg2=embedding_service
            self._init_legacy(
                persist_dir=arg1,
                embedding_service=arg2,
                client=client,
                collection_name=collection_name,
            )

    def _init_governed(
        self,
        runtime: SideChannelEmbeddingRuntime,
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

    def _init_legacy(
        self,
        *,
        persist_dir: str | None = None,
        embedding_service: Any = None,
        client: Any = None,
        collection_name: str | None = None,
    ) -> None:
        """Legacy initialization for pre-B0.5 callers.

        Uses raw ChromaDB and the embedding service directly. No governed
        adapter validation, no namespace isolation. Production governed
        code should use the runtime constructor.
        """
        import chromadb

        self._client = client or chromadb.PersistentClient(path=persist_dir or "./data/chroma")
        self._embedding = embedding_service
        self._runtime = None
        self._adapter = None
        self._collection_name = collection_name or LEGACY_COLLECTION_NAME
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def collection_name(self) -> str:
        return self._collection_name

    @staticmethod
    def _entity_to_text(entity: KnowledgeEntity) -> str:
        """Backward-compat alias for build_kg_entity_text."""
        return build_kg_entity_text(entity)

    async def index_entity(self, entity: KnowledgeEntity) -> None:
        """Index a single entity."""
        text = build_kg_entity_text(entity)
        content_hash = compute_entity_content_hash(entity)

        if self._adapter is not None:
            # Governed path
            vectors = await self._adapter.embed_documents([text])
            embeddings = [list(vectors[0])]
        else:
            # Legacy path
            embeddings = [await self._embedding.embed_single(text)]

        metadata = {
            "entity_type": entity.entity_type.value,
            "name": entity.name,
            "content_hash": content_hash,
        }
        if self._runtime is not None:
            metadata["namespace_fingerprint"] = self._runtime.namespace_fingerprint
            metadata["embedding_purpose"] = "knowledge_graph_entity"
            metadata["entity_content_contract_version"] = KG_ENTITY_CONTENT_CONTRACT_V1

        self._collection.upsert(
            ids=[entity.id],
            documents=[text],
            embeddings=embeddings,
            metadatas=[metadata],
        )

    async def index_graph(self, kg: Any) -> int:
        """Index all entities from a KnowledgeGraph."""
        entities = list(kg._entities.values())
        if not entities:
            return 0

        texts = [build_kg_entity_text(e) for e in entities]
        content_hashes = [compute_entity_content_hash(e) for e in entities]

        if self._adapter is not None:
            try:
                vectors = await self._adapter.embed_documents(texts)
            except Exception as e:
                logger.warning("KG embedding batch failed: %s", e)
                return 0
            embeddings = [list(v) for v in vectors]
        else:
            embeddings = await self._embedding.embed_texts(texts)

        self._collection.upsert(
            ids=[e.id for e in entities],
            documents=texts,
            embeddings=embeddings,
            metadatas=[{
                "entity_type": e.entity_type.value,
                "name": e.name,
                "content_hash": ch,
                **({"namespace_fingerprint": self._runtime.namespace_fingerprint,
                    "embedding_purpose": "knowledge_graph_entity",
                    "entity_content_contract_version": KG_ENTITY_CONTENT_CONTRACT_V1}
                   if self._runtime is not None else {})
            } for e, ch in zip(entities, content_hashes)],
        )
        logger.info("Indexed %d entities in governed KG collection", len(entities))
        return len(entities)

    async def query_similar(
        self, query: str, n_results: int = 20, entity_type: EntityType | None = None
    ) -> list[dict]:
        """Similarity query."""
        if self._adapter is not None:
            query_vector = list(await self._adapter.embed_query(query))
        else:
            query_vector = await self._embedding.embed_single(query)

        where = {"entity_type": entity_type.value} if entity_type else None
        if where is None and self._runtime is not None:
            where = {"embedding_purpose": "knowledge_graph_entity"}

        results = self._collection.query(
            query_embeddings=[query_vector],
            n_results=n_results,
            where=where,
        )

        return self._parse_results(results)

    async def query_by_embedding(
        self, embedding: list[float], n_results: int = 20
    ) -> list[dict]:
        """Query by pre-computed embedding vector."""
        where = {"embedding_purpose": "knowledge_graph_entity"} if self._runtime is not None else None
        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where,
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
            # Validate namespace in result (governed path only)
            if self._runtime is not None:
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
