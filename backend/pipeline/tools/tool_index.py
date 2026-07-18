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
    """Stores and queries embeddings for tools in a dedicated ChromaDB collection.

    B0.5c: Supports governed SideChannelEmbeddingRuntime for namespace isolation.
    Legacy callers pass persist_dir + embedding_service directly.
    """

    def __init__(
        self,
        arg1: Any = None,
        arg2: Any = None,
        *,
        collection_name: str | None = None,
        client: Any | None = None,
        chroma_client: Any = None,
    ) -> None:
        from backend.pipeline.side_channel_embedding import SideChannelEmbeddingRuntime

        if isinstance(arg1, SideChannelEmbeddingRuntime):
            # Governed path
            from backend.pipeline.side_channel_embedding import (
                assert_purpose_not_paper,
                SideChannelEmbeddingError,
                compute_side_channel_collection_name,
            )
            assert_purpose_not_paper(arg1.purpose)
            if arg1.purpose != "tool_description":
                raise SideChannelEmbeddingError(
                    "side_channel_purpose_mismatch",
                    f"ToolEmbeddingIndex requires purpose 'tool_description', "
                    f"got {arg1.purpose!r}",
                )
            self._runtime = arg1
            self._adapter = arg1.embedding_adapter
            self._embedding = None
            self._client = chroma_client
            coll_name = compute_side_channel_collection_name(
                "tool_embeddings_v2", arg1.namespace_fingerprint,
            )
            self._collection_name = coll_name
            self._collection = chroma_client.get_or_create_collection(
                name=coll_name,
                metadata={"hnsw:space": "cosine"},
            )
        else:
            # Legacy path: arg1=persist_dir, arg2=embedding_service
            self._runtime = None
            self._adapter = None
            self._client = client or chromadb.PersistentClient(path=arg1 or "./data/chroma")
            self._embedding = arg2
            self._collection_name = collection_name or COLLECTION_NAME
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
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
        if self._adapter is not None:
            vectors = await self._adapter.embed_documents([text])
            embeddings = [list(vectors[0])]
        else:
            embeddings = [await self._embedding.embed_single(text)]
        self._collection.upsert(
            ids=[tool.name],
            documents=[text],
            embeddings=embeddings,
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
        if self._adapter is not None:
            vectors = await self._adapter.embed_documents(texts)
            embeddings = [list(v) for v in vectors]
            valid = list(zip(tools, texts, embeddings))
        else:
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
        if self._adapter is not None:
            embedding = list(await self._adapter.embed_query(capability_description))
        else:
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
