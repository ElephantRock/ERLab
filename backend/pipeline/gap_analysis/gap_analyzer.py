"""Gap analysis — identify underexplored research areas."""

import json
import logging

from backend.pipeline.gap_analysis.cluster_service import ClusterService
from backend.pipeline.gap_analysis.models import ClusterReport, ResearchGap
from backend.pipeline.knowledge.truth import TruthValue
from backend.pipeline.literature.models import Paper
from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

GAP_ANALYSIS_PROMPT = """You are an expert AI/NLP research analyst. Analyze the following research landscape
and identify {max_gaps} significant research gaps.

## Current Research Clusters:
{cluster_summary}

## Sample Papers:
{paper_summaries}

## CITATION INTEGRITY (MANDATORY)
You MUST only reference papers that are listed in the Sample Papers section above.
Do NOT invent, fabricate, or hallucinate any paper titles, authors, or years.
If you mention a paper, it MUST appear in the Sample Papers list.
If you are unsure whether a paper exists in the provided list, do not cite it.
Instead, describe the gap in general terms without naming a specific paper.

For each gap, provide:
1. A concise title
2. A detailed description of what's missing or underexplored
3. The gap type: methodological, empirical, theoretical, or cross-domain
4. Which clusters it relates to
5. The potential impact if addressed
6. Your confidence in this being a genuine gap (0.0 to 1.0)
7. Specific paper references from the Sample Papers list that support this gap (use only papers listed above)

Respond with a JSON array of objects with keys: title, description, gap_type, related_clusters, potential_impact, confidence"""


def _title_similarity(a: str, b: str) -> float:
    """Simple word-overlap similarity between two titles."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


class GapAnalyzer:
    def __init__(self, provider: LLMProvider):
        self._provider = provider
        self._cluster_service = ClusterService()

    async def analyze(
        self,
        papers: list[Paper],
        domain: str = "AI/NLP",
        max_gaps: int = 5,
        prior_gaps: list[ResearchGap] | None = None,
    ) -> tuple[list[ResearchGap], ClusterReport]:
        """Identify research gaps from a collection of papers.

        When prior_gaps are provided, gaps that match prior gaps by title
        similarity have their truth values revised (evidence accumulation)
        rather than replaced.

        Returns (gaps, cluster_report).
        """
        # Step 1: Cluster the papers
        cluster_report = await self._cluster_service.cluster_papers(papers)

        # Step 2: Build context for LLM
        cluster_summary = self._format_clusters(cluster_report)
        paper_summaries = self._format_paper_summaries(papers[:20])  # Limit context to avoid timeout

        # Step 3: Ask LLM to identify gaps
        prompt = GAP_ANALYSIS_PROMPT.format(
            max_gaps=max_gaps,
            cluster_summary=cluster_summary,
            paper_summaries=paper_summaries,
        )

        try:
            # Use complete() instead of structured_output() to avoid tool_use timeout
            # through the z.ai proxy
            raw_response = await self._provider.complete(
                messages=[
                    {"role": "system", "content": f"You are a {domain} research analyst. Respond with valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=4096,
            )

            # Parse JSON from response
            response_text = raw_response.strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            parsed = json.loads(response_text)
            result = parsed if isinstance(parsed, dict) else {"gaps": parsed}

            gaps = []
            # Handle both dict and list returns from different providers
            raw_gaps = result.get("gaps", []) if isinstance(result, dict) else (result if isinstance(result, list) else [])
            for g in raw_gaps:
                # Normalize related_clusters: local LLMs may return strings instead of ints
                clusters_raw = g.get("related_clusters", [])
                clusters_normalized: list[int] = []
                for c in clusters_raw:
                    if isinstance(c, int):
                        clusters_normalized.append(c)
                    elif isinstance(c, str):
                        # Try to extract integer from strings like "Cluster 1 (vision)" or "1"
                        import re as _re
                        match = _re.search(r'\d+', c)
                        if match:
                            clusters_normalized.append(int(match.group()))
                    elif isinstance(c, (float,)):
                        clusters_normalized.append(int(c))

                new_gap = ResearchGap(
                    title=g.get("title", "Untitled Gap"),
                    description=g.get("description", ""),
                    gap_type=g.get("gap_type", "unknown"),
                    related_clusters=clusters_normalized,
                    potential_impact=g.get("potential_impact", ""),
                    confidence=min(1.0, max(0.0, float(g.get("confidence", 0.5)))),
                )

                # Truth revision: if this gap matches a prior gap, revise truth
                if prior_gaps:
                    matched = False
                    for prior in prior_gaps:
                        sim = _title_similarity(new_gap.title, prior.title)
                        if sim > 0.8:
                            new_observation = TruthValue.from_observation(
                                frequency=new_gap.confidence,
                            )
                            new_gap = ResearchGap(
                                title=prior.title,
                                description=new_gap.description,
                                gap_type=new_gap.gap_type,
                                related_clusters=new_gap.related_clusters,
                                potential_impact=new_gap.potential_impact,
                                confidence=new_gap.confidence,
                                truth=prior.truth.revise(new_observation),
                            )
                            matched = True
                            logger.info(
                                "Revised truth for gap '%s': %s",
                                prior.title,
                                new_gap.truth,
                            )
                            break
                    if not matched:
                        new_gap = ResearchGap(
                            **new_gap.model_dump(exclude={"truth"}),
                            truth=TruthValue.from_observation(
                                frequency=new_gap.confidence,
                            ),
                        )
                else:
                    new_gap = ResearchGap(
                        **new_gap.model_dump(exclude={"truth"}),
                        truth=TruthValue.from_observation(
                            frequency=new_gap.confidence,
                        ),
                    )

                gaps.append(new_gap)
            return sorted(gaps, key=lambda g: g.confidence, reverse=True), cluster_report

        except Exception as e:
            logger.error("Gap analysis LLM call failed: %s", e, exc_info=True)
            return [], cluster_report

    @staticmethod
    def _format_clusters(report: ClusterReport) -> str:
        lines = []
        for c in report.clusters:
            lines.append(
                f"- Cluster {c.cluster_id} ({c.label}): {c.paper_count} papers, "
                f"avg citations: {c.avg_citations:.1f}"
                if c.avg_citations
                else f"- Cluster {c.cluster_id} ({c.label}): {c.paper_count} papers"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_paper_summaries(papers: list[Paper]) -> str:
        lines = []
        for i, p in enumerate(papers[:30], 1):
            abstract = (p.abstract or "")[:150]
            # Include authors and year for citation grounding
            authors_str = ""
            if hasattr(p, 'authors') and p.authors:
                if isinstance(p.authors, list):
                    names = []
                    for a in p.authors[:3]:
                        if hasattr(a, 'name'):
                            names.append(a.name)
                        else:
                            names.append(str(a))
                    authors_str = ", ".join(names)
                    if len(p.authors) > 3:
                        authors_str += " et al."
                else:
                    authors_str = str(p.authors)
            year_str = str(p.year) if p.year else "N/A"
            author_line = f" Authors: {authors_str}" if authors_str else ""
            lines.append(f"{i}. [{year_str}] {p.title}{author_line}\n   {abstract}...")
        return "\n".join(lines) if lines else "(No papers provided)"
