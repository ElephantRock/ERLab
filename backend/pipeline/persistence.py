"""Pipeline DB persistence operations."""

import json
import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CHECKPOINT_DIR = Path("./data/checkpoints")


def normalize_title(title: str) -> str:
    """Normalize a gap title for dedup hashing (BATCH-42, HB-02)."""
    t = title.lower()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def content_hash(title: str) -> str:
    """SHA-256 hash of normalized title (BATCH-42, HB-01)."""
    return hashlib.sha256(normalize_title(title).encode("utf-8")).hexdigest()


class PipelinePersistence:
    """Handles all database writes for pipeline runs."""

    def __init__(self):
        self.warnings: list[str] = []

    def get_warnings(self) -> list[str]:
        return self.warnings.copy()

    def create_run_record(self, domain: str, params: dict, session_id: str | None = None) -> int | None:
        try:
            from backend.db import crud
            from backend.db.database import get_session

            with get_session() as session:
                db_run = crud.create_pipeline_run(
                    session,
                    domain=domain,
                    status="running",
                    current_stage="initializing",
                    config_json=json.dumps(params),
                    session_id=session_id,
                )
                return db_run.id
        except Exception as e:
            logger.warning("Failed to create DB run record: %s", e)
            self.warnings.append(f"create_run_record: {e}")
            return None

    def persist_gaps(self, result, db_run_id: int | None) -> None:
        if not db_run_id or not result.gaps:
            return
        try:
            from backend.db import crud
            from backend.db.database import get_session

            with get_session() as session:
                for gap in result.gaps:
                    gap_kwargs = {
                        "title": gap.title,
                        "description": gap.description,
                        "gap_type": gap.gap_type,
                        "confidence": gap.confidence,
                        "potential_impact": gap.potential_impact,
                        "pipeline_run_id": db_run_id,
                    }
                    # Write truth value columns when present (BATCH-38)
                    if hasattr(gap, "truth") and gap.truth is not None:
                        gap_kwargs["truth_frequency"] = gap.truth.frequency
                        gap_kwargs["truth_confidence"] = gap.truth.confidence
                        gap_kwargs["truth_evidence_count"] = gap.truth.evidence_count
                    # Write related_clusters as JSON array (BATCH-38)
                    if hasattr(gap, "related_clusters") and gap.related_clusters:
                        gap_kwargs["related_clusters"] = json.dumps(gap.related_clusters)
                    # Deduplication: check content_hash (BATCH-42)
                    c_hash = content_hash(gap.title)
                    existing = crud.find_gap_by_hash(session, c_hash)
                    if existing:
                        # Revise truth values using OpenNARS rule (HB-03)
                        from backend.pipeline.knowledge.truth import TruthValue
                        new_truth = TruthValue.from_observation(frequency=gap.confidence)
                        if hasattr(gap, "truth") and gap.truth is not None:
                            new_truth = gap.truth
                        revised = TruthValue(
                            frequency=existing.truth_frequency,
                            confidence=existing.truth_confidence,
                            evidence_count=existing.truth_evidence_count,
                        ).revise(new_truth)
                        existing.truth_frequency = revised.frequency
                        existing.truth_confidence = revised.confidence
                        existing.truth_evidence_count = revised.evidence_count
                        session.commit()
                        logger.info("Revised truth for duplicate gap: %s (hash=%s)", gap.title[:50], c_hash[:12])
                        continue
                    gap_kwargs["content_hash"] = c_hash
                    gap_kwargs["canonical_id"] = c_hash  # First occurrence is canonical
                    crud.create_gap(session, **gap_kwargs)
        except Exception as e:
            logger.warning("Failed to persist gaps: %s", e)
            self.warnings.append(f"persist_gaps: {e}")

    def persist_papers(self, papers: list, db_run_id: int | None) -> None:
        if not db_run_id:
            return
        try:
            from backend.db import crud
            from backend.db.database import get_session

            with get_session() as session:
                for paper in papers:
                    if not crud.get_paper_by_source_id(session, paper.id):
                        crud.create_paper(
                            session,
                            source_id=paper.id,
                            source=paper.source,
                            title=paper.title,
                            abstract=paper.abstract,
                            authors=json.dumps([a.name for a in paper.authors])
                            if paper.authors
                            else "[]",
                            year=paper.year,
                            venue=paper.venue,
                            citation_count=paper.citation_count,
                            url=paper.url,
                            doi=paper.doi,
                            arxiv_id=paper.arxiv_id,
                            keywords=json.dumps(paper.keywords) if paper.keywords else "[]",
                        )
        except Exception as e:
            logger.warning("Failed to persist papers: %s", e)
            self.warnings.append(f"persist_papers: {e}")

    def persist_ideas(self, result, db_run_id: int | None) -> None:
        if not db_run_id or not result.ideas:
            return
        try:
            from sqlalchemy import select

            from backend.db import crud
            from backend.db.database import get_session
            from backend.db.models import Idea as IdeaModel

            with get_session() as session:
                for i, idea in enumerate(result.ideas):
                    # Dedup check: skip if idea with same (title, pipeline_run_id) already exists (BATCH-75, HB-03)
                    existing = session.execute(
                        select(IdeaModel).where(
                            IdeaModel.title == idea.title,
                            IdeaModel.pipeline_run_id == db_run_id,
                        ).limit(1)
                    ).scalar_one_or_none()
                    nov = result.novelty_reports.get(i)
                    feas = result.feasibility_reports.get(i)

                    if existing:
                        # Idea already persisted (e.g., after idea_generation).
                        # If novelty/feasibility data is now available, update scores.
                        if nov or feas:
                            nov_dict = None
                            if nov:
                                nov_dict = {
                                    "method_novelty": nov.method_novelty,
                                    "problem_novelty": nov.problem_novelty,
                                    "domain_transfer": nov.domain_transfer,
                                    "combination_novelty": nov.combination_novelty,
                                    "novelty_arguments": nov.novelty_arguments,
                                }
                            mech = result.mechanical_metrics.get(i)
                            if mech and nov_dict is not None:
                                nov_dict["mechanical_metrics"] = mech
                            elif mech and nov_dict is None:
                                nov_dict = {"mechanical_metrics": mech, "overall_score": None}

                            feas_dict = None
                            if feas:
                                feas_dict = {
                                    "data_availability": feas.data_availability,
                                    "computational_requirements": feas.computational_requirements,
                                    "methodological_complexity": feas.methodological_complexity,
                                    "evaluation_plan": feas.evaluation_plan,
                                    "reasoning": feas.reasoning,
                                    "estimated_timeline": feas.estimated_timeline,
                                }

                            crud.update_idea_scores(
                                session,
                                existing.id,
                                novelty_score=nov.overall_score if nov else None,
                                feasibility_score=feas.overall_score if feas else None,
                                novelty_report=json.dumps(nov_dict) if nov_dict else None,
                                feasibility_report=json.dumps(feas_dict) if feas_dict else None,
                            )
                            logger.info(
                                "Updated scores for idea '%s' (run_id=%s)",
                                idea.title[:50], db_run_id,
                            )
                        else:
                            logger.debug(
                                "Skipping duplicate idea (no new scores): '%s'",
                                idea.title[:50],
                            )
                        continue

                    # getattr guards for IdeaCandidate compatibility (BATCH-75, HB-02)
                    source_gap_ids_raw = getattr(idea, 'source_gap_ids', None)
                    # novelty_rationale is guarded via getattr even though not persisted yet
                    getattr(idea, 'novelty_rationale', '')

                    db_idea = crud.create_idea(
                        session,
                        title=idea.title,
                        problem_statement=idea.problem_statement,
                        proposed_method=idea.proposed_method,
                        expected_contributions=getattr(idea, 'expected_contributions', ''),
                        domain=getattr(idea, 'domain', 'AI/NLP'),
                        source_gap_ids=json.dumps(source_gap_ids_raw) if source_gap_ids_raw else None,
                        pipeline_run_id=db_run_id,
                    )
                    if nov or feas:
                        # Build novelty report dict
                        nov_dict = None
                        if nov:
                            nov_dict = {
                                "method_novelty": nov.method_novelty,
                                "problem_novelty": nov.problem_novelty,
                                "domain_transfer": nov.domain_transfer,
                                "combination_novelty": nov.combination_novelty,
                                "novelty_arguments": nov.novelty_arguments,
                            }
                        # Merge mechanical metrics into novelty report (BATCH-64)
                        mech = result.mechanical_metrics.get(i)
                        if mech and nov_dict is not None:
                            nov_dict["mechanical_metrics"] = mech
                        elif mech and nov_dict is None:
                            nov_dict = {"mechanical_metrics": mech, "overall_score": None}

                        feas_dict = None
                        if feas:
                            feas_dict = {
                                "data_availability": feas.data_availability,
                                "computational_requirements": feas.computational_requirements,
                                "methodological_complexity": feas.methodological_complexity,
                                "evaluation_plan": feas.evaluation_plan,
                                "reasoning": feas.reasoning,
                                "estimated_timeline": feas.estimated_timeline,
                            }

                        crud.update_idea_scores(
                            session,
                            db_idea.id,
                            novelty_score=nov.overall_score if nov else None,
                            feasibility_score=feas.overall_score if feas else None,
                            novelty_report=json.dumps(nov_dict) if nov_dict else None,
                            feasibility_report=json.dumps(feas_dict) if feas_dict else None,
                        )
        except Exception as e:
            logger.warning("Failed to persist ideas: %s", e)
            self.warnings.append(f"persist_ideas: {e}")

    def persist_proposals(self, result, db_run_id: int | None) -> None:
        if not db_run_id or not result.proposals:
            return
        try:
            from sqlalchemy import select

            from backend.db import crud
            from backend.db.database import get_session
            from backend.db.models import Idea

            with get_session() as session:
                for i, proposal in result.proposals.items():
                    idea = result.ideas[i] if i < len(result.ideas) else None
                    if idea:
                        db_idea_row = session.execute(
                            select(Idea).where(
                                Idea.title == idea.title,
                                Idea.pipeline_run_id == db_run_id,
                            ).limit(1)
                        ).scalar_one_or_none()
                        if db_idea_row:
                            # Filter out non-serializable values (e.g., EnsembleReviewResult)
                            sections_to_store = {}
                            for k, v in proposal.sections.items():
                                if k == "validated_text":
                                    continue
                                if isinstance(v, (str, list, dict, int, float, bool, type(None))):
                                    sections_to_store[k] = v
                                elif hasattr(v, "model_dump"):
                                    sections_to_store[k] = v.model_dump()
                                elif hasattr(v, "__dict__"):
                                    sections_to_store[k] = str(v)

                            refs = proposal.sections.get("references", [])
                            if not isinstance(refs, (list, dict, str)):
                                refs = str(refs)

                            crud.create_proposal(
                                session,
                                idea_id=db_idea_row.id,
                                content_md=proposal.to_markdown(),
                                references_json=json.dumps(refs),
                                sections_json=json.dumps(sections_to_store),
                            )
        except Exception as e:
            logger.warning("Failed to persist proposals: %s", e)
            self.warnings.append(f"persist_proposals: {e}")

    def persist_cluster_report(self, cluster_report, db_run_id: int | None) -> None:
        """Write cluster_report_json to PipelineRun (BATCH-38)."""
        if not db_run_id:
            return
        try:
            from backend.db.database import get_session
            from backend.db.models import PipelineRun as PipelineRunModel
            from sqlalchemy import select

            report_data = cluster_report
            if hasattr(cluster_report, "model_dump"):
                report_data = cluster_report.model_dump()
            report_json = json.dumps(report_data)

            with get_session() as session:
                run = session.get(PipelineRunModel, db_run_id)
                if run:
                    run.cluster_report_json = report_json
                    session.commit()
        except Exception as e:
            logger.warning("Failed to persist cluster report: %s", e)
            self.warnings.append(f"persist_cluster_report: {e}")

    def persist_tree_data(self, tree_data: dict | None, db_run_id: int | None) -> None:
        """Write tree_data_json to PipelineRun (BATCH-63)."""
        if not db_run_id or not tree_data:
            return
        try:
            from backend.db.database import get_session
            from backend.db.models import PipelineRun as PipelineRunModel

            report_json = json.dumps(tree_data, default=str)

            with get_session() as session:
                run = session.get(PipelineRunModel, db_run_id)
                if run:
                    run.tree_data_json = report_json
                    session.commit()
        except Exception as e:
            logger.warning("Failed to persist tree data: %s", e)
            self.warnings.append(f"persist_tree_data: {e}")

    def advance_stage(self, run_id: int, stage_name: str) -> None:
        """Update the current stage, append to stages_completed, and update updated_at."""
        try:
            from backend.db.database import get_session
            from backend.db.models import PipelineRun

            with get_session() as session:
                run = session.query(PipelineRun).filter(PipelineRun.id == run_id).first()
                if run:
                    run.current_stage = stage_name
                    stages = json.loads(run.stages_completed) if run.stages_completed else []
                    if stage_name not in stages:
                        stages.append(stage_name)
                    run.stages_completed = json.dumps(stages)
                    run.updated_at = datetime.now(timezone.utc)
                    session.commit()
        except Exception as e:
            logger.warning("Failed to advance stage: %s", e)
            self.warnings.append(f"advance_stage: {e}")

    def mark_run_failed(self, db_run_id: int | None, message: str) -> None:
        if not db_run_id:
            return
        try:
            from backend.db import crud
            from backend.db.database import get_session

            with get_session() as session:
                crud.update_pipeline_run(
                    session, db_run_id,
                    status="failed",
                    current_stage="failed",
                    error_message=message,
                )
        except Exception as e:
            logger.warning("Failed to mark DB run as failed: %s", e)
            self.warnings.append(f"mark_run_failed: {e}")

    def mark_run_completed(self, db_run_id: int | None) -> None:
        if not db_run_id:
            return
        try:
            from backend.db import crud
            from backend.db.database import get_session

            with get_session() as session:
                crud.update_pipeline_run(
                    session, db_run_id,
                    status="completed",
                    current_stage="completed",
                )
        except Exception as e:
            logger.warning("Failed to mark DB run as completed: %s", e)
            self.warnings.append(f"mark_run_completed: {e}")

    def find_stale_runs(self, max_age: timedelta) -> list:
        """Find runs stuck in 'running' longer than max_age.

        Args:
            max_age: Maximum time a run should be in 'running' state.

        Returns:
            List of PipelineRun objects that are stale.
        """
        try:
            from backend.db.database import get_session
            from backend.db.models import PipelineRun

            cutoff = datetime.now(timezone.utc) - max_age
            with get_session() as session:
                # Check updated_at first (heartbeat-updated), fall back to created_at
                stale = session.query(PipelineRun).filter(
                    PipelineRun.status == "running",
                ).all()
                result = []
                for run in stale:
                    last_active = run.updated_at or run.created_at
                    if last_active:
                        # Handle both tz-aware and tz-naive datetimes
                        if last_active.tzinfo is None:
                            last_active = last_active.replace(tzinfo=timezone.utc)
                        if last_active < cutoff:
                            result.append(run)
                return result
        except Exception as e:
            logger.warning("Failed to find stale runs: %s", e)
            return []

    def mark_stale_run_failed(self, db_run_id: int, message: str) -> None:
        """Mark a single stale run as failed with a watchdog message."""
        try:
            from backend.db import crud
            from backend.db.database import get_session

            with get_session() as session:
                crud.update_pipeline_run(
                    session, db_run_id,
                    status="failed",
                    current_stage="failed",
                    error_message=message,
                )
        except Exception as e:
            logger.warning("Failed to mark stale run as failed: %s", e)

    # ── Checkpoint persistence (durable execution) ─────────────────

    def save_checkpoint(self, checkpoint: "RunCheckpoint") -> None:
        """Save a run checkpoint to disk."""
        try:
            _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
            path = _CHECKPOINT_DIR / f"{checkpoint.run_id}.json"
            path.write_text(checkpoint.to_json(), encoding="utf-8")
            logger.info("Checkpoint saved: %s", checkpoint.run_id)
        except Exception as e:
            logger.warning("Failed to save checkpoint: %s", e)
            self.warnings.append(f"save_checkpoint: {e}")

    def load_checkpoint(self, run_id: str) -> "RunCheckpoint | None":
        """Load a run checkpoint from disk."""
        try:
            path = _CHECKPOINT_DIR / f"{run_id}.json"
            if not path.exists():
                return None
            from backend.pipeline.execution.run_state import RunCheckpoint
            return RunCheckpoint.from_json(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Failed to load checkpoint for %s: %s", run_id, e)
            self.warnings.append(f"load_checkpoint: {e}")
            return None

    def list_checkpoints(self) -> list[dict]:
        """List all resumable checkpoints."""
        results = []
        if not _CHECKPOINT_DIR.exists():
            return results
        for path in _CHECKPOINT_DIR.glob("*.json"):
            try:
                from backend.pipeline.execution.run_state import RunCheckpoint
                cp = RunCheckpoint.from_json(path.read_text(encoding="utf-8"))
                results.append({
                    "run_id": cp.run_id,
                    "state": cp.state.value,
                    "completed_stages": sum(1 for s in cp.stages if s.status.value == "completed"),
                    "total_stages": len(cp.stages),
                })
            except Exception:
                pass
        return results

    # ---- State Reconstruction for Resume ----

    def get_run_by_uuid(self, run_id: str) -> Any | None:
        """Look up a PipelineRun by its UUID string."""
        from backend.db.crud import list_pipeline_runs
        from backend.db.database import get_session

        with get_session() as session:
            runs = list_pipeline_runs(session, limit=100)
            for run in runs:
                if str(run.id) == run_id or run_id.endswith(str(run.id)):
                    return run
        return None

    def load_gaps(self, run_db_id: int) -> list:
        """Load ResearchGap objects from database for a pipeline run."""
        from backend.db.crud import get_pipeline_run
        from backend.db.database import get_session
        from backend.pipeline.gap_analysis.models import ResearchGap
        from backend.pipeline.knowledge.truth import TruthValue

        with get_session() as session:
            run = get_pipeline_run(session, run_db_id)
            if not run:
                return []
            gaps = []
            for gap_db in getattr(run, "gaps", []):
                # Reconstruct TruthValue from persisted columns (BATCH-38)
                truth = TruthValue(
                    frequency=getattr(gap_db, "truth_frequency", 0.5),
                    confidence=getattr(gap_db, "truth_confidence", 0.5),
                    evidence_count=getattr(gap_db, "truth_evidence_count", 0),
                )
                # Parse related_clusters from JSON string (BATCH-38)
                related_clusters_raw = getattr(gap_db, "related_clusters", None)
                related_clusters = json.loads(related_clusters_raw) if related_clusters_raw else []

                gaps.append(ResearchGap(
                    title=gap_db.title,
                    description=gap_db.description,
                    gap_type=gap_db.gap_type,
                    confidence=gap_db.confidence,
                    potential_impact=getattr(gap_db, "potential_impact", ""),
                    truth=truth,
                    related_clusters=related_clusters,
                ))
            return gaps

    def load_ideas(self, run_db_id: int) -> list:
        """Load ResearchIdea objects from database for a pipeline run."""
        from backend.db.crud import get_pipeline_run
        from backend.db.database import get_session
        from backend.pipeline.generation.models import ResearchIdea

        with get_session() as session:
            run = get_pipeline_run(session, run_db_id)
            if not run:
                return []
            ideas = []
            for idea_db in getattr(run, "ideas", []):
                ideas.append(ResearchIdea(
                    title=idea_db.title,
                    problem_statement=getattr(idea_db, "problem_statement", ""),
                    proposed_method=getattr(idea_db, "proposed_method", ""),
                    domain=getattr(idea_db, "domain", "AI/NLP"),
                    score=getattr(idea_db, "overall_score", 0.0) or 0.0,
                ))
            return ideas
