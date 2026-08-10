"""LLM-based relationship extraction between research papers.

Extracts CITES, USES_METHOD, EXTENDS, CONTRADICTS, BUILDS_ON, APPLIED_TO
relationships by comparing paper abstracts using the configured LLM provider.

Design constraints:
  - O(n) comparisons: each paper compared with at most 3 subsequent papers
  - Graceful degradation: individual extraction failures don't halt the pipeline
  - Confidence threshold: only relationships with confidence >= 0.5 are persisted
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from backend.pipeline.knowledge.relationships import KnowledgeRelationship, RelationType
from backend.pipeline.knowledge.truth import TruthValue
from backend.pipeline.utils.json_extraction import extract_json

if TYPE_CHECKING:
    from backend.pipeline.literature.models import Paper
    from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

MAX_COMPARISONS_PER_PAPER = 3  # HB-01: max LLM calls per paper
MIN_CONFIDENCE = 0.5  # Authority rule: minimum confidence to persist

RELATIONSHIP_EXTRACTION_PROMPT = """Given these two research papers, identify the primary relationship between them.

Paper A: {title_a}
Abstract: {abstract_a}

Paper B: {title_b}
Abstract: {abstract_b}

Classify the relationship. Choose exactly one:
- CITES: Paper A cites or directly references Paper B's work
- USES_METHOD: Paper A uses a method, technique, or algorithm introduced in Paper B
- EXTENDS: Paper A extends or builds upon Paper B's approach
- CONTRADICTS: Paper A contradicts or challenges Paper B's findings
- BUILDS_ON: Paper A builds on Paper B's theoretical framework
- APPLIED_TO: Paper A applies Paper B's technique to a new domain or problem

Respond with JSON only: {{"relation_type": "...", "confidence": 0.0, "evidence": "brief explanation"}}
If no meaningful relationship exists, respond: {{"relation_type": "none", "confidence": 0.0, "evidence": ""}}"""


def _parse_relation_response(text: str) -> dict | None:
    """Parse the LLM response JSON, handling common formatting issues."""
    result = extract_json(text)
    if isinstance(result, dict) and "relation_type" in result:
        return result
    return None


    try:
        result = json.loads(text)
        if isinstance(result, dict) and "relation_type" in result:
            return result
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                result = json.loads(text[start:end])
                if isinstance(result, dict) and "relation_type" in result:
                    return result
            except json.JSONDecodeError:
                pass
    return None


async def extract_relationships(
    papers: list[Paper],
    provider: LLMProvider,
    max_comparisons: int = MAX_COMPARISONS_PER_PAPER,
) -> list[KnowledgeRelationship]:
    """Extract relationships between papers using LLM.

    Each paper is compared with at most `max_comparisons` subsequent papers,
    ensuring O(n) LLM calls rather than O(n²).

    Args:
        papers: List of papers to analyze.
        provider: LLM provider for relationship classification.
        max_comparisons: Maximum comparisons per paper (HB-01).

    Returns:
        List of KnowledgeRelationship objects with confidence >= MIN_CONFIDENCE.
    """
    if len(papers) < 2:
        logger.debug("Relationship extraction skipped: fewer than 2 papers")
        return []

    relationships: list[KnowledgeRelationship] = []

    for i, paper_a in enumerate(papers):
        # Compare with at most max_comparisons subsequent papers
        for j in range(i + 1, min(i + 1 + max_comparisons, len(papers))):
            paper_b = papers[j]

            try:
                prompt = RELATIONSHIP_EXTRACTION_PROMPT.format(
                    title_a=paper_a.title[:300],
                    abstract_a=(paper_a.abstract or "")[:500],
                    title_b=paper_b.title[:300],
                    abstract_b=(paper_b.abstract or "")[:500],
                )

                response = await provider.complete(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a research relationship classifier. "
                                "Respond with JSON only. No explanation outside the JSON."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=200,
                )

                parsed = _parse_relation_response(response)
                if not parsed:
                    continue

                relation_type_str = parsed.get("relation_type", "none").lower()
                confidence = float(parsed.get("confidence", 0.0))
                evidence = parsed.get("evidence", "")

                # Skip "none" relations and low-confidence ones
                if relation_type_str == "none" or confidence < MIN_CONFIDENCE:
                    continue

                # Map string to RelationType
                try:
                    relation_type = RelationType(relation_type_str)
                except ValueError:
                    logger.debug(
                        "Unknown relation type '%s' for %s → %s",
                        relation_type_str, paper_a.title[:40], paper_b.title[:40],
                    )
                    continue

                rel = KnowledgeRelationship(
                    source_id=f"paper:{paper_a.id}",
                    target_id=f"paper:{paper_b.id}",
                    relation_type=relation_type,
                    weight=confidence,
                    evidence=[evidence] if evidence else [],
                    truth=TruthValue.from_observation(frequency=confidence),
                )
                relationships.append(rel)

                logger.debug(
                    "Extracted %s: %s → %s (confidence=%.2f)",
                    relation_type.value,
                    paper_a.title[:40],
                    paper_b.title[:40],
                    confidence,
                )

            except Exception as e:
                logger.warning(
                    "Relationship extraction failed for papers %s→%s: %s",
                    paper_a.id, paper_b.id, e,
                )
                continue

    logger.info(
        "Extracted %d relationships from %d papers",
        len(relationships), len(papers),
    )
    return relationships
