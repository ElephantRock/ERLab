"""ChromaDB vector store wrapper."""

import logging
from pathlib import Path

import chromadb

from backend.pipeline.ingestion.chunker import DocumentChunk
from backend.pipeline.knowledge.embedding_service import EmbeddingService
from backend.pipeline.literature.models import Paper

logger = logging.getLogger(__name__)

COLLECTION_NAME = "research_papers"


class VectorStore:
    """Manages paper embeddings in ChromaDB."""

    def __init__(self, persist_dir: str, embedding_service: EmbeddingService):
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._embedding_service = embedding_service
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    async def add_papers(
        self,
        papers: list[Paper],
        chunks: list[list[DocumentChunk]],
    ) -> int:
        """Add papers with their chunks to the vector store. Returns count of chunks added."""
        if not papers or not chunks:
            return 0

        all_ids = []
        all_texts = []
        all_embeddings = []
        all_metadata = []

        for paper, paper_chunks in zip(papers, chunks, strict=True):
            texts = [c.text for c in paper_chunks]
            if not texts:
                continue

            embeddings = await self._embedding_service.embed_texts(texts)

            for i, (chunk, embedding) in enumerate(zip(paper_chunks, embeddings, strict=True)):
                chunk_id = f"{paper.id}_chunk_{i}"
                all_ids.append(chunk_id)
                all_texts.append(chunk.text)
                all_embeddings.append(embedding)
                all_metadata.append(
                    {
                        "paper_id": paper.id,
                        "paper_title": paper.title[:500],
                        "source": paper.source,
                        "section": chunk.section,
                        "year": paper.year or 0,
                    }
                )

        if all_ids:
            # ChromaDB add is synchronous
            self._collection.add(
                ids=all_ids,
                documents=all_texts,
                embeddings=all_embeddings,
                metadatas=all_metadata,
            )

        return len(all_ids)

    async def query(
        self,
        query_text: str,
        n_results: int = 10,
        filter_metadata: dict | None = None,
    ) -> list[dict]:
        """Semantic search across stored chunks."""
        query_embedding = await self._embedding_service.embed_single(query_text)

        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
        }
        if filter_metadata:
            kwargs["where"] = filter_metadata

        results = self._collection.query(**kwargs)

        # Format results
        formatted = []
        for i in range(len(results["ids"][0])):
            formatted.append(
                {
                    "id": results["ids"][0][i],
                    "text": results["documents"][0][i],
                    "distance": results["distances"][0][i] if "distances" in results else None,
                    "metadata": results["metadatas"][0][i] if "metadatas" in results else {},
                }
            )
        return formatted

    async def query_by_embedding(
        self,
        embedding: list[float],
        n_results: int = 10,
    ) -> list[dict]:
        """Search by pre-computed embedding."""
        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
        )

        formatted = []
        for i in range(len(results["ids"][0])):
            formatted.append(
                {
                    "id": results["ids"][0][i],
                    "text": results["documents"][0][i],
                    "distance": results["distances"][0][i] if "distances" in results else None,
                    "metadata": results["metadatas"][0][i] if "metadatas" in results else {},
                }
            )
        return formatted

    def get_stats(self) -> dict:
        """Return collection statistics."""
        count = self._collection.count()
        return {
            "collection": COLLECTION_NAME,
            "document_count": count,
        }

    async def delete_paper(self, paper_id: str) -> int:
        """Delete all chunks for a paper. Returns count deleted."""
        self._collection.delete(where={"paper_id": paper_id})
        return 0  # ChromaDB doesn't return count easily
