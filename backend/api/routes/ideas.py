"""Ideas API routes."""

import json

from fastapi import APIRouter, Query
from sqlalchemy import select

from backend.api.errors import APIError, NotFoundError
from backend.api.schemas import IdeaFeedbackRequest
from backend.api.traceability import resolve_source_gaps, extract_proposal_references

router = APIRouter()


@router.get(
    "/",
    summary="List research ideas",
    description=(
        "List research ideas with optional domain, score, search, and sort filters. "
        "All filters are additive. search performs case-insensitive LIKE on title. "
        "sort_by accepts score/novelty/feasibility/date. Uses parameterized queries (HB-01)."
    ),
)
async def list_ideas(
    domain: str | None = None,
    min_score: float = Query(default=0.0, ge=0.0, le=1.0),
    search: str | None = Query(default=None, description="Full-text keyword search on title (parameterized)"),
    sort_by: str | None = Query(default=None, description="Sort field: score, novelty, feasibility, date"),
    sort_order: str = Query(default="desc", description="Sort direction: desc or asc"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List research ideas with optional filters.

    Args:
        domain: Optional domain filter (e.g. "AI/NLP").
        min_score: Minimum overall score threshold (0.0-1.0).
        search: Optional full-text keyword search on title (parameterized).
        sort_by: Optional sort field (score, novelty, feasibility, date).
        sort_order: Sort direction (desc or asc).
        limit: Maximum number of ideas to return.
        offset: Number of ideas to skip.

    Returns:
        {"ideas": [...], "total": 42, "score_guide": {...}}
    """
    from backend.db.crud import count_ideas, list_ideas as db_list_ideas
    from backend.db.database import get_session

    effective_min_score = min_score if min_score > 0 else None

    with get_session() as session:
        ideas = db_list_ideas(
            session,
            limit=limit,
            offset=offset,
            domain=domain,
            min_score=effective_min_score,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        total = count_ideas(session, domain=domain, min_score=effective_min_score, search=search)
        return {
            "ideas": [
                {
                    "id": i.id,
                    "title": i.title,
                    "domain": i.domain,
                    "novelty_score": i.novelty_score,
                    "feasibility_score": i.feasibility_score,
                    "overall_score": i.overall_score,
                    "source_gap_ids": json.loads(i.source_gap_ids) if i.source_gap_ids else None,
                    "has_proposal": i.proposal is not None,
                    "pipeline_run_id": i.pipeline_run_id,
                    "created_at": str(i.created_at),
                }
                for i in ideas
            ],
            "total": total,
            "score_guide": {
                "novelty": {
                    "0-0.3": "Low",
                    "0.3-0.6": "Moderate",
                    "0.6-0.8": "High",
                    "0.8-1.0": "Very High",
                },
                "feasibility": {
                    "0-3": "Difficult",
                    "3-6": "Moderate",
                    "6-8": "Feasible",
                    "8-10": "Very Feasible",
                },
            },
        }


@router.get(
    "/{idea_id}",
    summary="Get idea details",
    description="Get a specific research idea with full novelty report, feasibility report, and synthesized proposal.",
)
async def get_idea(idea_id: int):
    """Get a specific idea with novelty and feasibility reports.

    Args:
        idea_id: The database primary key of the idea.

    Returns:
        {"idea": {...}} with full idea details including reports and proposals.

    Example response:
        {"idea": {"id": 1, "title": "Novel Attention Mechanism", "problem_statement": "...", "proposed_method": "...", "expected_contributions": "...", "domain": "AI/NLP", "novelty_score": 0.85, "feasibility_score": 7.2, "overall_score": 0.78, "novelty_report": {"overall_score": 0.85}, "feasibility_report": {"overall_score": 7.2}, "proposal_md": "...", "proposal_latex": "...", "created_at": "2026-05-02T14:30:00"}}
    """
    from backend.db.crud import get_idea as db_get_idea
    from backend.db.crud import get_proposal_by_idea
    from backend.db.database import get_session

    with get_session() as session:
        idea = db_get_idea(session, idea_id)
        if not idea:
            raise NotFoundError("Idea not found")
        proposal = get_proposal_by_idea(session, idea.id)

        # Get experiment results (BATCH-66)
        from backend.db.models import ExperimentResult as ExperimentResultDB
        exp_results = session.execute(
            select(ExperimentResultDB).where(ExperimentResultDB.idea_id == idea.id)
        ).scalars().all()
        experiment_results = [
            {
                "id": r.id,
                "success": r.success,
                "exit_code": r.exit_code,
                "execution_time_seconds": r.execution_time_seconds,
                "stdout": r.stdout[:500] if r.stdout else None,
                "error": r.error,
                "created_at": str(r.created_at),
            }
            for r in exp_results
        ]

        # Extract mechanical_metrics from novelty_report JSON (BATCH-64)
        novelty_report_raw = json.loads(idea.novelty_report) if idea.novelty_report else None
        mechanical_metrics = None
        if isinstance(novelty_report_raw, dict):
            mechanical_metrics = novelty_report_raw.pop("mechanical_metrics", None)

        # Resolve source_gap_ids (titles or idempotency keys) to real gap records
        try:
            raw_gap_ids = json.loads(idea.source_gap_ids) if idea.source_gap_ids else []
        except (json.JSONDecodeError, TypeError):
            raw_gap_ids = []
        if not isinstance(raw_gap_ids, list):
            raw_gap_ids = []
        source_gaps = resolve_source_gaps(session, raw_gap_ids, idea.pipeline_run_id)

        # Extract structured proposal references
        proposal_references = None
        if proposal:
            proposal_references = extract_proposal_references(proposal)

        return {
            "idea": {
                "id": idea.id,
                "title": idea.title,
                "problem_statement": idea.problem_statement,
                "proposed_method": idea.proposed_method,
                "expected_contributions": idea.expected_contributions,
                "domain": idea.domain,
                "novelty_score": idea.novelty_score,
                "feasibility_score": idea.feasibility_score,
                "overall_score": idea.overall_score,
                "source_gap_ids": raw_gap_ids if raw_gap_ids else None,
                "source_gaps": source_gaps if source_gaps else None,
                "novelty_report": novelty_report_raw,
                "feasibility_report": json.loads(idea.feasibility_report)
                if idea.feasibility_report
                else None,
                "mechanical_metrics": mechanical_metrics,
                "proposal_md": proposal.content_md if proposal else None,
                "proposal_latex": proposal.content_latex if proposal else None,
                "proposal_sections": (
                    json.loads(proposal.sections_json)
                    if proposal and proposal.sections_json
                    else None
                ),
                "proposal_references": proposal_references,
                "experiment_results": experiment_results if experiment_results else None,
                "created_at": str(idea.created_at),
            },
        }


@router.post(
    "/{idea_id}/feedback",
    summary="Submit idea feedback",
    description="Submit user feedback (rating + optional notes) for a research idea.",
)
async def submit_feedback(idea_id: int, request: IdeaFeedbackRequest):
    """Submit user feedback for an idea.

    Args:
        idea_id: The database primary key of the idea.
        request: Feedback with rating (1-5) and optional notes.

    Example request:
        {"rating": 4, "notes": "Strong methodology, needs more evaluation detail"}

    Example response:
        {"id": 1, "user_rating": 4, "user_notes": "Strong methodology, needs more evaluation detail"}
    """
    from backend.db.crud import get_idea as db_get_idea
    from backend.db.crud import update_idea_feedback
    from backend.db.database import get_session

    with get_session() as session:
        idea = db_get_idea(session, idea_id)
        if not idea:
            raise NotFoundError("Idea not found")
        updated = update_idea_feedback(session, idea_id, request.rating, request.notes)
        return {
            "id": updated.id,
            "user_rating": updated.user_rating,
            "user_notes": updated.user_notes,
        }


@router.post(
    "/{idea_id}/refine",
    summary="Refine an idea",
    description="Re-run novelty checking, feasibility scoring, and proposal synthesis for a single idea.",
)
async def refine_idea(idea_id: int):
    """Re-run novelty + feasibility + synthesis for a single idea.

    Args:
        idea_id: The database primary key of the idea.

    Returns:
        Updated scores and proposal title.

    Example response:
        {"id": 1, "novelty_score": 0.88, "feasibility_score": 7.5, "proposal_title": "Improved Attention via Sparse Gating"}
    """
    import traceback
    from backend.db.crud import get_idea as db_get_idea
    from backend.db.crud import update_idea_scores
    from backend.db.database import get_session
    from backend.pipeline.feasibility.feasibility_scorer import FeasibilityScorer
    from backend.pipeline.generation.models import ResearchIdea
    from backend.pipeline.novelty.novelty_checker import NoveltyChecker
    from backend.pipeline.synthesis.proposal_synthesizer import ProposalSynthesizer
    from backend.providers.provider_factory import create_provider

    try:
        with get_session() as session:
            idea = db_get_idea(session, idea_id)
            if not idea:
                raise NotFoundError("Idea not found")

            provider = create_provider()
            research_idea = ResearchIdea(
                title=idea.title,
                problem_statement=idea.problem_statement,
                proposed_method=idea.proposed_method,
                expected_contributions=idea.expected_contributions,
                novelty_rationale="",
                evaluation_approach="",
            )

            from backend.config import get_settings
            from backend.pipeline.knowledge.embedding_providers import create_embedding_provider
            from backend.pipeline.knowledge.embedding_service import EmbeddingService
            from backend.pipeline.knowledge.vector_store import VectorStore

            settings = get_settings()
            embedding_provider = create_embedding_provider(
                provider_name=settings.embedding_provider,
                model=settings.embedding_model,
                api_key=settings.openai_api_key,
                base_url=settings.ollama_base_url,
                dimension=settings.embedding_dimension or None,
            )
            embedding_service = EmbeddingService(embedding_provider, expected_dimension=settings.embedding_dimension or 768)
            store = VectorStore(settings.chroma_persist_dir, embedding_service)

            novelty_checker = NoveltyChecker(provider, store)
            feasibility_scorer = FeasibilityScorer(provider)
            synthesizer = ProposalSynthesizer(provider)

            novelty_report = await novelty_checker.check_novelty(research_idea)
            feasibility_report = await feasibility_scorer.score_feasibility(
                research_idea, novelty_report
            )
            proposal = await synthesizer.synthesize(
                research_idea, novelty_report, feasibility_report
            )

            update_idea_scores(
                session,
            idea_id,
            novelty_score=novelty_report.overall_score,
            feasibility_score=feasibility_report.overall_score,
            novelty_report=json.dumps({"overall_score": novelty_report.overall_score}),
            feasibility_report=json.dumps({"overall_score": feasibility_report.overall_score}),
        )

            return {
                "id": idea_id,
                "novelty_score": novelty_report.overall_score,
                "feasibility_score": feasibility_report.overall_score,
                "proposal_title": proposal.title,
            }
    except Exception as e:
        traceback.print_exc()
        raise APIError(
            500,
            "INTERNAL_ERROR",
            f"Idea refinement failed: {str(e)}",
            "The LLM provider may be unavailable. Check provider connectivity.",
        )
