"""LLM-powered progressive summarization of accumulated pipeline context."""

from __future__ import annotations

import logging

from backend.pipeline.compaction.prompts import (
    CRITIQUE_SUMMARY_PROMPT,
    GAP_SUMMARY_PROMPT,
    REPORT_SUMMARY_PROMPT,
)
from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class ContextSummarizer:
    """Compresses intermediate pipeline data to reduce context growth."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def summarize_gaps(
        self,
        gaps: list,
        cluster_report: object | None = None,
        target_tokens: int = 500,
    ) -> str:
        """Compress gaps + cluster details into a compact summary."""
        gaps_text = "\n".join(
            f"- [{g.gap_type}] {g.title} (confidence {g.confidence:.2f}): {g.description[:200]}"
            for g in gaps
        )
        clusters_text = ""
        if cluster_report and hasattr(cluster_report, "clusters"):
            clusters_text = "\n".join(
                f"Cluster {c.cluster_id}: {c.label} ({c.paper_count} papers, terms: {', '.join(c.top_terms[:5])})"
                for c in cluster_report.clusters
            )

        prompt = GAP_SUMMARY_PROMPT.format(
            gaps_text=gaps_text,
            clusters_text=clusters_text or "No cluster data",
            target_tokens=target_tokens,
        )
        try:
            return await self._provider.complete(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=target_tokens,
            )
        except Exception:
            logger.warning("Gap summarization failed, using fallback")
            return self._fallback_gap_summary(gaps)

    async def summarize_critiques(
        self,
        critiques: list,
        target_tokens: int = 300,
    ) -> str:
        """Compress multiple critiques into key themes."""
        critiques_text = "\n".join(
            f"Idea: {c.idea_title}\n"
            f"  Weaknesses: {'; '.join(c.weaknesses[:3])}\n"
            f"  Suggestions: {'; '.join(c.suggestions[:3])}\n"
            f"  Assessment: {c.overall_assessment[:100]}"
            for c in critiques
        )

        prompt = CRITIQUE_SUMMARY_PROMPT.format(
            critiques_text=critiques_text,
            target_tokens=target_tokens,
        )
        try:
            return await self._provider.complete(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=target_tokens,
            )
        except Exception:
            logger.warning("Critique summarization failed, using fallback")
            return self._fallback_critique_summary(critiques)

    async def summarize_reports(
        self,
        novelty_report: object,
        feasibility_report: object,
        target_tokens: int = 400,
    ) -> str:
        """Compress novelty + feasibility reports into essential points."""
        prompt = REPORT_SUMMARY_PROMPT.format(
            novelty_score=f"{novelty_report.overall_score:.2f}",
            method_novelty=f"{novelty_report.method_novelty:.2f}",
            problem_novelty=f"{novelty_report.problem_novelty:.2f}",
            domain_transfer=f"{novelty_report.domain_transfer:.2f}",
            combination_novelty=f"{novelty_report.combination_novelty:.2f}",
            novelty_args=novelty_report.novelty_arguments[:300],
            feasibility_score=f"{feasibility_report.overall_score:.1f}",
            data_avail=f"{feasibility_report.data_availability:.1f}",
            compute_req=f"{feasibility_report.computational_requirements:.1f}",
            method_complexity=f"{feasibility_report.methodological_complexity:.1f}",
            eval_plan=f"{feasibility_report.evaluation_plan:.1f}",
            timeline=feasibility_report.estimated_timeline,
            risks=", ".join(feasibility_report.key_risks[:3]),
            target_tokens=target_tokens,
        )
        try:
            return await self._provider.complete(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=target_tokens,
            )
        except Exception:
            logger.warning("Report summarization failed, using fallback")
            return self._fallback_report_summary(novelty_report, feasibility_report)

    # ── Fallback summaries (no LLM call) ──────────────────────────

    @staticmethod
    def _fallback_gap_summary(gaps: list) -> str:
        lines = [f"[{g.gap_type}] {g.title} (conf {g.confidence:.2f})" for g in gaps[:10]]
        return "Gaps: " + "; ".join(lines)

    @staticmethod
    def _fallback_critique_summary(critiques: list) -> str:
        all_weaknesses: list[str] = []
        all_suggestions: list[str] = []
        for c in critiques:
            all_weaknesses.extend(c.weaknesses[:2])
            all_suggestions.extend(c.suggestions[:2])
        return (
            f"Common weaknesses: {'; '.join(all_weaknesses[:6])}. "
            f"Key suggestions: {'; '.join(all_suggestions[:6])}"
        )

    @staticmethod
    def _fallback_report_summary(novelty: object, feasibility: object) -> str:
        return (
            f"Novelty: {novelty.overall_score:.2f} "
            f"(method={novelty.method_novelty:.2f}, problem={novelty.problem_novelty:.2f}). "
            f"Feasibility: {feasibility.overall_score:.1f}/10. "
            f"Timeline: {feasibility.estimated_timeline}. "
            f"Risks: {', '.join(feasibility.key_risks[:3])}"
        )
