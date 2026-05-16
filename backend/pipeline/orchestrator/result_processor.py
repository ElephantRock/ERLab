"""Result processor — post-stage verification, evaluation, fingerprinting, persistence.

Extracted from PipelineOrchestrator to isolate result handling
from the orchestration flow.
"""

import json
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.pipeline.result import PipelineResult
    from backend.pipeline.stages import StageContext
    from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class ResultProcessor:
    """Handles post-stage result processing: verification, evaluation, persistence."""

    def __init__(
        self,
        reference_verifier=None,
        persistence=None,
        integration=None,
        provider: "LLMProvider | None" = None,
        cross_stage_ctx=None,
    ) -> None:
        self._reference_verifier = reference_verifier
        self._persistence = persistence
        self._integration = integration
        self._provider = provider
        self._cross_stage_ctx = cross_stage_ctx

    def verify_references(self, result: "PipelineResult", ctx: "StageContext") -> None:
        """Run reference verification on all generated proposals.

        Verifies citations against corpus papers. If trust score < 0.7,
        strips unverifiable citations with [Citation needed] markers.

        HB-01: This method MUST NOT raise exceptions that propagate to the
        pipeline executor. All errors are caught and logged.
        """
        try:
            if not result.proposals:
                logger.debug("No proposals to verify — skipping reference verification")
                return
            if not self._reference_verifier:
                return

            # Build corpus paper dicts from all_papers in context
            corpus_dicts: list[dict] = []
            for paper in getattr(ctx, 'all_papers', []) or []:
                try:
                    corpus_dicts.append({
                        "title": getattr(paper, 'title', ''),
                        "authors": getattr(paper, 'authors', []),
                        "year": getattr(paper, 'year', ''),
                    })
                except Exception:
                    continue

            total_verified = 0
            total_unverifiable = 0

            for proposal in result.proposals.values() if isinstance(result.proposals, dict) else result.proposals:
                text = getattr(proposal, 'content_md', '') or getattr(proposal, 'content', '') or ''
                if not text:
                    continue

                report = self._reference_verifier.verify(text, corpus_dicts)
                trust = report.trust_score

                logger.info(
                    "Reference verification for proposal '%s': "
                    "trust=%.2f, verified=%d, unverifiable=%d, hallucinated=%d",
                    getattr(proposal, 'title', 'untitled')[:60],
                    trust,
                    report.verified,
                    report.unverifiable,
                    report.potentially_hallucinated,
                )

                if trust < 0.7:
                    logger.warning(
                        "Low reference trust score (%.2f) — stripping unverifiable citations",
                        trust,
                    )
                    cleaned = self._reference_verifier.strip_unverified_citations(text, report)
                    if hasattr(proposal, 'content_md'):
                        proposal.content_md = cleaned
                    elif hasattr(proposal, 'content'):
                        proposal.content = cleaned

                    # Store verification metadata
                    metadata = {}
                    if hasattr(proposal, 'metadata') and proposal.metadata:
                        try:
                            metadata = json.loads(proposal.metadata) if isinstance(proposal.metadata, str) else proposal.metadata
                        except (json.JSONDecodeError, TypeError):
                            metadata = {}
                    metadata["reference_verification"] = {
                        "trust_score": trust,
                        "verified": report.verified,
                        "unverifiable": report.unverifiable,
                        "hallucinated": report.potentially_hallucinated,
                        "stripped": True,
                    }
                    if hasattr(proposal, 'metadata'):
                        proposal.metadata = json.dumps(metadata) if not isinstance(metadata, str) else metadata

                total_verified += report.verified
                total_unverifiable += report.unverifiable

            logger.info(
                "Reference verification complete: %d verified, %d unverifiable across %d proposals",
                total_verified, total_unverifiable, len(result.proposals),
            )

            # Journal
            if self._integration:
                self._integration.journal_note(
                    "reference_verification",
                    f"Verified {total_verified} citations, {total_unverifiable} unverifiable",
                )

        except Exception as e:
            logger.warning("Reference verification failed (non-fatal, HB-01): %s", e)

    def evaluate_pipeline(self, result: "PipelineResult", ctx: "StageContext") -> None:
        """Run pipeline quality evaluation after all stages complete.

        Compares detected gaps against gold-standard lists and computes
        precision, recall, novelty rate, and overall quality score.

        HB-01: Non-blocking — catches all exceptions.
        """
        try:
            from backend.pipeline.verification.pipeline_evaluator import PipelineEvaluator as PE
            from backend.pipeline.verification.gold_standards import get_gold_gaps

            domain = ctx.domain or "AI/NLP"
            gold_gaps = get_gold_gaps(domain)
            evaluator = PE(known_gaps=gold_gaps)

            detected = [
                {"title": g.title, "description": getattr(g, 'description', ''),
                 "gap_type": getattr(g, 'gap_type', 'unknown')}
                for g in result.gaps
            ]
            ideas = [
                {"title": getattr(i, 'title', ''), "novelty_score": getattr(i, 'score', 0.5)}
                for i in result.ideas
            ]

            report = evaluator.evaluate(detected, ideas)

            logger.info(
                "Pipeline quality: score=%.2f, gap_recall=%.1f%%, gap_precision=%.1f%%, "
                "idea_novelty=%.1f%%",
                report.pipeline_quality_score,
                report.gap_recall * 100,
                report.gap_precision * 100,
                report.idea_novelty_rate * 100,
            )

            result.quality_report = {
                "pipeline_quality_score": report.pipeline_quality_score,
                "gap_recall": report.gap_recall,
                "gap_precision": report.gap_precision,
                "idea_novelty_rate": report.idea_novelty_rate,
                "gaps_detected": report.gaps_detected,
                "gaps_novel": report.gaps_novel,
                "ideas_generated": report.ideas_generated,
                "ideas_novel": report.ideas_novel,
            }

            if self._integration:
                self._integration.journal_note(
                    "pipeline_evaluation",
                    f"Quality score: {report.pipeline_quality_score:.2f}",
                )

        except Exception as e:
            logger.warning("Pipeline evaluation failed (non-fatal): %s", e)

    @staticmethod
    def extract_stage_fingerprint(stage_name: str, result: "PipelineResult") -> str:
        """Extract minimal fingerprint for doom-prone stages.

        Only gap_analysis, idea_generation, and proposal_synthesis produce
        fingerprints — these are the stages most likely to loop.
        """
        if stage_name == "gap_analysis":
            if result.gaps:
                return "|".join(g.title for g in result.gaps)
            return ""

        if stage_name == "idea_generation":
            if result.ideas:
                parts = [f"{i.title}:{i.score:.2f}" for i in result.ideas]
                return "|".join(parts)
            return ""

        if stage_name == "proposal_synthesis":
            if result.proposals:
                parts = []
                for prop in result.proposals.values():
                    abstract = getattr(prop, 'abstract', '') or ''
                    if not abstract and hasattr(prop, 'sections'):
                        abstract = prop.sections.get('abstract', '')
                    parts.append(abstract[:500])
                return "|".join(parts)
            return ""

        return ""

    def should_stop(self, budget, cost_tracker, settings) -> bool:
        """Check if pipeline should stop due to budget/cost limits."""
        if not budget:
            return False
        from backend.pipeline.autonomy.budget import BudgetPolicy

        policy = budget.check_policy()
        if policy == BudgetPolicy.STOP:
            logger.warning("Budget STOP triggered. Halting pipeline.")
            return True
        if policy == BudgetPolicy.REPLAN:
            logger.warning("Budget REPLAN — 80%% budget used. Continuing with caution.")
        if cost_tracker:
            summary = cost_tracker.summary()
            if summary["total_cost_usd"] > settings.budget_max_cost_usd:
                logger.warning(
                    "Cost tracker STOP: $%.2f exceeds budget $%.2f",
                    summary["total_cost_usd"],
                    settings.budget_max_cost_usd,
                )
                return True
        return False

    async def persist_stage_context(
        self, run_id: str, stage_name: str, ctx: "StageContext", result: "PipelineResult"
    ) -> None:
        """Save stage outputs to cross-stage context for later retrieval."""
        try:
            if not self._cross_stage_ctx:
                return
            if stage_name == "literature_search" and ctx.all_papers:
                await self._cross_stage_ctx.save_stage_output(
                    run_id, "literature_search", "papers",
                    [{"title": p.title, "abstract": getattr(p, "abstract", "")}
                     for p in ctx.all_papers[:50]],
                )
            elif stage_name == "gap_analysis" and result.gaps:
                await self._cross_stage_ctx.save_stage_output(
                    run_id, "gap_analysis", "gaps",
                    [{"title": g.title, "description": g.description,
                      "confidence": g.confidence, "gap_type": g.gap_type}
                     for g in result.gaps],
                )
            elif stage_name == "idea_generation" and result.ideas:
                await self._cross_stage_ctx.save_stage_output(
                    run_id, "idea_generation", "ideas",
                    [{"title": i.title, "proposed_method": getattr(i, "proposed_method", ""),
                      "score": i.score, "domain": getattr(i, "domain", "")}
                     for i in result.ideas],
                )
            elif stage_name == "feasibility_scoring" and result.feasibility_reports:
                await self._cross_stage_ctx.save_stage_output(
                    run_id, "feasibility_scoring", "scores",
                    {str(k): {"overall": v.overall_score}
                     for k, v in result.feasibility_reports.items()},
                )
            elif stage_name == "proposal_synthesis" and result.proposals:
                await self._cross_stage_ctx.save_stage_output(
                    run_id, "proposal_synthesis", "proposals",
                    {"count": len(result.proposals)},
                )
        except Exception as exc:
            logger.warning("Failed to persist cross-stage context for %s: %s", stage_name, exc)

    def collect_warnings(self, result: "PipelineResult") -> None:
        """Collect persistence warnings into the result."""
        if self._persistence:
            warnings = self._persistence.get_warnings()
            if warnings:
                result.persistence_warnings.extend(warnings)

    def persist_stage_report(self, result: "PipelineResult", db_run_id: int | None) -> None:
        """Persist stage_report list to DB (BATCH-173)."""
        if not db_run_id or not result.stage_report:
            return
        try:
            from backend.db.database import get_session
            from backend.db.models import PipelineRun

            report_json = json.dumps([r.to_dict() for r in result.stage_report])
            with get_session() as session:
                run = session.query(PipelineRun).filter(PipelineRun.id == db_run_id).first()
                if run:
                    run.stage_report_json = report_json
                    session.commit()
        except Exception as e:
            logger.warning("Failed to persist stage_report: %s", e)

    async def background_memory_extraction(self, result: "PipelineResult", run_id: str,
                                            provider, memory_service) -> None:
        """Extract memories from pipeline result in background."""
        try:
            from backend.pipeline.memory.extraction import extract_from_pipeline_result
            stored = await extract_from_pipeline_result(
                result, provider, memory_service, run_id=run_id,
            )
            logger.info("Background memory extraction: stored %d memories", stored)
        except Exception as e:
            logger.error("Background memory extraction failed: %s", e)
