"""Embedding-based tool search — dedicated ChromaDB collection for tool definitions."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import chromadb
from pydantic import BaseModel

if TYPE_CHECKING:
    from backend.pipeline.knowledge.embedding_service import EmbeddingService
    from backend.pipeline.tools.registry import ToolDefinition, ToolRegistry

logger = logging.getLogger(__name__)

COLLECTION_NAME = "tool_embeddings"


class ToolSearchResult(BaseModel):
    tool_name: str
    score: float
    source: str = "semantic"
    metadata: dict[str, Any] = {}


class ToolEmbeddingIndex:
    """Stores and queries embeddings for tools in a dedicated ChromaDB collection."""

    def __init__(
        self,
        persist_dir: str,
        embedding_service: EmbeddingService,
        *,
        collection_name: str | None = None,
        client: Any | None = None,
    ) -> None:
        self._client = client or chromadb.PersistentClient(path=persist_dir)
        self._embedding = embedding_service
        self._collection = self._client.get_or_create_collection(
            name=collection_name or COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    @staticmethod
    def _tool_to_text(tool: ToolDefinition) -> str:
        params = ", ".join(tool.parameters.keys()) if tool.parameters else ""
        parts = [f"{tool.name}:", tool.description]
        if params:
            parts.append(f"params: {params}")
        return " ".join(parts)

    async def index_tool(self, tool: ToolDefinition) -> None:
        text = self._tool_to_text(tool)
        embedding = await self._embedding.embed_single(text)
        self._collection.upsert(
            ids=[tool.name],
            documents=[text],
            embeddings=[embedding],
            metadatas=[{
                "trust_level": tool.trust_level,
                "source": tool.source,
                "description": tool.description,
            }],
        )

    async def index_registry(self, registry: ToolRegistry) -> int:
        tools = registry.list_tools(enabled_only=True)
        if not tools:
            return 0

        texts = [self._tool_to_text(t) for t in tools]
        embeddings = await self._embedding.embed_texts(texts)

        valid = [(t, txt, emb) for t, txt, emb in zip(tools, texts, embeddings) if emb]
        if not valid:
            return 0

        self._collection.upsert(
            ids=[t.name for t, _, _ in valid],
            documents=[txt for _, txt, _ in valid],
            embeddings=[emb for _, _, emb in valid],
            metadatas=[{
                "trust_level": t.trust_level,
                "source": t.source,
                "description": t.description,
            } for t, _, _ in valid],
        )
        logger.info("Indexed %d tools in embedding collection", len(valid))
        return len(valid)

    async def query(
        self,
        capability_description: str,
        n_results: int = 10,
        trust_level: str | None = None,
    ) -> list[ToolSearchResult]:
        embedding = await self._embedding.embed_single(capability_description)
        where = {"trust_level": trust_level} if trust_level else None
        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where,
        )

        items: list[ToolSearchResult] = []
        ids = results.get("ids", [[]])[0]
        dists = results.get("distances", [[]])[0]
        metas = results.get("metadatas", [[]])[0]

        for name, dist, meta in zip(ids, dists, metas):
            score = 1.0 - dist if dist is not None else 0.0
            items.append(ToolSearchResult(
                tool_name=name,
                score=score,
                source="semantic",
                metadata=meta or {},
            ))
        return items
