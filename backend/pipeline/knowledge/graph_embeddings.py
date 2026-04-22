"""Entity embedding index for graph-augmented retrieval — dedicated ChromaDB collection."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import chromadb

from backend.pipeline.knowledge.entities import EntityType, KnowledgeEntity

if TYPE_CHECKING:
    from backend.pipeline.knowledge.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

COLLECTION_NAME = "kg_entity_embeddings"


class GraphEmbeddingIndex:
    """Stores and queries embeddings for KG entities in a dedicated ChromaDB collection."""

    def __init__(
        self,
        persist_dir: str,
        embedding_service: EmbeddingService,
        *,
        client: Any | None = None,
        collection_name: str | None = None,
    ) -> None:
        self._client = client or chromadb.PersistentClient(path=persist_dir)
        self._embedding = embedding_service
        self._collection = self._client.get_or_create_collection(
            name=collection_name or COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    @staticmethod
    def _entity_to_text(entity: KnowledgeEntity) -> str:
        props = " ".join(f"{k}: {v}" for k, v in entity.properties.items() if v)
        return f"{entity.entity_type.value} {entity.name} {props}".strip()

    async def index_entity(self, entity: KnowledgeEntity) -> None:
        text = self._entity_to_text(entity)
        embedding = await self._embedding.embed_single(text)
        self._collection.upsert(
            ids=[entity.id],
            documents=[text],
            embeddings=[embedding],
            metadatas=[{
                "entity_type": entity.entity_type.value,
                "name": entity.name,
            }],
        )

    async def index_graph(self, kg: "KnowledgeGraph") -> int:  # noqa: F821
        entities = list(kg._entities.values())
        if not entities:
            return 0

        texts = [self._entity_to_text(e) for e in entities]
        embeddings = await self._embedding.embed_texts(texts)

        valid = [(e, t, emb) for e, t, emb in zip(entities, texts, embeddings) if emb]
        if not valid:
            return 0

        self._collection.upsert(
            ids=[e.id for e, _, _ in valid],
            documents=[t for _, t, _ in valid],
            embeddings=[emb for _, _, emb in valid],
            metadatas=[{"entity_type": e.entity_type.value, "name": e.name} for e, _, _ in valid],
        )
        logger.info("Indexed %d entities in graph embedding collection", len(valid))
        return len(valid)

    async def query_similar(
        self, query: str, n_results: int = 20, entity_type: EntityType | None = None
    ) -> list[dict]:
        embedding = await self._embedding.embed_single(query)
        where = {"entity_type": entity_type.value} if entity_type else None
        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where,
        )

        items = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        dists = results.get("distances", [[]])[0]
        metas = results.get("metadatas", [[]])[0]

        for eid, doc, dist, meta in zip(ids, docs, dists, metas):
            items.append({
                "id": eid,
                "text": doc,
                "distance": dist,
                "metadata": meta or {},
            })
        return items

    async def query_by_embedding(
        self, embedding: list[float], n_results: int = 20
    ) -> list[dict]:
        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
        )

        items = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        dists = results.get("distances", [[]])[0]
        metas = results.get("metadatas", [[]])[0]

        for eid, doc, dist, meta in zip(ids, docs, dists, metas):
            items.append({
                "id": eid,
                "text": doc,
                "distance": dist,
                "metadata": meta or {},
            })
        return items
