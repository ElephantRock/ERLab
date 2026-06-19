"""Ideas API routes."""

import json

from fastapi import APIRouter, Query
from sqlalchemy import select

from backend.api.errors import APIError, NotFoundError
from backend.api.schemas import IdeaFeedbackRequest
from backend.api.traceability import resolve_source_gaps, extract_proposal_references
from backend.api.quality_checks import compute_quality_checks, compute_remediation_hints, audit_citations
from backend.pipeline.provenance.reference_resolver import resolve_references

router = APIRouter()


def _parse_source_gap_ids(raw: str | None) -> list[str] | None:
    """Safely parse source_gap_ids from DB.
    
    Handles three storage formats:
    - None/empty → None
    - JSON array string → parsed list
    - Raw hash string (pre-migration) → [raw]
    """
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
        return [str(parsed)]
    except (json.JSONDecodeError, TypeError):
        return [raw]


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

    from backend.db.models import GovernanceDecision, IdeaPaperLink, Proposal
    from sqlalchemy import func as sa_func

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

        idea_ids = [i.id for i in ideas]

        # Batch: latest governance decision per idea
        gov_status: dict[int, str | None] = {iid: None for iid in idea_ids}
        if idea_ids:
            # Subquery: latest decision per idea
            gov_subq = (
                select(
                    GovernanceDecision.idea_id,
                    GovernanceDecision.decision,
                    sa_func.max(GovernanceDecision.created_at).label("max_created"),
                )
                .where(GovernanceDecision.idea_id.in_(idea_ids))
                .group_by(GovernanceDecision.idea_id, GovernanceDecision.decision)
                .subquery()
            )
            # Get the actual latest decision per idea
            gov_rows = session.execute(
                select(GovernanceDecision.idea_id, GovernanceDecision.decision)
                .where(GovernanceDecision.idea_id.in_(idea_ids))
                .order_by(GovernanceDecision.idea_id, GovernanceDecision.created_at.desc())
            ).all()
            seen = set()
            for gid, gdecision in gov_rows:
                if gid not in seen:
                    gov_status[gid] = gdecision
                    seen.add(gid)

        # Batch: paper link counts per idea, split by role
        cited_counts: dict[int, int] = {iid: 0 for iid in idea_ids}
        supporting_counts: dict[int, int] = {iid: 0 for iid in idea_ids}
        if idea_ids:
            link_rows = session.execute(
                select(IdeaPaperLink.idea_id, IdeaPaperLink.role, sa_func.count(IdeaPaperLink.id))
                .where(IdeaPaperLink.idea_id.in_(idea_ids))
                .group_by(IdeaPaperLink.idea_id, IdeaPaperLink.role)
            ).all()
            for lid, lrole, lcount in link_rows:
                if lrole == "cited":
                    cited_counts[lid] = lcount
                elif lrole == "supporting":
                    supporting_counts[lid] = lcount

        # Batch: quality pass rate per idea from proposal sections_json
        quality_summary: dict[int, dict] = {iid: {} for iid in idea_ids}
        if idea_ids:
            prop_rows = session.execute(
                select(Proposal.idea_id, Proposal.sections_json)
                .where(Proposal.idea_id.in_(idea_ids))
            ).all()
            for pid, psections_json in prop_rows:
                sections = None
                if psections_json:
                    try:
                        sections = json.loads(psections_json)
                    except (json.JSONDecodeError, TypeError):
                        pass
                checks = compute_quality_checks(sections)
                if checks:
                    passed = sum(1 for c in checks if c.get("passed"))
                    quality_summary[pid] = {
                        "passed": passed,
                        "total": len(checks),
                        "has_issues": passed < len(checks),
                    }

        return {
            "ideas": [
                {
                    "id": i.id,
                    "title": i.title,
                    "domain": i.domain,
                    "novelty_score": i.novelty_score,
                    "feasibility_score": i.feasibility_score,
                    "overall_score": i.overall_score,
                    "source_gap_ids": _parse_source_gap_ids(i.source_gap_ids),
                    "has_proposal": i.proposal is not None,
                    "pipeline_run_id": i.pipeline_run_id,
                    "created_at": str(i.created_at),
                    "quality_summary": quality_summary.get(i.id, {}),
                    "governance_status": gov_status.get(i.id),
                    "reference_count": cited_counts.get(i.id, 0) + supporting_counts.get(i.id, 0),
                    "cited_count": cited_counts.get(i.id, 0),
                    "supporting_count": supporting_counts.get(i.id, 0),
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

        # Resolve source_gap_ids (titles, gap IDs, or idempotency keys) to real gap records
        try:
            raw_gap_ids = json.loads(idea.source_gap_ids) if idea.source_gap_ids else []
        except (json.JSONDecodeError, TypeError):
            # source_gap_ids is a raw idempotency hash, not JSON
            raw_gap_ids = [idea.source_gap_ids] if idea.source_gap_ids else []
        if not isinstance(raw_gap_ids, list):
            raw_gap_ids = [str(raw_gap_ids)]
        source_gaps = resolve_source_gaps(session, raw_gap_ids, idea.pipeline_run_id)

        # Extract structured proposal references — try new resolver first
        proposal_references = None
        if proposal:
            raw_refs = extract_proposal_references(proposal)
            if raw_refs:
                # Use the domain-layer resolver for structured matching
                resolved = resolve_references(raw_refs, session, idea.pipeline_run_id)
                proposal_references = [
                    {
                        "raw": r.raw,
                        "number": r.number,
                        "authors": r.authors,
                        "year": r.year,
                        "title": r.title,
                        "venue": r.venue,
                        "resolved": r.resolved,
                        "paper": r.paper,
                        "match_method": r.match_method,
                        "match_confidence": r.match_confidence,
                    }
                    for r in resolved
                ]

        # Fetch supporting papers via junction table (schema-backed provenance)
        from backend.db.models import IdeaPaperLink, Paper as PaperModel
        supporting_papers_raw = session.execute(
            select(IdeaPaperLink).where(IdeaPaperLink.idea_id == idea.id)
        ).scalars().all()
        supporting_papers = None
        if supporting_papers_raw:
            enriched = []
            for link in supporting_papers_raw:
                paper = session.get(PaperModel, link.paper_id)
                if paper:
                    enriched.append({
                        "id": paper.id,
                        "title": paper.title,
                        "year": paper.year,
                        "venue": paper.venue,
                        "citation_count": paper.citation_count,
                        "doi": paper.doi,
                        "arxiv_id": paper.arxiv_id,
                        "url": paper.url,
                        "role": link.role,
                    })
            if enriched:
                supporting_papers = enriched

        # Compute sections dict once for reuse
        sections_dict = (
            json.loads(proposal.sections_json)
            if proposal and proposal.sections_json
            else None
        )
        quality_checks = compute_quality_checks(sections_dict)

        # Pre-compute per-section content hashes for optimistic concurrency
        section_hashes = None
        if sections_dict:
            import hashlib as _hashlib
            section_hashes = {
                k: _hashlib.sha256(v.encode()).hexdigest()
                for k, v in sections_dict.items()
                if isinstance(v, str)
            }

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
                "proposal_sections": sections_dict,
                "proposal_references": proposal_references,
                "supporting_papers": supporting_papers,
                "quality_checks": quality_checks,
                "section_hashes": section_hashes,
                "remediation_hints": compute_remediation_hints(sections_dict, quality_checks),
                "citation_audit": audit_citations(sections_dict, proposal_references),
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


# --------------------------------------------------------------------------- #
# Section refinement (Release 2) — revision-tracked mutations
# --------------------------------------------------------------------------- #

from pydantic import BaseModel


class SectionRefineRequest(BaseModel):
    expected_current_hash: str
    trigger_detail: dict | None = None


class SectionRestoreRequest(BaseModel):
    expected_current_hash: str


@router.post(
    "/{idea_id}/sections/{section_key}/refine",
    summary="Refine a single proposal section via LLM",
    description="Regenerate a specific proposal section with full revision tracking.",
)
async def refine_section(
    idea_id: int,
    section_key: str,
    request: SectionRefineRequest,
):
    """Regenerate a single proposal section.

    Creates a new revision with the old text preserved. Requires
    expected_current_hash for optimistic concurrency.
    """
    from backend.db.crud import get_idea as db_get_idea
    from backend.db.crud import get_proposal_by_idea
    from backend.db.database import get_session
    from backend.pipeline.synthesis.section_refinement import (
        ProposalSectionRefinementService,
        ConcurrencyConflict,
        ReceiptRequired,
    )
    from backend.pipeline.synthesis.proposal_synthesizer import ProposalSynthesizer, MIN_WORDS
    from backend.pipeline.generation.models import ResearchIdea
    from backend.providers.provider_factory import create_provider

    if section_key not in MIN_WORDS:
        raise APIError(
            400, "INVALID_SECTION",
            f"Section '{section_key}' is not refinable.",
            f"Allowed: {list(MIN_WORDS.keys())}",
        )

    with get_session() as session:
        idea = db_get_idea(session, idea_id)
        if not idea:
            raise NotFoundError("Idea not found")
        proposal = get_proposal_by_idea(session, idea.id)
        if not proposal:
            raise NotFoundError("No proposal found for this idea")

        sections = json.loads(proposal.sections_json) if proposal.sections_json else {}
        if section_key not in sections:
            raise NotFoundError(f"Section '{section_key}' not found")

        try:
            provider = create_provider()
            synthesizer = ProposalSynthesizer(provider)
            service = ProposalSectionRefinementService(synthesizer)

            research_idea = ResearchIdea(
                title=idea.title,
                problem_statement=idea.problem_statement,
                proposed_method=idea.proposed_method,
                expected_contributions=idea.expected_contributions,
                novelty_rationale="",
                evaluation_approach="",
            )

            result = await service.refine_section(
                session=session,
                proposal=proposal,
                section_key=section_key,
                idea=research_idea,
                expected_current_hash=request.expected_current_hash,
                trigger_detail=request.trigger_detail,
                provider=provider,
            )

            return {
                "revision_id": result.revision_id,
                "section_key": result.section_key,
                "previous_hash": result.previous_hash,
                "section_hash": result.section_hash,
                "quality_checks_before": result.quality_checks_before,
                "quality_checks_after": result.quality_checks_after,
                "model_receipt": result.model_receipt,
            }
        except ConcurrencyConflict as e:
            raise APIError(409, "CONFLICT", str(e), "The section was modified. Refresh and try again.")
        except ReceiptRequired as e:
            raise APIError(422, "RECEIPT_REQUIRED", str(e), "Use a provider that produces model receipts.")


@router.post(
    "/{idea_id}/sections/{section_key}/restore/{revision_id}",
    summary="Restore a section to a previous revision",
    description="Rolls back a section to the text captured in a specific revision.",
)
async def restore_section(
    idea_id: int,
    section_key: str,
    revision_id: int,
    request: SectionRestoreRequest,
):
    """Restore a section to a previous revision's text."""
    from backend.db.crud import get_idea as db_get_idea
    from backend.db.crud import get_proposal_by_idea
    from backend.db.database import get_session
    from backend.pipeline.synthesis.section_refinement import (
        ProposalSectionRefinementService,
        ConcurrencyConflict,
    )

    with get_session() as session:
        idea = db_get_idea(session, idea_id)
        if not idea:
            raise NotFoundError("Idea not found")
        proposal = get_proposal_by_idea(session, idea.id)
        if not proposal:
            raise NotFoundError("No proposal found for this idea")

        try:
            service = ProposalSectionRefinementService.__new__(ProposalSectionRefinementService)
            result = await service.restore_version(
                session=session,
                proposal=proposal,
                section_key=section_key,
                target_revision_id=revision_id,
                expected_current_hash=request.expected_current_hash,
            )

            return {
                "revision_id": result.revision_id,
                "section_key": result.section_key,
                "previous_hash": result.previous_hash,
                "section_hash": result.section_hash,
                "quality_checks_before": result.quality_checks_before,
                "quality_checks_after": result.quality_checks_after,
                "model_receipt": result.model_receipt,
            }
        except ConcurrencyConflict as e:
            raise APIError(409, "CONFLICT", str(e), "The section was modified. Refresh and try again.")


@router.get(
    "/{idea_id}/sections/{section_key}/revisions",
    summary="Get revision history for a section",
    description="Returns all revisions plus a synthetic original entry.",
)
async def get_section_revisions(idea_id: int, section_key: str):
    """Get revision history for a proposal section."""
    import hashlib
    from backend.db.crud import get_idea as db_get_idea
    from backend.db.crud import get_proposal_by_idea
    from backend.db.database import get_session
    from backend.db.models import ProposalSectionRevision
    from backend.pipeline.synthesis.proposal_synthesizer import MIN_WORDS
    from backend.api.quality_checks import compute_quality_checks

    with get_session() as session:
        idea = db_get_idea(session, idea_id)
        if not idea:
            raise NotFoundError("Idea not found")
        proposal = get_proposal_by_idea(session, idea.id)
        if not proposal:
            raise NotFoundError("No proposal found for this idea")

        sections = json.loads(proposal.sections_json) if proposal.sections_json else {}
        current_text = sections.get(section_key, "")
        current_hash = hashlib.sha256(current_text.encode()).hexdigest()

        revisions_raw = session.execute(
            select(ProposalSectionRevision)
            .where(
                ProposalSectionRevision.proposal_id == proposal.id,
                ProposalSectionRevision.section_key == section_key,
            )
            .order_by(ProposalSectionRevision.created_at.desc())
        ).scalars().all()

        def _summarize(qc_list):
            if not qc_list:
                return None
            c = qc_list[0]
            return {
                "section": c.get("section"),
                "passed": c.get("passed"),
                "word_count": c.get("word_count"),
                "min_words": c.get("min_words"),
                "failures": c.get("failures", []),
            }

        revisions = []
        for rev in revisions_raw:
            revisions.append({
                "id": rev.id,
                "source": rev.source,
                "trigger": rev.trigger,
                "trigger_detail": json.loads(rev.trigger_detail) if rev.trigger_detail else None,
                "section_hash": rev.section_hash,
                "model_receipt": json.loads(rev.model_receipt_json) if rev.model_receipt_json else None,
                "quality_summary": _summarize(json.loads(rev.quality_checks_json) if rev.quality_checks_json else []),
                "created_at": str(rev.created_at),
                "is_current": rev.section_hash == current_hash,
            })

        # Synthetic original
        synthetic_original = None
        if not revisions:
            qc = compute_quality_checks({section_key: current_text}) or []
            synthetic_original = {
                "source": "pipeline",
                "section_hash": current_hash,
                "quality_summary": _summarize(qc),
                "note": "Original pipeline output (current sections_json)",
            }
        elif revisions_raw:
            earliest = revisions_raw[-1]
            if earliest.previous_text:
                eh = hashlib.sha256(earliest.previous_text.encode()).hexdigest()
                qc = compute_quality_checks({section_key: earliest.previous_text}) or []
                synthetic_original = {
                    "source": "pipeline",
                    "section_hash": eh,
                    "quality_summary": _summarize(qc),
                    "note": "Original pipeline output (earliest revision previous_text)",
                }
            else:
                synthetic_original = {
                    "source": "pipeline",
                    "section_hash": None,
                    "quality_summary": None,
                    "note": "Original unavailable (no previous_text captured)",
                }

        return {
            "revisions": revisions,
            "synthetic_original": synthetic_original,
            "current_hash": current_hash,
        }


@router.post(
    "/{idea_id}/backfill-citations",
    summary="Backfill cited paper links from proposal references",
    description=(
        "Resolves the proposal's reference list against the Paper table and "
        "creates IdeaPaperLink rows with role='cited'. Idempotent via unique constraint."
    ),
)
async def backfill_citations(idea_id: int):
    """Backfill cited paper links for a single idea.

    Parses the proposal's ``references_json``, resolves each reference against
    the Paper table using DOI/arXiv/title matching, and persists matched papers
    as ``IdeaPaperLink`` rows with ``role='cited'``.

    Idempotent: existing links are skipped.
    """
    from backend.db.database import get_session
    from backend.pipeline.provenance.backfill import backfill_cited_links_for_idea

    with get_session() as session:
        result = backfill_cited_links_for_idea(session, idea_id)
        return {
            "idea_id": result.idea_id,
            "total_references": result.total_refs,
            "resolved": result.resolved,
            "new_links": result.new_links,
            "skipped_existing": result.skipped_existing,
            "unresolved": result.unresolved,
        }


@router.post(
    "/backfill-citations/all",
    summary="Backfill cited paper links for all ideas",
    description=(
        "Runs citation backfill for every idea that has a proposal. "
        "Useful for one-time migration of existing data."
    ),
)
async def backfill_all_citations():
    """Backfill cited paper links for all ideas with proposals."""
    from backend.db.database import get_session
    from backend.pipeline.provenance.backfill import backfill_cited_links_for_all_ideas

    with get_session() as session:
        results = backfill_cited_links_for_all_ideas(session)
        total_new = sum(r.new_links for r in results)
        total_resolved = sum(r.resolved for r in results)
        total_unresolved = sum(r.unresolved for r in results)
        return {
            "ideas_processed": len(results),
            "total_new_links": total_new,
            "total_resolved": total_resolved,
            "total_unresolved": total_unresolved,
            "results": [
                {
                    "idea_id": r.idea_id,
                    "total_references": r.total_refs,
                    "resolved": r.resolved,
                    "new_links": r.new_links,
                    "skipped_existing": r.skipped_existing,
                    "unresolved": r.unresolved,
                }
                for r in results
            ],
        }
