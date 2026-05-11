import asyncio
import sys
from pathlib import Path

PROJECT = Path(r"C:\Next-Era\elephant-rock-platform")
sys.path.insert(0, str(PROJECT))

from backend.config import get_settings
from backend.pipeline.ingestion.pdf_service import PDFService
from backend.pipeline.knowledge.embedding_service import EmbeddingService
from backend.pipeline.knowledge.embedding_providers import create_embedding_provider
from backend.pipeline.knowledge.vector_store import VectorStore
from backend.pipeline.literature.models import Paper

PAPERS = [
    (r"C:\Next-Era\elephant-rock-platform\sessions\260511-prime-wave\long_responses\20595fdc-6d3e-4b70-a8ec-9a55c901b7bd_2603.06365.pdf", "arxiv-2603-06365", "ESAA-Security: An Event-Sourced, Verifiable Architecture for Agent-Assisted Security Audits of AI-Generated Code", 2026, "https://arxiv.org/abs/2603.06365"),
    (r"C:\Next-Era\elephant-rock-platform\sessions\260511-prime-wave\long_responses\89cc2a5e-0798-4317-bf9a-17aaf008174a_2602.23193.pdf", "arxiv-2602-23193", "ESAA: Event Sourcing for Autonomous Agents in LLM-Based Software Engineering", 2026, "https://arxiv.org/abs/2602.23193"),
    (r"C:\Next-Era\elephant-rock-platform\sessions\260511-prime-wave\long_responses\a71ed909-fab8-42fc-923f-90576bf04b52_2503.11951.pdf", "arxiv-2503-11951", "SagaLLM: Context Management, Validation, and Transaction Guarantees for Multi-Agent LLM Planning", 2025, "https://arxiv.org/abs/2503.11951"),
]

async def main():
    settings = get_settings()
    provider = create_embedding_provider(
        provider_name=settings.embedding_provider,
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
        base_url=settings.ollama_base_url,
        dimension=settings.embedding_dimension or None,
    )
    embedding = EmbeddingService(provider, batch_size=settings.embedding_batch_size)
    ok = await embedding.validate_startup()
    print(f"embedding_valid={ok}")
    pdf = PDFService(mode=settings.s1_parser_mode, s1_parser_url=settings.s1_parser_url)
    store = VectorStore(settings.chroma_persist_dir, embedding)
    total_chunks = 0
    for pdf_path, pid, title, year, url in PAPERS:
        chunks = await pdf.parse_and_chunk(pdf_path, pid, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap)
        paper = Paper(id=pid, source="local_upload", title=title, year=year, url=url)
        count = await store.add_papers([paper], [chunks])
        total_chunks += count
        print(f"ingested id={pid} chunks={count}/{len(chunks)} title={title[:70]}")
    print(f"total_chunks={total_chunks}")

if __name__ == "__main__":
    asyncio.run(main())
