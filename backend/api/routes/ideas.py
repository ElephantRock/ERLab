"""Ideas API routes."""

import json

from fastapi import APIRouter, Query

from backend.api.errors import NotFoundError
from backend.api.schemas import IdeaFeedbackRequest

router = APIRouter()


@router.get("/")
async def list_ideas(
    domain: str | None = None,
    min_score: float = Query(default=0.0, ge=0.0, le=1.0),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List research ideas with optional filters."""
    from backend.db.crud import count_ideas, list_ideas as db_list_ideas
    from backend.db.database import get_session

    with get_session() as session:
        ideas = db_list_ideas(session, limit=limit, offset=offset, domain=domain, min_score=min_score)
        total = count_ideas(session, domain=domain, min_score=min_score)
        return {
            "ideas": [
                {
                    "id": i.id,
                    "title": i.title,
                    "domain": i.domain,
                    "novelty_score": i.novelty_score,
                    "feasibility_score": i.feasibility_score,
                    "overall_score": i.overall_score,
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


@router.get("/{idea_id}")
async def get_idea(idea_id: int):
    """Get a specific idea with novelty and feasibility reports."""
    from backend.db.crud import get_idea as db_get_idea
    from backend.db.crud import get_proposal_by_idea
    from backend.db.database import get_session

    with get_session() as session:
        idea = db_get_idea(session, idea_id)
        if not idea:
            raise NotFoundError("Idea not found")
        proposal = get_proposal_by_idea(session, idea.id)
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
                "novelty_report": json.loads(idea.novelty_report) if idea.novelty_report else None,
                "feasibility_report": json.loads(idea.feasibility_report)
                if idea.feasibility_report
                else None,
                "proposal_md": proposal.content_md if proposal else None,
                "proposal_latex": proposal.content_latex if proposal else None,
                "proposal_sections": (
                    json.loads(proposal.sections_json)
                    if proposal and proposal.sections_json
                    else None
                ),
                "created_at": str(idea.created_at),
            },
        }


@router.post("/{idea_id}/feedback")
async def submit_feedback(idea_id: int, request: IdeaFeedbackRequest):
    """Submit user feedback (rating + optional notes) for an idea."""
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


@router.post("/{idea_id}/refine")
async def refine_idea(idea_id: int):
    """Re-run novelty + feasibility + synthesis for a single idea."""
    from backend.db.crud import get_idea as db_get_idea
    from backend.db.crud import update_idea_scores
    from backend.db.database import get_session
    from backend.pipeline.feasibility.feasibility_scorer import FeasibilityScorer
    from backend.pipeline.generation.models import ResearchIdea
    from backend.pipeline.novelty.novelty_checker import NoveltyChecker
    from backend.pipeline.synthesis.proposal_synthesizer import ProposalSynthesizer
    from backend.providers.provider_factory import create_provider

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
        from backend.pipeline.knowledge.vector_store import VectorStore

        settings = get_settings()
        embedding_provider = create_embedding_provider(
            provider_name=settings.embedding_provider,
            model=settings.embedding_model,
            api_key=settings.openai_api_key,
            base_url=settings.ollama_base_url,
            dimension=settings.embedding_dimension or None,
        )
        store = VectorStore(settings.chroma_persist_dir, embedding_provider)

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

