"""Global search across all resources (BATCH-47)."""

from fastapi import APIRouter, Query

router = APIRouter()


@router.get(
    "/",
    summary="Global search",
    description="Search across ideas, gaps, papers, and runs (BATCH-47).",
)
async def global_search(
    q: str = Query(default="", description="Search query"),
    types: str = Query(default="ideas,gaps,papers,runs", description="Resource types to search"),
):
    from sqlalchemy import func, select as sa_select, or_
    from backend.db.database import get_session
    from backend.db.models import Idea, ResearchGapDB, Paper, PipelineRun

    if not q.strip():
        return {"query": q, "results": {}, "total": 0}

    requested_types = set(t.strip() for t in types.split(",") if t.strip())
    results = {}
    total = 0

    with get_session() as session:
        if "ideas" in requested_types:
            idea_rows = session.execute(
                sa_select(Idea).where(
                    or_(Idea.title.ilike(f"%{q}%"), Idea.problem_statement.ilike(f"%{q}%"))
                ).limit(10)
            ).scalars().all()
            results["ideas"] = {
                "total": len(idea_rows),
                "items": [{"id": i.id, "title": i.title, "domain": i.domain, "overall_score": i.overall_score} for i in idea_rows],
            }
            total += len(idea_rows)

        if "gaps" in requested_types:
            gap_rows = session.execute(
                sa_select(ResearchGapDB).where(
                    or_(ResearchGapDB.title.ilike(f"%{q}%"), ResearchGapDB.description.ilike(f"%{q}%"))
                ).limit(10)
            ).scalars().all()
            results["gaps"] = {
                "total": len(gap_rows),
                "items": [{"id": g.id, "title": g.title, "gap_type": g.gap_type, "confidence": g.confidence} for g in gap_rows],
            }
            total += len(gap_rows)

        if "papers" in requested_types:
            paper_rows = session.execute(
                sa_select(Paper).where(
                    or_(Paper.title.ilike(f"%{q}%"), Paper.abstract.ilike(f"%{q}%"))
                ).limit(10)
            ).scalars().all()
            results["papers"] = {
                "total": len(paper_rows),
                "items": [{"id": p.id, "title": p.title, "year": p.year, "venue": p.venue} for p in paper_rows],
            }
            total += len(paper_rows)

        if "runs" in requested_types:
            run_rows = session.execute(
                sa_select(PipelineRun).where(
                    or_(PipelineRun.domain.ilike(f"%{q}%"), PipelineRun.config_json.ilike(f"%{q}%"))
                ).limit(10)
            ).scalars().all()
            results["runs"] = {
                "total": len(run_rows),
                "items": [{"id": r.id, "status": r.status, "domain": r.domain, "created_at": str(r.created_at)} for r in run_rows],
            }
            total += len(run_rows)

    return {"query": q, "results": results, "total": total}


@router.get(
    "/knowledge/{domain}",
    summary="Query knowledge library",
    description="Get previously indexed papers, gaps, and ideas for a domain (B158).",
)
async def query_knowledge(domain: str):
    from backend.pipeline.knowledge.integration import KnowledgeIntegrationService
    service = KnowledgeIntegrationService()
    try:
        summary = service.query_existing_knowledge(domain)
        papers = service._indexer.get_existing_papers(domain, limit=20)
        gaps = service._indexer.get_existing_gaps(domain, limit=20)
        return {
            "domain": domain,
            "summary": summary,
            "papers": papers,
            "gaps": gaps,
        }
    except Exception as e:
        return {"domain": domain, "error": str(e), "papers": [], "gaps": []}
    finally:
        service.close()
