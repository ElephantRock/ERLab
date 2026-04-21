"""GAIA-style fire-and-forget memory extraction after pipeline runs.

Domain-specific extraction prompts for research facts, agent experiences,
and learned skills. Quality-gated: LLM validates before storing.
"""

import logging
from datetime import datetime

from backend.pipeline.knowledge.truth import TruthValue
from backend.pipeline.memory.models import MemoryEntry, MemoryType
from backend.pipeline.memory.service import MemoryService
from backend.pipeline.result import PipelineResult
from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Extract key facts and lessons from this research pipeline run.

## Research Gaps Identified:
{gaps_text}

## Top Ideas Generated:
{ideas_text}

For each extraction:
1. A factual observation about the research domain (e.g., "RAG with reranking outperforms naive retrieval")
2. A lesson about the pipeline process (e.g., "Round 2 ideas scored 20% higher than Round 1")
3. A reusable skill (e.g., "For NLP methodology gaps, focus on evaluation metrics first")

Respond with JSON: {{"extractions": [{{"content": "...", "type": "semantic|episodic|procedural", "tags": [...]}}]}}
"""

QUALITY_GATE_PROMPT = """Is this extracted fact accurate, specific, and useful for future research?
Fact: {fact}
Answer JSON: {{"is_valid": true/false, "reason": "..."}}"""


async def extract_from_pipeline_result(
    result: PipelineResult,
    provider: LLMProvider,
    memory: MemoryService,
    run_id: str | None = None,
) -> int:
    """Fire-and-forget background extraction after pipeline completes.

    Returns number of memories stored.
    """
    if not result.ideas and not result.gaps:
        logger.info("No ideas or gaps to extract from")
        return 0

    gaps_text = "\n".join(f"- {g.title}: {g.description[:200]}" for g in result.gaps[:10])
    ideas_text = "\n".join(
        f"- {i.title} (score: {i.score:.2f}): {i.proposed_method[:200]}"
        for i in sorted(result.ideas, key=lambda x: x.score, reverse=True)[:10]
    )

    prompt = EXTRACTION_PROMPT.format(gaps_text=gaps_text, ideas_text=ideas_text)

    try:
        raw = await provider.structured_output(
            messages=[
                {"role": "system", "content": "You are a knowledge extraction agent."},
                {"role": "user", "content": prompt},
            ],
            schema={
                "type": "object",
                "properties": {
                    "extractions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": {"type": "string"},
                                "type": {"type": "string"},
                                "tags": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["content", "type"],
                        },
                    }
                },
                "required": ["extractions"],
            },
        )

        stored = 0
        for ext in raw.get("extractions", []):
            content = ext.get("content", "").strip()
            if len(content) < 10:
                continue

            mem_type_str = ext.get("type", "semantic")
            try:
                mem_type = MemoryType(mem_type_str)
            except ValueError:
                mem_type = MemoryType.SEMANTIC

            # Quality gate: validate the extraction
            if not await _quality_gate(content, provider):
                logger.debug("Quality gate rejected: %s", content[:50])
                continue

            entry = MemoryEntry(
                id="",  # Will be set by MemoryService.store()
                content=content,
                memory_type=mem_type,
                namespace="research_facts"
                if mem_type == MemoryType.SEMANTIC
                else "pipeline_experience",
                truth=TruthValue.from_observation(frequency=0.8),
                source_run_id=run_id,
                tags=ext.get("tags", []),
                created_at=datetime.now(),
            )
            await memory.store(entry)
            stored += 1

        logger.info("Extracted and stored %d memories from pipeline run", stored)
        return stored

    except Exception as e:
        logger.error("Memory extraction failed: %s", e)
        return 0


async def _quality_gate(content: str, provider: LLMProvider) -> bool:
    """Validate an extracted fact before storing."""
    try:
        result = await provider.structured_output(
            messages=[
                {"role": "system", "content": "You validate research facts."},
                {"role": "user", "content": QUALITY_GATE_PROMPT.format(fact=content)},
            ],
            schema={
                "type": "object",
                "properties": {
                    "is_valid": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                "required": ["is_valid"],
            },
            temperature=0.1,
        )
        return result.get("is_valid", False)
    except Exception as exc:
        logger.warning("Quality gate check failed, rejecting fact: %s", exc)
        return False
