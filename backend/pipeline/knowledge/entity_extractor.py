"""LLM-based entity and relationship extraction from text."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Extract entities and relationships from the following text.

Identify: papers, authors, methods, datasets, and concepts.
For each entity, provide a name, type (paper/author/method/dataset/concept), and optional description.
For relationships, specify source, target, relationship type, and evidence.

Text:
{text}

Entity types to look for: {entity_types}

Respond with JSON matching the provided schema."""


class ExtractedEntity(BaseModel):
    name: str
    entity_type: str
    description: str = ""
    properties: dict = {}


class ExtractedRelation(BaseModel):
    source_name: str
    target_name: str
    relation_type: str
    evidence: str = ""


class ExtractionResult(BaseModel):
    entities: list[ExtractedEntity] = []
    relationships: list[ExtractedRelation] = []


class EntityExtractor:
    """LLM-based entity and relationship extraction from text."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def extract(
        self, text: str, entity_types: list[str] | None = None
    ) -> ExtractionResult:
        types_str = ", ".join(entity_types) if entity_types else "paper, author, method, dataset, concept"
        prompt = EXTRACTION_PROMPT.format(text=text[:2000], entity_types=types_str)

        try:
            result = await self._provider.structured_output(
                messages=[
                    {"role": "system", "content": "You are an entity extraction agent."},
                    {"role": "user", "content": prompt},
                ],
                schema={
                    "type": "object",
                    "properties": {
                        "entities": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "entity_type": {"type": "string"},
                                    "description": {"type": "string"},
                                    "properties": {"type": "object"},
                                },
                                "required": ["name", "entity_type"],
                            },
                        },
                        "relationships": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "source_name": {"type": "string"},
                                    "target_name": {"type": "string"},
                                    "relation_type": {"type": "string"},
                                    "evidence": {"type": "string"},
                                },
                                "required": ["source_name", "target_name", "relation_type"],
                            },
                        },
                    },
                    "required": ["entities"],
                },
                temperature=0.1,
            )

            entities = [
                ExtractedEntity(
                    name=e.get("name", ""),
                    entity_type=e.get("entity_type", "concept"),
                    description=e.get("description", ""),
                    properties=e.get("properties", {}),
                )
                for e in result.get("entities", [])
                if e.get("name")
            ]

            seen = set()
            deduped = []
            for ent in entities:
                key = (ent.name.lower(), ent.entity_type.lower())
                if key not in seen:
                    seen.add(key)
                    deduped.append(ent)

            relationships = [
                ExtractedRelation(
                    source_name=r.get("source_name", ""),
                    target_name=r.get("target_name", ""),
                    relation_type=r.get("relation_type", ""),
                    evidence=r.get("evidence", ""),
                )
                for r in result.get("relationships", [])
                if r.get("source_name") and r.get("target_name")
            ]

            return ExtractionResult(entities=deduped, relationships=relationships)

        except Exception as e:
            logger.warning("Entity extraction failed: %s", e)
            return ExtractionResult()

    async def extract_batch(self, texts: list[str]) -> list[ExtractionResult]:
        tasks = [self.extract(text) for text in texts]
        return await asyncio.gather(*tasks)
