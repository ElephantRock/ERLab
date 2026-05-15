#!/usr/bin/env python3
"""Re-index VectorStore: delete all embeddings and regenerate from SQL papers.

This fixes the zero-vector problem when LM Studio was down during ingestion.
Reads papers from SQL, re-chunks them, and generates fresh embeddings.

Usage:
    python scripts/reindex_vectors.py [--dry-run] [--batch-size 50]
"""
import argparse
import asyncio
import json
import logging
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def reindex(dry_run: bool = False, batch_size: int = 50) -> dict:
    """Re-index all papers in VectorStore with fresh embeddings."""
    start = time.time()

    # Late imports to avoid loading heavy modules on --help
    from backend.config import get_settings
    settings = get_settings()

    from backend.db.database import get_session
    from backend.db.models import Paper as SQLPaper
    from backend.pipeline.literature.models import Paper
    from backend.pipeline.ingestion.chunker import DocumentChunker
    from backend.pipeline.knowledge.embedding_providers import create_embedding_provider
    from backend.pipeline.knowledge.embedding_service import EmbeddingService
    from backend.pipeline.knowledge.vector_store import VectorStore

    # Build embedding service
    provider = create_embedding_provider(settings)
    emb_service = EmbeddingService(provider, expected_dimension=getattr(provider, "dimension", None))

    # Validate embedding provider first
    logger.info("Validating embedding provider...")
    valid = await emb_service.validate_startup()
    if not valid:
        logger.error(
            "ABORTING: Embedding provider returns zero vectors. "
            "Ensure LM Studio is running with an embedding model loaded, "
            "or set EROCK_EMBEDDING_PROVIDER=openai in .env"
        )
        return {"status": "aborted", "reason": "zero_vectors"}

    logger.info("Embedding provider OK (%d-dim)", emb_service.dimension)

    # Build vector store
    store = VectorStore(
        persist_dir=settings.chroma_persist_dir,
        embedding_service=emb_service,
    )

    # Count existing vectors
    before_stats = store.get_stats()
    logger.info("Before: %s", json.dumps(before_stats, indent=2))

    if dry_run:
        # Count papers in SQL
        session = next(get_session())
        paper_count = session.query(SQLPaper).count()
        logger.info("DRY RUN: Would re-index %d papers from SQL", paper_count)
        return {"status": "dry_run", "papers_in_sql": paper_count, "before": before_stats}

    # Delete existing collection and recreate
    logger.info("Deleting existing collection...")
    import chromadb
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    try:
        client.delete_collection("research_papers")
    except Exception:
        pass

    store = VectorStore(
        persist_dir=settings.chroma_persist_dir,
        embedding_service=emb_service,
    )

    # Load papers from SQL
    session = next(get_session())
    sql_papers = session.query(SQLPaper).all()
    logger.info("Loaded %d papers from SQL", len(sql_papers))

    if not sql_papers:
        return {"status": "no_papers", "before": before_stats}

    # Convert to pipeline Paper model
    chunker = DocumentChunker()
    total_chunks = 0
    total_zero_rejected = 0

    for batch_start in range(0, len(sql_papers), batch_size):
        batch = sql_papers[batch_start:batch_start + batch_size]

        papers = []
        all_chunks = []
        for sp in batch:
            # Parse keywords from JSON string
            try:
                keywords = json.loads(sp.keywords) if sp.keywords else []
            except (json.JSONDecodeError, TypeError):
                keywords = []

            paper = Paper(
                id=sp.id,
                source=sp.source or "unknown",
                title=sp.title,
                abstract=sp.abstract or "",
                year=sp.year,
                authors=[],  # Not needed for re-indexing
                venue=sp.venue,
                citation_count=sp.citation_count,
                url=sp.url,
                doi=sp.doi,
                arxiv_id=sp.arxiv_id,
                keywords=keywords,
            )
            papers.append(paper)

            # Chunk the paper
            text = f"{paper.title}\n\n{paper.abstract}" if paper.abstract else paper.title
            chunks = chunker.chunk(text, paper_id=paper.id)
            all_chunks.append(chunks)

        # Add to vector store (includes zero-vector rejection)
        before_count = sum(len(c) for c in all_chunks)
        added = await store.add_papers(papers, all_chunks)
        rejected = before_count - added
        total_zero_rejected += rejected
        total_chunks += added

        logger.info(
            "Batch %d/%d: %d papers, %d/%d chunks added (%d zero rejected)",
            batch_start // batch_size + 1,
            (len(sql_papers) + batch_size - 1) // batch_size,
            len(batch), added, before_count, rejected,
        )

    elapsed = time.time() - start
    after_stats = store.get_stats()
    logger.info("After: %s", json.dumps(after_stats, indent=2))

    result = {
        "status": "complete",
        "papers_processed": len(sql_papers),
        "chunks_added": total_chunks,
        "zero_vectors_rejected": total_zero_rejected,
        "elapsed_seconds": round(elapsed, 1),
        "before": before_stats,
        "after": after_stats,
    }
    logger.info("Re-index complete: %s", json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-index VectorStore from SQL papers")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--batch-size", type=int, default=50, help="Papers per batch")
    args = parser.parse_args()

    result = asyncio.run(reindex(dry_run=args.dry_run, batch_size=args.batch_size))
    sys.exit(0 if result["status"] in ("complete", "dry_run") else 1)
