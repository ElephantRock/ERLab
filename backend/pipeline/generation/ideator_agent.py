"""IdeatorAgent — generates raw research ideas from gaps and literature.

When a TwoStageRetriever is provided, retrieves relevant papers from the
vector store via hybrid BM25+semantic search rather than relying solely
on the static context_papers list.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Template

from backend.pipeline.gap_analysis.models import ResearchGap
from backend.pipeline.generation.models import IdeaCandidate
from backend.pipeline.literature.models import Paper
from backend.providers.base import LLMProvider

if TYPE_CHECKING:
    from backend.pipeline.knowledge.retriever import TwoStageRetriever

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent / "prompts"


class IdeatorAgent:
    def __init__(
        self,
        provider: LLMProvider,
        retriever: TwoStageRetriever | None = None,
    ):
        self._provider = provider
        self._retriever = retriever
        self._prompt_template = (PROMPT_DIR / "ideator_system.md").read_text()

    async def generate_ideas(
        self,
        gaps: list[ResearchGap],
        context_papers: list[Paper],
        prior_critique: list[str] | None = None,
        n_ideas: int = 3,
    ) -> list[IdeaCandidate]:
        """Generate raw research ideas informed by gaps and literature."""
        # RAG: retrieve relevant papers per gap when retriever is available
        if self._retriever and gaps:
            context_papers = await self._augment_with_retrieval(gaps, context_papers)

        context = self._build_context(gaps, context_papers)
        critique_text = "\n\n".join(prior_critique) if prior_critique else None

        prompt = Template(self._prompt_template).render(
            n_ideas=n_ideas,
            context=context,
            prior_critique=critique_text,
        )

        try:
            result = await self._provider.structured_output(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert AI/NLP research ideation agent.",
                    },
                    {"role": "user", "content": prompt},
                ],
                schema={
                    "type": "object",
                    "properties": {
                        "ideas": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "problem_statement": {"type": "string"},
                                    "proposed_method": {"type": "string"},
                                    "expected_contributions": {"type": "string"},
                                    "novelty_rationale": {"type": "string"},
                                    "evaluation_approach": {"type": "string"},
                                },
                                "required": ["title", "problem_statement", "proposed_method"],
                            },
                        }
                    },
                    "required": ["ideas"],
                },
                temperature=0.8,
            )

            ideas = []
            for item in result.get("ideas", []):
                ideas.append(
                    IdeaCandidate(
                        title=item.get("title", "Untitled"),
                        problem_statement=item.get("problem_statement", ""),
                        proposed_method=item.get("proposed_method", ""),
                        expected_contributions=item.get("expected_contributions", ""),
                        novelty_rationale=item.get("novelty_rationale", ""),
                        evaluation_approach=item.get("evaluation_approach", ""),
                    )
                )
            return ideas

        except Exception as e:
            logger.error("IdeatorAgent failed: %s", e)
            return []

    @staticmethod
    def _build_context(gaps: list[ResearchGap], papers: list[Paper]) -> str:
        parts = ["### Identified Research Gaps:"]
        for i, gap in enumerate(gaps, 1):
            parts.append(
                f"{i}. **{gap.title}** ({gap.gap_type})\n   {gap.description}\n   Impact: {gap.potential_impact}"
            )

        parts.append("\n### Key Literature:")
        for p in papers[:20]:
            abstract = (p.abstract or "")[:150]
            parts.append(f"- [{p.year or 'N/A'}] {p.title}: {abstract}...")

        return "\n".join(parts)

    async def _augment_with_retrieval(
        self,
        gaps: list[ResearchGap],
        existing_papers: list[Paper],
        n_results: int = 15,
    ) -> list[Paper]:
        """Retrieve papers from vector store that are relevant to each gap.

        Uses a richer query built from gap title, description, and potential impact.
        The TwoStageRetriever handles multi-query expansion if a QueryTransformer
        is wired in (MultiQueryExpander or MultiQueryTransformer).
        """
        existing_ids = {p.id for p in existing_papers}
        additional_papers: list[Paper] = []

        for gap in gaps:
            query = f"{gap.title} {gap.description}"
            if gap.potential_impact:
                query += f" {gap.potential_impact}"

            results = await self._retriever.retrieve(query, n_results=n_results)  # type: ignore[union-attr]

            unique_found = 0
            for r in results:
                paper_id = r.metadata.get("paper_id")
                if paper_id and paper_id not in existing_ids:
                    additional_papers.append(
                        Paper(
                            id=paper_id,
                            title=r.metadata.get("paper_title", ""),
                            abstract=r.text,
                            source=r.metadata.get("source", ""),
                            year=r.metadata.get("year") or None,
                        )
                    )
                    existing_ids.add(paper_id)
                    unique_found += 1

            logger.info(
                "Gap '%s': retrieved %d results, %d new papers",
                gap.title[:50], len(results), unique_found,
            )

        logger.info(
            "RAG augmentation: %d existing + %d retrieved = %d total papers",
            len(existing_papers), len(additional_papers),
            len(existing_papers) + len(additional_papers),
        )
        return existing_papers + additional_papers
