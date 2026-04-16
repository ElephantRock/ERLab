"""Pipeline API routes."""

from fastapi import APIRouter

router = APIRouter()


@router.post("/run")
async def trigger_run(
    domain: str = "AI/NLP",
    max_gaps: int = 5,
    generation_rounds: int | None = None,
    ideas_per_round: int | None = None,
):
    """Trigger a new pipeline run."""
    from backend.pipeline.orchestrator import PipelineOrchestrator

    orchestrator = PipelineOrchestrator()
    result = await orchestrator.run(
        domain=domain,
        max_gaps=max_gaps,
        generation_rounds=generation_rounds,
        ideas_per_round=ideas_per_round,
    )
    return {
        "run_id": result.run_id,
        "ideas_count": len(result.ideas),
        "gaps_count": len(result.gaps),
        "top_ideas": [
            {"title": i.title, "score": i.score}
            for i in sorted(result.ideas, key=lambda x: x.score, reverse=True)[:5]
        ],
        "gaps": [
            {"title": g.title, "confidence": g.confidence}
            for g in result.gaps
        ],
    }


@router.get("/runs")
async def list_runs():
    """List pipeline runs (placeholder — requires DB integration)."""
    return {"runs": [], "message": "Requires DB integration (Gap 12)"}
