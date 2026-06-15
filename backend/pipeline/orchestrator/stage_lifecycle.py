"""Stage lifecycle handlers — post-stage and post-pipeline processing.

Extracted from PipelineOrchestrator.run() to separate processing logic
from the stage iteration loop.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.pipeline.result import PipelineResult, StageReport
    from backend.pipeline.stages import PipelineStage, StageContext
    from backend.pipeline.execution.run_state import RunCheckpoint
    from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class StageLifecycle:
    """Handles per-stage post-processing and post-pipeline finalization."""

    def __init__(
        self,
        services,  # ServiceRegistry
        settings,
        persistence,
        integration,
        processor,  # ResultProcessor
        provider: "LLMProvider",
        cost_tracker=None,
        compaction=None,
        token_counter=None,
        notifier=None,
        ccw=None,
    ) -> None:
        self._services = services
        self._settings = settings
        self._persistence = persistence
        self._integration = integration
        self._processor = processor
        self._provider = provider
        self._cost_tracker = cost_tracker
        self._compaction = compaction
        self._token_counter = token_counter
        self._notifier = notifier
        self._ccw = ccw
        self._doom_history: list[dict] = []
        self._doom_detected = False

    def set_run_context(self, ccw=None, notifier=None, integration=None) -> None:
        """Update per-run instances that are created inside run()."""
        self._ccw = ccw
        self._notifier = notifier
        self._integration = integration

    def reset_doom(self) -> None:
        """Reset doom loop state for a new run."""
        self._doom_history = []
        self._doom_detected = False

    @property
    def doom_detected(self) -> bool:
        return self._doom_detected

    async def post_stage_common(
        self,
        stage: "PipelineStage",
        result: "PipelineResult",
        ctx: "StageContext",
        elapsed: float,
        run_id: str,
        domain: str,
        strategy: str,
    ) -> None:
        """Run common post-stage processing: contracts, compaction, hooks, doom, CCW, notifications."""
        # Contract verification — Phase 3: wire violations into StageReport
        try:
            from backend.pipeline.monitoring.contracts import STAGE_CONTRACTS, verify_contract
            contract = STAGE_CONTRACTS.get(stage.name)
            if contract:
                violation = verify_contract(stage.name, result, contract)
                if violation:
                    # Populate StageReport with violations
                    latest_report = result.stage_report[-1] if result.stage_report else None
                    if latest_report and latest_report.name == stage.name:
                        latest_report.contract_violations = violation.violations
                        latest_report.data_quality = {
                            "is_error": violation.is_error,
                            "contract_name": contract.stage_name,
                        }

                    if violation.is_error:
                        logger.error(
                            "CONTRACT VIOLATION: %s — %s",
                            stage.name, "; ".join(violation.violations),
                        )
                        # Phase 3: Hard enforcement mode
                        enforcement = getattr(self._settings, "contract_enforcement_mode", "warn")
                        if enforcement == "enforce" and latest_report:
                            latest_report.status = "contract_violation"
                            logger.warning(
                                "Contract enforcement: stage '%s' marked as contract_violation",
                                stage.name,
                            )
                    else:
                        logger.warning(
                            "CONTRACT WARNING: %s — %s",
                            stage.name, "; ".join(violation.violations),
                        )
        except Exception as e:
            logger.debug("Contract verification failed (non-fatal): %s", e)

        # Compaction recording
        if self._compaction:
            self._compaction.record_usage(stage.name)

        # Metacognitive recording
        if self._services.metacog:
            self._services.metacog.record_stage(stage.name, {"elapsed_seconds": elapsed})

        # Hook dispatch
        await self._services.hooks.dispatch_sync_safe(
            "pipeline.stage.complete",
            {"stage": stage.name, "elapsed": elapsed, "run_id": run_id},
        )

        # Doom loop detection
        if not self._doom_detected:
            try:
                from backend.pipeline.monitoring.doom_loop import (
                    extract_stage_fingerprint,
                    hash_stage_output,
                    check_pipeline_doom,
                )
                fingerprint = extract_stage_fingerprint(
                    stage.name,
                    gaps=result.gaps if hasattr(result, 'gaps') else None,
                    ideas=result.ideas if hasattr(result, 'ideas') else None,
                    proposals=result.proposals if hasattr(result, 'proposals') else None,
                )
                if fingerprint:
                    self._doom_history.append({
                        "stage_name": stage.name,
                        "output_hash": hash_stage_output(fingerprint),
                    })
                    doom_msg = check_pipeline_doom(self._doom_history)
                    if doom_msg:
                        logger.warning("Doom loop detected: %s", doom_msg)
                        self._doom_detected = True
            except Exception as e:
                logger.debug("Doom loop check failed for %s: %s", stage.name, e)

        # CCW compression after key stages
        if self._ccw:
            try:
                if stage.name in ("literature_search", "ingestion"):
                    if ctx.all_papers:
                        self._ccw.add_papers(ctx.all_papers)
                        logger.info("CCW: compressed %d papers (%d tokens)",
                                     len(self._ccw.papers), self._ccw.estimate_tokens())
                elif stage.name == "gap_analysis":
                    if result.gaps:
                        self._ccw.add_gaps(result.gaps)
                        logger.info("CCW: compressed %d gaps", len(self._ccw.gaps))
                elif stage.name == "idea_generation":
                    if result.ideas:
                        self._ccw.add_ideas(result.ideas)
                        logger.info("CCW: compressed %d ideas", len(self._ccw.ideas))
            except Exception as e:
                logger.debug("CCW compression failed for %s: %s", stage.name, e)

        # Stage completion notification
        if self._notifier:
            try:
                from backend.pipeline.notifications.gateway import Notification, PipelineEvent
                await self._notifier.send(Notification(
                    event=PipelineEvent.STAGE_COMPLETED,
                    run_id=run_id, strategy=strategy, domain=domain,
                    message=f"Stage {stage.name} completed ({elapsed:.1f}s)",
                    data={"stage": stage.name, "elapsed": elapsed},
                ))
            except Exception:
                pass

    async def post_stage_specific(
        self,
        stage: "PipelineStage",
        result: "PipelineResult",
        ctx: "StageContext",
        run_id: str,
        db_run_id: int | None,
        domain: str,
        strategy: str,
        should_continue: bool,
    ) -> str | None:
        """Run stage-specific post-processing. Returns 'abort' if pipeline should stop."""
        if stage.name == "literature_search":
            return await self._post_literature_search(result, ctx, run_id, db_run_id, domain, strategy, should_continue)

        if stage.name == "gap_analysis":
            self._persistence.persist_gaps(result, db_run_id)
            self._processor.collect_warnings(result)

        elif stage.name == "idea_generation":
            self._persistence.persist_ideas(result, db_run_id)
            self._processor.collect_warnings(result)
            if getattr(result, 'tree_data', None):
                self._persistence.persist_tree_data(result.tree_data, db_run_id)
                self._processor.collect_warnings(result)

        elif stage.name == "feasibility_scoring":
            await self._post_feasibility_scoring(result)

        elif stage.name == "proposal_synthesis":
            await self._post_proposal_synthesis(result, ctx)

        return None

    async def _post_literature_search(
        self, result, ctx, run_id, db_run_id, domain, strategy, should_continue
    ) -> str | None:
        """Post-processing for literature_search: persist, rerank, metrics, early-exit check."""
        from backend.pipeline.result import StageReport

        self._persistence.persist_papers(ctx.all_papers, db_run_id)
        self._processor.collect_warnings(result)

        # Rerank papers using cross-encoder
        if self._settings.reranker_enabled:
            try:
                from backend.pipeline.knowledge.reranker import create_reranker
                reranker = create_reranker("auto")
                if ctx.all_papers and ctx.domain:
                    docs = [
                        {"id": str(p.id), "text": f"{p.title} {p.abstract or ''}"}
                        for p in ctx.all_papers
                        if p.abstract
                    ]
                    if docs:
                        ranked = await reranker.rerank(ctx.domain, docs, top_k=min(20, len(docs)))
                        ranked_ids = {r.id: r.score for r in ranked}
                        scored_papers = []
                        for p in ctx.all_papers:
                            score = ranked_ids.get(str(p.id), 0.0)
                            scored_papers.append((score, p))
                        scored_papers.sort(key=lambda x: x[0], reverse=True)
                        ctx.all_papers = [p for _, p in scored_papers]
                        logger.info(
                            "Reranked %d papers, top score=%.3f",
                            len(ranked), ranked[0].score if ranked else 0.0,
                        )
            except Exception as e:
                logger.debug("Reranking skipped: %s", str(e)[:100])

        # Compute retrieval metrics
        try:
            from backend.pipeline.evaluation.retrieval_metrics import (
                compute_retrieval_metrics,
                RetrievedDocument,
            )
            queries = ctx.search_queries or [ctx.domain]
            if ctx.all_papers and queries:
                docs_per_query = []
                for q in queries:
                    docs = [
                        RetrievedDocument(
                            doc_id=str(p.id),
                            rank=i + 1,
                            score=p.relevance_score or 0.0,
                            is_relevant=False,
                        )
                        for i, p in enumerate(ctx.all_papers[:20])
                    ]
                    docs_per_query.append((q, docs))
                metrics_report = compute_retrieval_metrics(docs_per_query)
                metrics_report.domain = ctx.domain
                metrics_report.strategy = ctx.params.get("strategy", "unknown")
                if not hasattr(result, '_retrieval_metrics'):
                    result._retrieval_metrics = metrics_report
                logger.info(
                    "Retrieval metrics: %d queries, %d docs, hit_rate=%.2f",
                    metrics_report.total_queries,
                    metrics_report.total_documents_retrieved,
                    metrics_report.hit_rate,
                )
        except Exception as e:
            logger.debug("Retrieval metrics computation skipped: %s", str(e)[:100])

        # Early exit if no papers found
        if not should_continue:
            self._persistence.mark_run_failed(db_run_id, "No papers found")
            self._processor.collect_warnings(result)
            await self._services.hooks.dispatch_sync_safe(
                "pipeline.complete",
                {"run_id": run_id, "status": "no_papers"},
            )
            return "abort"

        return None

    async def _post_feasibility_scoring(self, result) -> None:
        """Post-processing for feasibility_scoring: evaluate, quality backloop."""
        self._persistence.persist_ideas(result, None)
        self._processor.collect_warnings(result)

        # Unified evaluation (WP-02)
        if self._services.pipeline_evaluator:
            eval_reports = await self._services.pipeline_evaluator.evaluate_all(
                ideas=result.ideas,
                novelty_reports=result.novelty_reports,
                feasibility_reports=result.feasibility_reports,
            )
            result.evaluation_reports = eval_reports
            for idx, er in eval_reports.items():
                if er.quality_gate_result and not er.quality_gate_result.passed:
                    logger.warning(
                        "Idea '%s' failed quality gate: %s (%s)",
                        er.idea_title[:50],
                        er.quality_gate_result.failures,
                        er.quality_gate_result.recommendation,
                    )
            if self._services.metacog:
                for er in eval_reports.values():
                    self._services.metacog.record_evaluation(er)
                plateau = self._services.metacog.check_plateau("overall_score")
                if plateau.is_plateau:
                    logger.warning("Metacognitive plateau: %s", plateau.reason)

        # Quality backloop (Gap 12) + Phase 7: abandonment tracking
        if getattr(self._settings, "quality_backloop_enabled", False) and result.ideas:
            avg_score = sum(i.score for i in result.ideas) / len(result.ideas)
            min_composite = getattr(self._settings, "quality_backloop_min_composite", 0.4)
            if avg_score < min_composite:
                logger.info(
                    "Quality backloop: avg score %.3f < %.3f, regenerating ideas",
                    avg_score, min_composite,
                )
                # Phase 7: Record abandoned ideas before removing
                if getattr(self._settings, "abandonment_tracking_enabled", True):
                    removed = [i for i in result.ideas if i.score < min_composite]
                    if removed:
                        try:
                            from backend.pipeline.research.abandonment import AbandonmentTracker
                            tracker = AbandonmentTracker(
                                getattr(self._settings, "abandonment_tracking_path",
                                       "./data/abandoned_directions.jsonl")
                            )
                            for idea in removed:
                                tracker.record(
                                    direction=getattr(idea, "title", "Untitled idea"),
                                    reason=f"Low composite score ({idea.score:.2f} < {min_composite})",
                                    evidence=f"Novelty/feasibility scores below viable threshold",
                                    run_id=getattr(result, 'run_id', 'unknown'),
                                    reopen_condition="Higher-quality literature or different angle",
                                )
                            logger.info("Recorded %d abandoned ideas", len(removed))
                        except Exception as e:
                            logger.warning("Failed to record abandoned ideas: %s", e)
                result.ideas = [i for i in result.ideas if i.score >= min_composite]

    async def _post_proposal_synthesis(self, result, ctx) -> None:
        """Post-processing for proposal_synthesis: persist, verify references, faithfulness."""
        self._persistence.persist_proposals(result, None)
        self._processor.collect_warnings(result)
        self._processor.verify_references(result, ctx)

        # Faithfulness scoring
        try:
            from backend.pipeline.evaluation.faithfulness_scorer import FaithfulnessScorer
            scorer = FaithfulnessScorer(provider=None)
            source_abstracts = [
                p.abstract for p in ctx.all_papers[:30]
                if hasattr(p, 'abstract') and p.abstract
            ]
            for prop in result.proposals:
                report = asyncio.get_event_loop().run_until_complete(
                    scorer.score_proposal(
                        proposal_text=prop.methodology if hasattr(prop, 'methodology') else str(prop),
                        proposal_title=prop.title if hasattr(prop, 'title') else "",
                        proposal_id=str(prop.id) if hasattr(prop, 'id') else "",
                        source_texts=source_abstracts,
                    )
                )
                prop._faithfulness_report = report
            logger.info("Faithfulness scoring complete for %d proposals", len(result.proposals))
        except Exception as e:
            logger.debug("Faithfulness scoring skipped: %s", str(e)[:100])

        # Phase 4: Evidence provenance checking
        if getattr(self._settings, "provenance_check_enabled", True):
            try:
                from backend.pipeline.verification.provenance_checker import ProvenanceChecker
                provenance_checker = ProvenanceChecker(provider=self._provider)

                corpus_dicts = [
                    {"title": getattr(p, 'title', ''), "abstract": getattr(p, 'abstract', '') or ''}
                    for p in ctx.all_papers[:50]
                ]

                provenance_results = {}
                for idx, proposal in result.proposals.items():
                    text = (
                        getattr(proposal, 'content_md', '')
                        or getattr(proposal, 'methodology', '')
                        or str(proposal)
                    )
                    report = provenance_checker.check(text, corpus_dicts)
                    provenance_results[idx] = report.to_dict()

                    logger.info(
                        "Provenance proposal %d: %d/%d claims supported (%.0f%% coverage)",
                        idx, report.supported_claims, report.total_claims,
                        report.coverage_ratio * 100,
                    )

                    if report.is_low_coverage:
                        logger.warning(
                            "Low provenance coverage (%.0f%%) for proposal %d",
                            report.coverage_ratio * 100, idx,
                        )

                # Store in quality_report for decision gate
                if not hasattr(result, 'quality_report') or result.quality_report is None:
                    result.quality_report = {}
                result.quality_report["provenance"] = provenance_results

            except Exception as e:
                logger.warning("Provenance check failed (non-fatal): %s", str(e)[:200])

    async def post_pipeline_finalize(
        self,
        result: "PipelineResult",
        ctx: "StageContext",
        run_id: str,
        domain: str,
        strategy: str,
        params: dict,
        db_run_id: int | None,
        session_id: str | None,
        ideas_per: int,
        rounds: int,
    ) -> None:
        """Run all post-pipeline finalization: self-improve, lessons, world model, cleanup."""
        # Pipeline quality evaluation
        self._processor.evaluate_pipeline(result, ctx)

        # Self-improvement evaluation
        if self._services.evolver and result.ideas:
            avg_score = sum(i.score for i in result.ideas) / len(result.ideas)
            avg_novelty = (
                sum(r.overall_score for r in result.novelty_reports.values())
                / len(result.novelty_reports)
                if result.novelty_reports
                else 0.0
            )

            from backend.pipeline.self_improve.fitness import FitnessScore
            total_text = sum(len(i.proposed_method) for i in result.ideas)
            length_penalty = FitnessScore.length_penalty_ramp(total_text, 50000)
            fitness = FitnessScore(
                correctness=avg_score,
                procedure_following=min(1.0, len(result.ideas) / max(1, ideas_per * rounds)),
                conciseness=1.0 - length_penalty,
                length_penalty=length_penalty,
            )

            self._services.evolver.evaluate(
                params=params,
                run_id=run_id,
                avg_idea_score=avg_score,
                avg_novelty_score=avg_novelty,
                good_ideas=sum(1 for i in result.ideas if i.score >= 0.6),
                fitness=fitness,
            )

        # Lesson extraction → store as memories
        if self._services.lesson_extractor and result.ideas:
            avg_score = sum(i.score for i in result.ideas) / len(result.ideas)
            if avg_score < 0.7:
                lessons = await self._services.lesson_extractor.extract(result, params)
                if lessons:
                    logger.info("Extracted %d lessons from run", len(lessons))
                    if self._services.memory:
                        from backend.pipeline.knowledge.truth import TruthValue
                        from backend.pipeline.memory.models import MemoryEntry, MemoryType

                        for lesson in lessons:
                            try:
                                entry = MemoryEntry(
                                    id="",
                                    content=str(lesson),
                                    memory_type=MemoryType.EPISODIC,
                                    namespace="pipeline_experience",
                                    truth=TruthValue.from_observation(frequency=0.7),
                                    tags=["lesson", "self_improve"],
                                    created_at=datetime.now(),
                                )
                                await self._services.memory.store(entry)
                            except Exception as e:
                                logger.warning("Failed to store lesson as memory: %s", e)
                        logger.info("Stored %d lessons as memories", len(lessons))

                    if self._services.evolver and lessons:
                        adjusted = self._services.evolver.apply_lessons(
                            [str(l) for l in lessons], params
                        )
                        logger.info(
                            "Lessons fed back to evolver. %d params adjusted",
                            sum(1 for k in adjusted if adjusted[k] != params.get(k)),
                        )

                    # Skill evolution
                    if (self._services.skill_proposer and self._services.skill_generator
                            and self._services.skill_registry):
                        skills = self._services.skill_registry.discover(domain=domain)
                        for skill in skills:
                            try:
                                diagnosis, suggestion = await self._services.skill_proposer.diagnose(
                                    skill, trace=str(lessons)
                                )
                                improved = await self._services.skill_generator.generate(
                                    skill, diagnosis, suggestion
                                )
                                self._services.skill_registry.add_version(skill.id, improved, score=avg_score)
                            except Exception as e:
                                logger.warning("Skill evolution failed for %s: %s", skill.id, e)

        # World model update + change detection
        if self._services.world_model and result.ideas:
            await self._services.world_model.update_from_run(result, self._provider)
            logger.info("World model updated")

            if self._services.kg and getattr(self._settings, "versioning_enabled", True):
                from backend.pipeline.knowledge.change_detector import WorldModelChangeDetector
                detector = WorldModelChangeDetector(
                    self._services.kg,
                    contradiction_scanner=self._services.contradiction_scanner,
                )
                summary = await detector.check_and_notify(
                    goal_manager=None,
                )
                if summary and summary.severity.value != "low":
                    logger.info(
                        "Change detection: %s severity, %d changes",
                        summary.severity.value, summary.total_changes,
                    )

        # Fire-and-forget memory extraction
        if self._services.memory:
            asyncio.create_task(
                self._processor.background_memory_extraction(
                    result, run_id, self._provider, self._services.memory
                )
            )

        # Hook: pipeline.complete
        await self._services.hooks.dispatch_sync_safe(
            "pipeline.complete",
            {
                "run_id": run_id,
                "ideas_count": len(result.ideas),
                "gaps_count": len(result.gaps),
                "proposals_count": len(result.proposals),
            },
        )

        logger.info("=== Pipeline Complete ===")

        # Determine if pipeline produced meaningful output
        n_gaps = len(result.gaps) if result.gaps else 0
        n_ideas = len(result.ideas) if result.ideas else 0
        n_proposals = len(result.proposals) if result.proposals else 0

        if n_gaps == 0 and n_ideas == 0 and n_proposals == 0:
            # Pipeline ran but produced nothing — mark as failed, not completed
            logger.warning(
                "Pipeline produced 0 gaps, 0 ideas, 0 proposals — marking as failed"
            )
            self._persistence.mark_run_failed(
                db_run_id,
                "Pipeline completed without producing any gaps, ideas, or proposals",
            )
        else:
            self._persistence.mark_run_completed(db_run_id)

        # Run completed notification
        if self._notifier:
            try:
                from backend.pipeline.notifications.gateway import Notification, PipelineEvent
                n_gaps = len(result.gaps) if result.gaps else 0
                n_ideas = len(result.ideas) if result.ideas else 0
                n_proposals = len(result.proposals) if result.proposals else 0
                await self._notifier.send(Notification(
                    event=PipelineEvent.RUN_COMPLETED,
                    run_id=run_id, strategy=strategy, domain=domain,
                    message=f"Pipeline completed: {n_gaps} gaps, {n_ideas} ideas, {n_proposals} proposals",
                    data={"gaps": n_gaps, "ideas": n_ideas, "proposals": n_proposals},
                ))
            except Exception:
                pass

        # Persist cost events
        if self._cost_tracker and self._cost_tracker._events:
            cost_dir = getattr(self._settings, "cost_persist_dir", "./data/costs")
            self._cost_tracker.persist(f"{cost_dir}/{run_id}.jsonl")

        # Session: complete run record
        if session_id and self._services.session_manager:
            tokens = self._cost_tracker.total_tokens if self._cost_tracker else 0
            cost = self._cost_tracker.total_cost if self._cost_tracker else 0.0
            self._services.session_manager.complete_run(
                session_id, run_id, tokens_used=tokens, cost_usd=cost
            )

        # Journal at pipeline end
        if self._integration:
            self._integration.journal_note(
                "pipeline", "Pipeline completed",
                {"ideas": len(result.ideas), "gaps": len(result.gaps)},
            )
            notes_path, readme_path = self._integration.journal_write()
            if notes_path:
                logger.info("Research journal written to %s", notes_path)

        # Phase 5: Durable run artifact export
        if getattr(self._settings, "run_artifacts_enabled", True):
            try:
                from backend.pipeline.export.run_artifacts import RunArtifactExporter
                artifact_exporter = RunArtifactExporter(
                    output_root=getattr(self._settings, "run_artifacts_dir", "./data/runs")
                )
                run_dir = await artifact_exporter.export_run(
                    run_id=run_id,
                    result=result,
                    ctx=ctx,
                    params=params,
                    domain=domain,
                    strategy=strategy,
                )
                logger.info("Run artifacts exported to %s", run_dir)
            except Exception as e:
                logger.warning("Run artifact export failed (non-fatal): %s", str(e)[:200])
