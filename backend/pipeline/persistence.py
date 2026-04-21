"""Pipeline DB persistence operations."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_CHECKPOINT_DIR = Path("./data/checkpoints")


class PipelinePersistence:
    """Handles all database writes for pipeline runs."""

    def __init__(self):
        self.warnings: list[str] = []

    def get_warnings(self) -> list[str]:
        return self.warnings.copy()

    def create_run_record(self, domain: str, params: dict) -> int | None:
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
                    crud.create_gap(
                        session,
                        title=gap.title,
                        description=gap.description,
                        gap_type=gap.gap_type,
                        confidence=gap.confidence,
                        potential_impact=gap.potential_impact,
                        pipeline_run_id=db_run_id,
                    )
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
            from backend.db import crud
            from backend.db.database import get_session

            with get_session() as session:
                for i, idea in enumerate(result.ideas):
                    nov = result.novelty_reports.get(i)
                    feas = result.feasibility_reports.get(i)
                    db_idea = crud.create_idea(
                        session,
                        title=idea.title,
                        problem_statement=idea.problem_statement,
                        proposed_method=idea.proposed_method,
                        expected_contributions=idea.expected_contributions,
                        domain=idea.domain,
                        pipeline_run_id=db_run_id,
                    )
                    if nov or feas:
                        crud.update_idea_scores(
                            session,
                            db_idea.id,
                            novelty_score=nov.overall_score if nov else None,
                            feasibility_score=feas.overall_score if feas else None,
                            novelty_report=json.dumps(
                                {
                                    "method_novelty": nov.method_novelty,
                                    "problem_novelty": nov.problem_novelty,
                                    "domain_transfer": nov.domain_transfer,
                                    "combination_novelty": nov.combination_novelty,
                                    "novelty_arguments": nov.novelty_arguments,
                                }
                            )
                            if nov
                            else None,
                            feasibility_report=json.dumps(
                                {
                                    "data_availability": feas.data_availability,
                                    "computational_requirements": feas.computational_requirements,
                                    "methodological_complexity": feas.methodological_complexity,
                                    "evaluation_plan": feas.evaluation_plan,
                                    "reasoning": feas.reasoning,
                                    "estimated_timeline": feas.estimated_timeline,
                                }
                            )
                            if feas
                            else None,
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
                            )
                        ).scalar_one_or_none()
                        if db_idea_row:
                            sections_to_store = {
                                k: v for k, v in proposal.sections.items() if k != "validated_text"
                            }
                            crud.create_proposal(
                                session,
                                idea_id=db_idea_row.id,
                                content_md=proposal.to_markdown(),
                                references_json=json.dumps(proposal.sections.get("references", [])),
                                sections_json=json.dumps(sections_to_store),
                            )
        except Exception as e:
            logger.warning("Failed to persist proposals: %s", e)
            self.warnings.append(f"persist_proposals: {e}")

    def mark_run_failed(self, db_run_id: int | None, message: str) -> None:
        if not db_run_id:
            return
        try:
            from backend.db import crud
            from backend.db.database import get_session

            with get_session() as session:
                crud.update_pipeline_run(session, db_run_id, status="failed", error_message=message)
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
                crud.update_pipeline_run(session, db_run_id, status="completed")
        except Exception as e:
            logger.warning("Failed to mark DB run as completed: %s", e)
            self.warnings.append(f"mark_run_completed: {e}")

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
