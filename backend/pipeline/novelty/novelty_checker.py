"""Novelty checking — compare generated ideas against existing literature.

When a TwoStageRetriever is available, uses hybrid BM25+semantic search
for better coverage. Falls back to VectorStore-only semantic search.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.knowledge.vector_store import VectorStore
from backend.providers.base import LLMProvider

if TYPE_CHECKING:
    from backend.pipeline.knowledge.retriever import TwoStageRetriever

logger = logging.getLogger(__name__)

NOVELTY_PROMPT = """You are a research novelty evaluator. Compare this research idea against the most similar
existing papers found in the literature.

## Research Idea:
Title: {title}
Problem: {problem}
Method: {method}

## Most Similar Existing Papers:
{similar_papers}

For each dimension, score from 0.0 to 1.0:
1. **method_novelty**: Is the proposed method new compared to existing approaches?
2. **problem_novelty**: Is this a new problem formulation?
3. **domain_transfer**: Does this apply existing methods to a new domain?
4. **combination_novelty**: Is the combination of techniques novel?

Also provide:
- **overall_score**: Weighted average of the above
- **novelty_arguments**: A paragraph explaining why this is or isn't novel
- **closest_match_title**: Title of the most similar existing paper
- **closest_match_similarity**: How similar on 0.0-1.0 scale"""


class NoveltyReport:
    def __init__(
        self,
        overall_score: float,
        method_novelty: float,
        problem_novelty: float,
        domain_transfer: float,
        combination_novelty: float,
        novelty_arguments: str,
        closest_matches: list[dict],
    ):
        self.overall_score = overall_score
        self.method_novelty = method_novelty
        self.problem_novelty = problem_novelty
        self.domain_transfer = domain_transfer
        self.combination_novelty = combination_novelty
        self.novelty_arguments = novelty_arguments
        self.closest_matches = closest_matches


class NoveltyChecker:
    def __init__(
        self,
        provider: LLMProvider,
        store: VectorStore,
        retriever: TwoStageRetriever | None = None,
    ):
        self._provider = provider
        self._store = store
        self._retriever = retriever

    async def check_novelty(
        self,
        idea: ResearchIdea,
        top_k: int = 20,
    ) -> NoveltyReport:
        """Check idea novelty against the knowledge base."""
        query = f"{idea.title} {idea.proposed_method}"

        if self._retriever:
            results = await self._retriever.retrieve(query, n_results=top_k)
            similar = [
                {"id": r.id, "text": r.text, "metadata": r.metadata, "distance": 1.0 - r.score}
                for r in results
            ]
        else:
            similar = await self._store.query(query, n_results=top_k)

        if not similar:
            # No similar papers found — high novelty by default
            return NoveltyReport(
                overall_score=0.8,
                method_novelty=0.8,
                problem_novelty=0.8,
                domain_transfer=0.5,
                combination_novelty=0.8,
                novelty_arguments="No similar papers found in the knowledge base.",
                closest_matches=[],
            )

        # Step 2: Format similar papers for LLM
        similar_text = self._format_similar(similar[:10])

        # Step 3: LLM novelty judgment
        prompt = NOVELTY_PROMPT.format(
            title=idea.title,
            problem=idea.problem_statement,
            method=idea.proposed_method,
            similar_papers=similar_text,
        )

        try:
            result = await self._provider.structured_output(
                messages=[
                    {"role": "system", "content": "You are an expert research novelty evaluator."},
                    {"role": "user", "content": prompt},
                ],
                schema={
                    "type": "object",
                    "properties": {
                        "method_novelty": {"type": "number"},
                        "problem_novelty": {"type": "number"},
                        "domain_transfer": {"type": "number"},
                        "combination_novelty": {"type": "number"},
                        "overall_score": {"type": "number"},
                        "novelty_arguments": {"type": "string"},
                        "closest_match_title": {"type": "string"},
                        "closest_match_similarity": {"type": "number"},
                    },
                    "required": ["overall_score", "novelty_arguments"],
                },
                temperature=0.2,
            )

            return NoveltyReport(
                overall_score=min(1.0, max(0.0, result.get("overall_score", 0.5))),
                method_novelty=min(1.0, max(0.0, result.get("method_novelty", 0.5))),
                problem_novelty=min(1.0, max(0.0, result.get("problem_novelty", 0.5))),
                domain_transfer=min(1.0, max(0.0, result.get("domain_transfer", 0.5))),
                combination_novelty=min(1.0, max(0.0, result.get("combination_novelty", 0.5))),
                novelty_arguments=result.get("novelty_arguments", ""),
                closest_matches=[
                    {
                        "title": s.get("metadata", {}).get("paper_title", "Unknown"),  # type: ignore[attr-defined]
                        "distance": s.get("distance"),  # type: ignore[attr-defined]
                        "id": s.get("id", ""),
                        "abstract": (s.get("text") or "")[:200],
                        "doi": s.get("metadata", {}).get("doi", ""),
                        "url": s.get("metadata", {}).get("url", ""),
                    }
                    for s in similar[:5]
                ],
            )

        except Exception as e:
            logger.error("Novelty check LLM call failed: %s", e)
            # Fall back to distance-based scoring
            avg_distance = sum(s.get("distance", 0.5) for s in similar[:5]) / max(  # type: ignore[attr-defined, misc]
                1, len(similar[:5])
            )
            score = min(1.0, max(0.0, avg_distance))  # Higher distance = more novel
            return NoveltyReport(
                overall_score=score,
                method_novelty=score,
                problem_novelty=score,
                domain_transfer=0.5,
                combination_novelty=score,
                novelty_arguments=f"Fallback distance-based score. Avg distance: {avg_distance:.3f}",
                closest_matches=[
                    {
                        "title": s.get("metadata", {}).get("paper_title", "Unknown"),
                        "distance": s.get("distance"),
                        "id": s.get("id", ""),
                        "abstract": (s.get("text") or "")[:200],
                    }
                    for s in similar[:5]
                ],
            )

    @staticmethod
    def _format_similar(similar: list[dict]) -> str:
        parts = []
        for i, s in enumerate(similar, 1):
            title = s.get("metadata", {}).get("paper_title", "Unknown")
            text = s.get("text", "")[:300]
            distance = s.get("distance", 0)
            parts.append(f"{i}. **{title}** (distance: {distance:.3f})\n   {text}...")
        return "\n\n".join(parts)
