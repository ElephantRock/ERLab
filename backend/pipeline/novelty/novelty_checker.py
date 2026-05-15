"""Novelty checking — compare generated ideas against existing literature.

When a TwoStageRetriever is available, uses hybrid BM25+semantic search
for better coverage. Falls back to VectorStore-only semantic search.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.knowledge.vector_store import VectorStore
from backend.pipeline.novelty.models import (
    AxisAssessment,
    AxisType,
    DownstreamDirectives,
    NoveltyProfile,
    PriorWorkMatch,
    SearchCoverage,
    StrategicDirection,
    build_directives,
)
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
- **closest_match_similarity**: How similar on 0.0-1.0 scale
- **strategic_direction**: One of: methodological_innovation, cross_domain_bridge, emergent_problem_exploration, incremental_optimization, high_risk_moonshot"""


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
        citation_traverser: Any | None = None,
        embedding_scorer: Any | None = None,
    ):
        self._provider = provider
        self._store = store
        self._retriever = retriever
        self._citation_traverser = citation_traverser
        self._embedding_scorer = embedding_scorer

    async def check_novelty(
        self,
        idea: ResearchIdea,
        top_k: int = 20,
    ) -> tuple[NoveltyProfile, DownstreamDirectives]:
        """Check idea novelty against the knowledge base.

        Returns:
            Tuple of (NoveltyProfile, DownstreamDirectives).
        """
        query = f"{idea.title} {idea.proposed_method}"

        if self._retriever:
            results = await self._retriever.retrieve(query, n_results=top_k)
            similar = [
                {"id": r.id, "text": r.text, "metadata": r.metadata, "distance": 1.0 - r.score}
                for r in results
            ]
        else:
            similar = await self._store.query(query, n_results=top_k)

        idea_id = getattr(idea, 'id', idea.title[:60])

        if not similar:
            # No similar papers found — UNVERIFIABLE, not fake-high
            profile = NoveltyProfile(
                idea_id=idea_id,
                strategic_direction=StrategicDirection.EMERGENT_PROBLEM_EXPLORATION,
                overall_score=0.5,
                overall_confidence=0.2,
                axes=[
                    AxisAssessment(axis=AxisType.PROBLEM, score=0.5, confidence=0.2,
                                   reasoning="No search results returned"),
                    AxisAssessment(axis=AxisType.METHOD, score=0.5, confidence=0.2,
                                   reasoning="No search results returned"),
                    AxisAssessment(axis=AxisType.CONTRIBUTION, score=0.5, confidence=0.2,
                                   reasoning="No search results returned"),
                    AxisAssessment(axis=AxisType.COMBINATION, score=0.5, confidence=0.2,
                                   reasoning="No search results returned"),
                ],
                closest_prior_work=[],
                differentiations=[],
                search_coverage=SearchCoverage(
                    queries_used=[query],
                    sources_queried=["vectorstore", "bm25"],
                    results_per_source={"vectorstore": 0, "bm25": 0},
                    blind_spots_identified=["No results from any source — vector quality may be degraded"],
                ),
                novelty_arguments="No similar papers found in the knowledge base. Score is unverifiable, not confirmed novel.",
            )
            return profile, build_directives(profile)

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
                        "strategic_direction": {
                            "type": "string",
                            "enum": [
                                "methodological_innovation",
                                "cross_domain_bridge",
                                "emergent_problem_exploration",
                                "incremental_optimization",
                                "high_risk_moonshot",
                            ],
                        },
                    },
                    "required": ["overall_score", "novelty_arguments", "strategic_direction"],
                },
                temperature=0.2,
            )

            # Parse strategic direction with fallback
            raw_direction = result.get("strategic_direction", "emergent_problem_exploration")
            try:
                direction = StrategicDirection(raw_direction)
            except ValueError:
                direction = StrategicDirection.EMERGENT_PROBLEM_EXPLORATION

            # Build prior work list from similar papers
            prior_work = []
            for s in similar[:5]:
                prior_work.append(PriorWorkMatch(
                    paper_id=s.get("id", ""),
                    paper_title=s.get("metadata", {}).get("paper_title", "Unknown"),
                    overlapping_axis=AxisType.METHOD,
                    similarity=1.0 - s.get("distance", 0.5),
                    key_difference="",
                ))

            # Build NoveltyProfile from LLM output
            profile = NoveltyProfile(
                idea_id=idea_id,
                strategic_direction=direction,
                overall_score=min(1.0, max(0.0, result.get("overall_score", 0.5))),
                overall_confidence=0.8,
                axes=[
                    AxisAssessment(
                        axis=AxisType.METHOD,
                        score=min(1.0, max(0.0, result.get("method_novelty", 0.5))),
                        confidence=0.8,
                        reasoning="LLM-assessed",
                    ),
                    AxisAssessment(
                        axis=AxisType.PROBLEM,
                        score=min(1.0, max(0.0, result.get("problem_novelty", 0.5))),
                        confidence=0.8,
                        reasoning="LLM-assessed",
                    ),
                    AxisAssessment(
                        axis=AxisType.CONTRIBUTION,
                        score=min(1.0, max(0.0, result.get("combination_novelty", 0.5))),
                        confidence=0.7,
                        reasoning="LLM-assessed",
                    ),
                    AxisAssessment(
                        axis=AxisType.COMBINATION,
                        score=min(1.0, max(0.0, result.get("domain_transfer", 0.5))),
                        confidence=0.7,
                        reasoning="LLM-assessed",
                    ),
                ],
                closest_prior_work=prior_work,
                differentiations=[],
                search_coverage=SearchCoverage(
                    queries_used=[query],
                    sources_queried=["vectorstore", "bm25"],
                    results_per_source={"vectorstore": len(similar)},
                ),
                novelty_arguments=result.get("novelty_arguments", ""),
            )

            # Augment with citation traversal and embedding scoring
            profile = await self._augment_profile_with_graph_novelty(idea, profile)

            # B163: Optional S2 web novelty verification
            try:
                from backend.pipeline.novelty.s2_verifier import S2NoveltyVerifier
                s2 = getattr(self, '_s2_source', None)
                if s2:
                    verifier = S2NoveltyVerifier(s2_source=s2, llm_provider=self._provider)
                    s2_result = await verifier.verify(idea.title, idea.proposed_method)
                    # Blend S2 score with local score (50/50 weight)
                    blended = (profile.overall_score + s2_result.novelty_score) / 2.0
                    profile.overall_score = blended
                    profile.novelty_arguments += f" [S2 web check: {s2_result.llm_verdict}, {s2_result.s2_papers_found} similar papers]"
            except Exception as e:
                logger.debug("S2 novelty verification skipped: %s", e)

            return profile, build_directives(profile)

        except Exception as e:
            logger.error("Novelty check LLM call failed: %s", e)
            # Fall back to distance-based scoring
            avg_distance = sum(s.get("distance", 0.5) for s in similar[:5]) / max(
                1, len(similar[:5])
            )
            score = min(1.0, max(0.0, avg_distance))  # Higher distance = more novel
            profile = NoveltyProfile(
                idea_id=idea_id,
                strategic_direction=StrategicDirection.EMERGENT_PROBLEM_EXPLORATION,
                overall_score=score,
                overall_confidence=0.3,
                axes=[
                    AxisAssessment(axis=a, score=score, confidence=0.3,
                                   reasoning=f"Fallback distance-based: avg_dist={avg_distance:.3f}")
                    for a in AxisType
                ],
                closest_prior_work=[],
                differentiations=[],
                search_coverage=SearchCoverage(
                    queries_used=[query],
                    sources_queried=["vectorstore", "bm25"],
                    results_per_source={"vectorstore": len(similar)},
                ),
                novelty_arguments=f"Fallback distance-based score. Avg distance: {avg_distance:.3f}",
            )
            return profile, build_directives(profile)

    @staticmethod
    def _format_similar(similar: list[dict]) -> str:
        parts = []
        for i, s in enumerate(similar, 1):
            title = s.get("metadata", {}).get("paper_title", "Unknown")
            text = s.get("text", "")[:300]
            distance = s.get("distance", 0)
            parts.append(f"{i}. **{title}** (distance: {distance:.3f})\n   {text}...")
        return "\n\n".join(parts)

    async def _augment_profile_with_graph_novelty(
        self, idea: ResearchIdea, profile: NoveltyProfile,
    ) -> NoveltyProfile:
        """Augment novelty profile with citation traversal and embedding scoring."""
        # Citation traversal
        if self._citation_traverser:
            try:
                idea_id = f"idea:{idea.title[:60]}"
                prior_art = self._citation_traverser.find_prior_art(idea_id)
                if prior_art:
                    exact_matches = [p for p in prior_art if p.relationship_type == "exact"]
                    if exact_matches:
                        profile.overall_score *= 0.7
                        profile.novelty_arguments += (
                            f" [Citation graph found {len(exact_matches)} exact prior art match(es).]"
                        )
                    for pa in prior_art[:3]:
                        profile.closest_prior_work.append(PriorWorkMatch(
                            paper_id=pa.prior_art_ids[0] if pa.prior_art_ids else "",
                            paper_title=pa.prior_art_ids[0] if pa.prior_art_ids else "unknown",
                            similarity=1.0 - pa.similarity_score,
                            key_difference=f"Citation traversal (depth={pa.citation_depth}, type={pa.relationship_type})",
                        ))
            except Exception as e:
                logger.warning("Citation traversal augmentation failed: %s", e)

        # Embedding scoring
        if self._embedding_scorer:
            try:
                emb_result = await self._embedding_scorer.score_novelty(idea)
                if emb_result.min_embedding_distance < 0.2:
                    profile.overall_score *= 0.8
                    profile.novelty_arguments += (
                        f" [Embedding distance to closest: {emb_result.min_embedding_distance:.3f}]"
                    )
                profile.closest_prior_work.append(PriorWorkMatch(
                    paper_id=emb_result.closest_paper_id,
                    similarity=1.0 - emb_result.min_embedding_distance,
                    key_difference=f"Embedding novelty (avg_dist={emb_result.avg_embedding_distance:.3f})",
                ))
            except Exception as e:
                logger.warning("Embedding novelty augmentation failed: %s", e)

        return profile

    async def _augment_with_graph_novelty(
        self, idea: ResearchIdea, report: NoveltyReport,
    ) -> NoveltyReport:
        """Legacy augment for backward compat."""
        # Citation traversal
        if self._citation_traverser:
            try:
                idea_id = f"idea:{idea.title[:60]}"
                prior_art = self._citation_traverser.find_prior_art(idea_id)
                if prior_art:
                    # Reduce novelty score if close prior art is found
                    exact_matches = [p for p in prior_art if p.relationship_type == "exact"]
                    if exact_matches:
                        report.overall_score *= 0.7
                        report.novelty_arguments += (
                            f" [Citation graph found {len(exact_matches)} exact prior art match(es).]"
                        )
                    for pa in prior_art[:3]:
                        report.closest_matches.append({
                            "title": pa.prior_art_ids[0] if pa.prior_art_ids else "unknown",
                            "distance": 1.0 - pa.similarity_score,
                            "id": pa.prior_art_ids[0] if pa.prior_art_ids else "",
                            "abstract": f"Citation traversal (depth={pa.citation_depth}, type={pa.relationship_type})",
                        })
            except Exception as e:
                logger.warning("Citation traversal augmentation failed: %s", e)

        # Embedding scoring
        if self._embedding_scorer:
            try:
                emb_result = await self._embedding_scorer.score_novelty(idea)
                if emb_result.min_embedding_distance < 0.2:
                    report.overall_score *= 0.8
                    report.novelty_arguments += (
                        f" [Embedding distance to closest: {emb_result.min_embedding_distance:.3f}]"
                    )
                report.closest_matches.append({
                    "title": emb_result.closest_paper_id,
                    "distance": emb_result.min_embedding_distance,
                    "id": emb_result.closest_paper_id,
                    "abstract": f"Embedding novelty (avg_dist={emb_result.avg_embedding_distance:.3f})",
                })
            except Exception as e:
                logger.warning("Embedding novelty augmentation failed: %s", e)

        return report
