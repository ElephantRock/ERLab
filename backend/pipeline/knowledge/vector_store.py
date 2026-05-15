"""ChromaDB vector store wrapper.

Data integrity guarantees (Phase C):
- Zero-vector rejection: embeddings that are all zeros are rejected at write time
- Keyword passthrough: paper keywords are stored in VectorStore metadata
"""

import logging
from pathlib import Path

import chromadb

from backend.pipeline.ingestion.chunker import DocumentChunk
from backend.pipeline.knowledge.embedding_service import EmbeddingService
from backend.pipeline.literature.models import Paper

logger = logging.getLogger(__name__)

COLLECTION_NAME = "research_papers"


def _is_zero_vector(vec: list[float]) -> bool:
    """Check if an embedding vector is all zeros."""
    if not vec:
        return True
    # Handle numpy arrays
    try:
        import numpy as np
        if isinstance(vec, np.ndarray):
            return bool(np.all(vec == 0.0))
    except ImportError:
        pass
    return all(v == 0.0 for v in vec)


def _zero_vector_count(embeddings: list[list[float]]) -> int:
    """Count how many embeddings are all-zero vectors."""
    return sum(1 for e in embeddings if _is_zero_vector(e))


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

        # Validate collection dimension matches current embedding dimension
        if self._collection.count() > 0:
            sample = self._collection.get(limit=1, include=["embeddings"])
            embeddings = sample.get("embeddings")
            if embeddings is not None and len(embeddings) > 0:
                stored_dim = len(sample["embeddings"][0])
                expected_dim = self._embedding_service.dimension
                if stored_dim != expected_dim:
                    logger.warning(
                        "Collection dimension (%d) != embedding dimension (%d). "
                        "Recreating collection to fix mismatch.",
                        stored_dim, expected_dim,
                    )
                    self._client.delete_collection(COLLECTION_NAME)
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

        # Batch all texts for parallel embedding (fixes 18min ingestion)
        paper_text_pairs = []
        for paper, paper_chunks in zip(papers, chunks, strict=True):
            texts = [c.text for c in paper_chunks]
            if texts:
                paper_text_pairs.append((paper, paper_chunks, texts))

        if paper_text_pairs:
            all_batch_texts = [t for _, _, texts in paper_text_pairs for t in texts]
            all_batch_embeddings = await self._embedding_service.embed_texts(all_batch_texts)

            # Map embeddings back to papers
            offset = 0
            for paper, paper_chunks, texts in paper_text_pairs:
                embeddings = all_batch_embeddings[offset:offset + len(texts)]
                offset += len(texts)

                for i, (chunk, embedding) in enumerate(zip(paper_chunks, embeddings, strict=True)):
                    # Phase C: Reject zero-vector embeddings at write time
                    if _is_zero_vector(embedding):
                        logger.warning(
                            "Zero-vector embedding rejected for %s chunk %d — "
                            "embedding provider may be offline",
                            paper.id, i,
                        )
                        continue
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
                            # Phase C: Pass keywords through to metadata
                            "keywords": ",".join(paper.keywords) if paper.keywords else "",
                        }
                    )

        if all_ids:
            # Log data quality stats
            zero_count = _zero_vector_count(all_embeddings)
            if zero_count > 0:
                logger.error(
                    "DATA INTEGRITY: %d zero vectors passed write guard (should be 0)",
                    zero_count,
                )

            # Deduplicate by ID — same paper can appear across multiple queries
            seen = {}
            for idx, cid in enumerate(all_ids):
                if cid not in seen:
                    seen[cid] = idx
            deduped_ids = list(seen.keys())
            deduped_texts = [all_texts[i] for i in seen.values()]
            deduped_embeddings = [all_embeddings[i] for i in seen.values()]
            deduped_metadata = [all_metadata[i] for i in seen.values()]

            self._collection.upsert(
                ids=deduped_ids,
                documents=deduped_texts,
                embeddings=deduped_embeddings,
                metadatas=deduped_metadata,
            )
            logger.info("Vector store: upserted %d chunks (deduped from %d)", len(deduped_ids), len(all_ids))

        return len(seen) if all_ids else 0

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
        """Return collection statistics including data quality metrics."""
        count = self._collection.count()
        stats = {
            "collection": COLLECTION_NAME,
            "document_count": count,
        }

        # Data quality: sample for zero vectors
        if count > 0:
            sample_n = min(count, 100)
            sample = self._collection.get(limit=sample_n, include=["embeddings", "metadatas"])
            embeddings = sample.get("embeddings") if sample.get("embeddings") is not None else []
            metadatas = sample.get("metadatas") if sample.get("metadatas") is not None else []

            zero_vec_count = 0
            for e in embeddings:
                if hasattr(e, 'ndim'):  # numpy array
                    import numpy as _np
                    if _np.all(e == 0.0):
                        zero_vec_count += 1
                elif all(v == 0.0 for v in e):
                    zero_vec_count += 1
            keyword_coverage = sum(
                1 for m in metadatas
                if m and m.get("keywords") and m["keywords"].strip()
            )

            stats["zero_vectors_sampled"] = zero_vec_count
            stats["zero_vector_pct"] = round(100.0 * zero_vec_count / max(sample_n, 1), 1)
            stats["keyword_coverage_pct"] = round(100.0 * keyword_coverage / max(sample_n, 1), 1)
            stats["sample_size"] = sample_n

        return stats

    async def delete_paper(self, paper_id: str) -> int:
        """Delete all chunks for a paper. Returns count deleted."""
        self._collection.delete(where={"paper_id": paper_id})
        return 0  # ChromaDB doesn't return count easily
