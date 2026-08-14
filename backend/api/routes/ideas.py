"""Ideas API routes."""

import json

from fastapi import APIRouter, Query
from sqlalchemy import select

from backend.api.errors import APIError, ConflictError, NotFoundError
from backend.api.quality_checks import (
    audit_citations,
    compute_quality_checks,
    compute_remediation_hints,
)
from backend.api.schemas import IdeaFeedbackRequest
from backend.api.traceability import extract_proposal_references, resolve_source_gaps
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


def _serialize_paper_state(proposal, idea) -> dict:
    """Phase 1 1C: serialize the persisted full-paper artifact + state.

    State machine: not_requested | pending | ready | failed.
      - not_requested: no proposal row yet, OR the run's strategy does not
        include paper synthesis (fast_scan / literature_review).
      - ready: paper_md persisted and non-empty.
      - failed: paper stage ran but produced an empty/explicitly-failed artifact
        (paper_meta_json.status == "failed").
      - pending: proposal exists, strategy includes paper synthesis, but no
        paper artifact persisted yet (run still in progress or stage not reached).

    Truth rule: an empty/placeholder paper is never reported as ready.
    """
    if proposal is None:
        # No proposal row yet. Shape-consistent with the ready/failed return so
        # the frontend always sees the same keys.
        return _paper_state_dict(
            status="pending" if _idea_run_includes_paper_stage(idea) else "not_requested",
            paper_md=None,
            meta={},
            idea=idea,
        )

    paper_md = getattr(proposal, "paper_md", None)
    meta_raw = getattr(proposal, "paper_meta_json", None)
    meta: dict = {}
    if meta_raw:
        try:
            meta = json.loads(meta_raw) or {}
        except (json.JSONDecodeError, TypeError):
            meta = {}

    if paper_md and paper_md.strip():
        status = "ready"
    elif meta.get("status") == "failed":
        status = "failed"
    elif meta_raw is not None or paper_md is not None:
        # Stage ran but left an empty/null artifact — treat as failed, not ready.
        status = "failed"
    else:
        # No paper columns written. If the strategy includes paper synthesis
        # the run hasn't reached/completed the stage; otherwise it was never
        # requested.
        status = "pending" if _idea_run_includes_paper_stage(idea) else "not_requested"

    return _paper_state_dict(status=status, paper_md=paper_md, meta=meta, idea=idea)


def _paper_state_dict(*, status, paper_md, meta, idea) -> dict:
    """Phase 1 1C: build the shape-consistent paper state object used by both
    the no-proposal and has-proposal branches of _serialize_paper_state."""
    release = meta.get("release")
    if isinstance(release, dict):
        import hashlib as _release_hashlib
        release = dict(release)
        current_hash = (
            _release_hashlib.sha256((paper_md or "").encode("utf-8")).hexdigest()
            if paper_md
            else None
        )
        release["current_paper_hash"] = current_hash
        release["current_matches_frozen"] = bool(
            current_hash and current_hash == release.get("frozen_paper_hash")
        )

    return {
        "status": status,
        "paper_md": paper_md if status == "ready" else None,
        "title": getattr(idea, "title", None),
        "word_count": meta.get("word_count"),
        "venue": meta.get("venue"),
        "model_used": meta.get("model_used"),
        "source_count": meta.get("source_count"),
        "synthesis_strategy": meta.get("synthesis_strategy"),
        "generated_at": meta.get("generated_at"),
        "source_run_id": getattr(idea, "pipeline_run_id", None),
        # Phase 1 1D: paper-level evaluation (scope=paper), exposed with an
        # explicit scope label so it is never confused with proposal evaluation.
        # The idea-detail response already carries the PROPOSAL evaluation
        # separately; these must not be collapsed into a single score.
        "paper_evaluation": meta.get("paper_evaluation"),
        # Release-final is separate from ordinary artifact readiness. A paper
        # may remain viewable/exportable without being frozen for release.
        "release": release,
    }


def _idea_run_includes_paper_stage(idea) -> bool:
    """Phase 1 1C: best-effort check whether the idea's run strategy includes
    the paper_synthesis stage. Used only to distinguish not_requested from
    pending; never used to claim a paper is ready. Returns True (conservative)
    when the strategy cannot be determined, so unknown runs surface as pending
    rather than not_requested.
    """
    try:
        from backend.db.database import get_session as _get_session
        from backend.db.models import PipelineRun as _PipelineRun

        run_id = getattr(idea, "pipeline_run_id", None)
        if not run_id:
            return True  # conservative: treat as paper-capable
        with _get_session() as session:
            run = session.get(_PipelineRun, run_id)
            if run is None:
                return True
            config = json.loads(run.config_json) if run.config_json else {}
            strategy = config.get("strategy", "deep_research")
        # paper_synthesis is enabled for deep_research and academic_proposal;
        # disabled for fast_scan and literature_review (see presets.py).
        return strategy in {"deep_research", "academic_proposal"}
    except Exception:
        return True  # conservative on any error


def _load_quarantine_rows(proposal_id: int) -> list:
    """Load QuarantinedCitation rows for a proposal.

    Returns [] on any error (fail-soft: a missing table or DB error means the
    proposal renders raw, which is the pre-quarantine behavior — no regression).
    Each row carries section_key and ref_index, which is all
    render_quarantined_view needs.
    """
    try:
        from sqlalchemy import select

        from backend.db.database import get_session
        from backend.db.models import QuarantinedCitation

        with get_session() as session:
            return list(session.execute(
                select(QuarantinedCitation).where(
                    QuarantinedCitation.proposal_id == proposal_id
                )
            ).scalars().all())
    except Exception:
        return []


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
    from backend.db.crud import count_ideas
    from backend.db.crud import list_ideas as db_list_ideas
    from backend.db.database import get_session

    effective_min_score = min_score if min_score > 0 else None

    from sqlalchemy import func as sa_func

    from backend.db.models import GovernanceDecision, IdeaPaperLink, Proposal

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
                select(Proposal.idea_id, Proposal.sections_json, Proposal.id)
                .where(Proposal.idea_id.in_(idea_ids))
            ).all()

            # STOPGAP: batch-load quarantine rows so list-view quality summaries
            # match detail-view (readers see redactions consistently).
            quarantine_by_proposal: dict[int, list] = {}
            try:
                from backend.db.models import QuarantinedCitation
                prop_ids = [row[2] for row in prop_rows if row[2] is not None]
                if prop_ids:
                    qrows = session.execute(
                        select(QuarantinedCitation).where(
                            QuarantinedCitation.proposal_id.in_(prop_ids)
                        )
                    ).scalars().all()
                    for q in qrows:
                        quarantine_by_proposal.setdefault(q.proposal_id, []).append(q)
            except Exception:
                pass  # fail-soft: render raw (pre-quarantine behavior)

            from backend.pipeline.quarantine import render_quarantined_view
            for pid, psections_json, prop_id in prop_rows:
                sections = None
                if psections_json:
                    try:
                        sections = json.loads(psections_json)
                    except (json.JSONDecodeError, TypeError):
                        pass
                if sections and prop_id in quarantine_by_proposal:
                    sections = render_quarantined_view(sections, quarantine_by_proposal[prop_id])
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
        from backend.db.models import IdeaPaperLink
        from backend.db.models import Paper as PaperModel
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

        # STOPGAP: render the quarantined view for reader-facing consumers.
        # section_hashes and the refine path use RAW sections_dict (so quarantine
        # never causes spurious 409s); quality_checks / remediation / citation_audit
        # / proposal_sections use the RENDERED view (readers see the redaction).
        # See backend/pipeline/quarantine.py for why sections is never mutated.
        rendered_sections = sections_dict
        if proposal and sections_dict:
            from backend.pipeline.quarantine import render_quarantined_view
            quarantined = _load_quarantine_rows(proposal.id)
            if quarantined:
                rendered_sections = render_quarantined_view(sections_dict, quarantined)

        quality_checks = compute_quality_checks(rendered_sections)

        # Pre-compute per-section content hashes for optimistic concurrency.
        # Uses RAW sections_dict — refine operates on the synthesizer's literal
        # output, so a quarantine must not change the hash a reviewer holds.
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
                # Phase 2 2B: expose the persisted proposal-scope evaluation so
                # proposal and paper evaluations are both visible and distinct.
                "proposal_evaluation": (
                    {"scope": "proposal", "dimensions": json.loads(proposal.proposal_evaluation_json)}
                    if getattr(proposal, "proposal_evaluation_json", None)
                    else None
                ),
                "proposal_sections": rendered_sections,
                "proposal_references": proposal_references,
                "supporting_papers": supporting_papers,
                "quality_checks": quality_checks,
                "section_hashes": section_hashes,
                "remediation_hints": compute_remediation_hints(rendered_sections, quality_checks),
                "citation_audit": audit_citations(rendered_sections, proposal_references),
                "experiment_results": experiment_results if experiment_results else None,
                # Phase 1 1C: exposed full-paper artifact + explicit state.
                # State machine: not_requested | pending | ready | failed.
                # An empty/placeholder paper is never reported as ready.
                "paper": _serialize_paper_state(proposal, idea),
                "created_at": str(idea.created_at),
            },
        }


@router.post(
    "/{idea_id}/paper/freeze",
    summary="Freeze the current assured paper as release-final",
)
async def freeze_paper(idea_id: int):
    """Freeze one exact assured paper revision without changing ordinary export.

    The current paper must have a READY assurance result bound to its exact
    content hash (or an existing READY PaperRevision for that exact hash).
    The frozen release is an immutable PaperRevision snapshot; later current
    revisions do not rewrite it.
    """
    from backend.db.database import get_session
    from backend.db.models import Idea, Proposal
    from backend.pipeline.evaluation.paper_release import (
        PaperReleaseError,
        freeze_current_paper,
    )

    with get_session() as session:
        idea = session.get(Idea, idea_id)
        if idea is None:
            raise NotFoundError("Idea not found")
        proposal = session.execute(
            select(Proposal).where(Proposal.idea_id == idea_id).limit(1)
        ).scalar_one_or_none()
        if proposal is None:
            raise NotFoundError("No proposal for this idea")
        try:
            release = freeze_current_paper(session, proposal)
        except PaperReleaseError as exc:
            raise ConflictError(str(exc)) from exc
        session.commit()
        return {"idea_id": idea_id, "proposal_id": proposal.id, "release": release}


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
    from backend.pipeline.generation.models import ResearchIdea
    from backend.pipeline.synthesis.proposal_synthesizer import MIN_WORDS, ProposalSynthesizer
    from backend.pipeline.synthesis.section_refinement import (
        ConcurrencyConflict,
        ProposalSectionRefinementService,
        ReceiptRequired,
    )
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
        ConcurrencyConflict,
        ProposalSectionRefinementService,
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

    from backend.api.quality_checks import compute_quality_checks
    from backend.db.crud import get_idea as db_get_idea
    from backend.db.crud import get_proposal_by_idea
    from backend.db.database import get_session
    from backend.db.models import ProposalSectionRevision

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


# ─── R2: Autonomous paper repair ─────────────────────────────────


def _derive_blocking_findings(eval_data: dict) -> list[str]:
    """Convert a persisted blocked evaluation into actionable repair findings.

    Uses dimension justifications and blocking_reasons — no human diagnosis
    required. The remediator receives these as its repair directive.
    """
    findings: list[str] = []

    dims = eval_data.get("dimensions", {})
    for dim_name, dim_data in sorted(dims.items()):
        if isinstance(dim_data, dict):
            score = dim_data.get("score", 1.0)
            justification = dim_data.get("justification", "")
            if score < 0.5 and justification:
                findings.append(f"{dim_name} (score={score}): {justification}")

    for reason in eval_data.get("blocking_reasons", []) or []:
        findings.append(f"Gate finding: {reason}")

    if not findings:
        findings.append("Paper evaluation is blocked but no specific low-scoring dimensions were identified.")

    return findings


@router.post(
    "/{idea_id}/paper/repair",
    summary="Autonomously repair a blocked paper using evaluator diagnostics",
)
async def repair_paper(idea_id: int):
    """Repair a blocked paper through governed autonomous remediation.

    Derives repair findings from the paper's own blocked evaluation, gathers
    persisted experiment evidence (spec, result markers, source map), and
    invokes the existing auto_revise_paper() remediator. One LLM call, zero
    human prose editing. The successor is then fully evaluated.

    The frozen release (if any) remains immutable. This operation creates a
    new current successor; it never edits historical revisions.
    """
    import hashlib as _hashlib
    from types import SimpleNamespace

    from backend.db.database import get_session
    from backend.db.models import ExperimentResult, Idea, Proposal
    from backend.pipeline.evaluation.paper_remediator import auto_revise_paper
    from backend.pipeline.experiment.manifest import ResultMarker
    from backend.pipeline.experiment.specification import load_spec
    from backend.pipeline.result import PipelineResult
    from backend.pipeline.stages import PaperSynthesisStage, StageContext
    from backend.providers.provider_factory import create_provider

    with get_session() as session:
        idea = session.get(Idea, idea_id)
        if idea is None:
            raise NotFoundError("Idea not found")

        proposal = session.execute(
            select(Proposal).where(Proposal.idea_id == idea_id).limit(1)
        ).scalar_one_or_none()
        if proposal is None:
            raise NotFoundError("No proposal for this idea")

        paper_md = proposal.paper_md or ""
        if not paper_md.strip():
            raise ConflictError("No paper to repair")

        # Capture the run linkage before the session closes — the
        # post-remediation evaluation needs the run's domain to score
        # the successor against the original research intent.
        idea_run_id = idea.pipeline_run_id

        meta = json.loads(proposal.paper_meta_json) if proposal.paper_meta_json else {}
        eval_data = meta.get("paper_evaluation", {})
        eval_status = eval_data.get("status", "unknown")
        eval_hash = eval_data.get("paper_hash", "")

        # Eligibility: must be blocked with exact-version evaluation
        if eval_status != "blocked":
            raise ConflictError(
                f"Paper evaluation status is '{eval_status}', not 'blocked'. "
                "Repair is only available for blocked papers."
            )

        actual_hash = _hashlib.sha256(paper_md.encode()).hexdigest()
        if eval_hash and eval_hash != actual_hash:
            raise ConflictError(
                "Evaluation paper_hash does not match current paper. "
                "Stale evaluation — re-evaluate before repairing."
            )

        # Derive blocking findings from the evaluation
        blocking_findings = _derive_blocking_findings(eval_data)

        # Resolve experiment evidence channels
        config = json.loads(meta.get("config", "{}")) if isinstance(meta.get("config"), str) else {}
        exp_spec_id = (
            config.get("experiment_spec_id")
            or meta.get("experiment_spec_id")
            or None
        )

        spec = None
        markers = []
        exp_result_id = None
        # Cold-repair shape: paper_meta_json is the flat dict written by
        # persistence._extract_paper_artifact, with source_map at the top
        # level. The nested full_paper shape only exists on the in-memory
        # proposal during a live run. Read both so the frozen source map
        # reaches the evidence invariants on either path — with an empty
        # map every SOURCE marker is falsely "invented" and no revision
        # can ever be promoted (run 2713, rev 24).
        source_map = meta.get("source_map")
        if not isinstance(source_map, list):
            nested_full_paper = meta.get("full_paper")
            source_map = (
                nested_full_paper.get("source_map", [])
                if isinstance(nested_full_paper, dict)
                else []
            )

        # EAD cold repair: detect autonomous multi-dataset design.
        # When the persisted metadata carries an autonomous design
        # state, recover both expected specs, both ExperimentResult
        # rows, and reconstruct the full dataset-qualified marker
        # set. This bypasses the single-spec path entirely.
        auto_design = meta.get("autonomous_experiment_design")
        if auto_design and auto_design.get("status") == "designed":
            from backend.pipeline.experiment.manifest import ResultMarker
            from backend.pipeline.experiment.specification import (
                _parse_spec as _auto_parse,
            )

            expected_specs = auto_design.get("specs", [])
            # Find all successful ExperimentResult rows for this
            # proposal.
            exp_rows = session.execute(
                select(ExperimentResult).where(
                    ExperimentResult.proposal_id == proposal.id,
                    ExperimentResult.success == True,  # noqa: E712
                ).order_by(ExperimentResult.id.asc()),
            ).scalars().all()

            if not exp_rows:
                raise ConflictError(
                    "No persisted experiment results found for"
                    " autonomous repair. Cannot proceed."
                )

            # Match results to expected specs by spec_id.
            exp_by_spec_id = {}
            for er in exp_rows:
                m = json.loads(er.manifest_json) if er.manifest_json else {}
                sid = m.get("experiment_spec_id", "")
                if m.get("status") == "succeeded" and sid:
                    exp_by_spec_id[sid] = er

            # Reconstruct markers in the same order as live execution.
            global_marker_idx = 0
            reconstructed_markers = []
            for spec_dict in expected_specs:
                sid = spec_dict.get("experiment_spec_id", "")
                er = exp_by_spec_id.get(sid)
                if not er:
                    continue
                dataset_name = spec_dict.get(
                    "dataset", {},
                ).get("name", "unknown")
                manifest = json.loads(
                    er.manifest_json,
                ) if er.manifest_json else {}
                results = manifest.get("results", {})
                artifacts = manifest.get("result_artifacts", [])

                try:
                    parsed_spec = _auto_parse(spec_dict)
                    _directions = parsed_spec.metric_directions
                    spec = parsed_spec  # last spec for auto_revise
                except Exception:
                    _directions = {}

                for metric_name, value in sorted(results.items()):
                    global_marker_idx += 1
                    artifact = next(
                        (
                            a for a in artifacts
                            if isinstance(a, dict)
                            and a.get("artifact_type") == "metrics"
                        ),
                        artifacts[0] if artifacts else None,
                    )
                    _role = "comparison"
                    if metric_name.startswith("baseline_"):
                        _role = "baseline"
                    reconstructed_markers.append(ResultMarker(
                        marker_index=global_marker_idx,
                        marker=f"RESULT-{global_marker_idx}",
                        metric_name=f"{dataset_name}.{metric_name}",
                        observed_value=value,
                        artifact_path=(
                            f"{dataset_name}/{artifact.get('filename', '')}"
                            if isinstance(artifact, dict) else ""
                        ),
                        artifact_sha256=(
                            artifact.get("sha256", "")
                            if isinstance(artifact, dict) else ""
                        ),
                        experiment_result_id=er.id,
                        direction=_directions.get(metric_name, ""),
                        role=_role,
                    ))

            markers = reconstructed_markers
            exp_result_id = exp_rows[0].id

            # Verify all expected datasets were recovered.
            recovered_ids = set(exp_by_spec_id.keys())
            expected_ids = {
                s.get("experiment_spec_id", "")
                for s in expected_specs
            }
            missing = expected_ids - recovered_ids
            if missing:
                raise ConflictError(
                    f"Autonomous repair incomplete: missing"
                    f" experiment results for {missing}."
                    f" Expected {len(expected_ids)},"
                    f" recovered {len(recovered_ids)}."
                )

        elif exp_spec_id:
            try:
                spec = load_spec(exp_spec_id)
            except Exception:
                pass

            # Find persisted experiment result
            exp_row = session.execute(
                select(ExperimentResult).where(
                    ExperimentResult.idea_id == idea_id
                ).order_by(ExperimentResult.id.desc()).limit(1)
            ).scalar_one_or_none()

            if exp_row:
                exp_result_id = exp_row.id
                manifest_raw = exp_row.manifest_json
                if manifest_raw:
                    manifest = json.loads(manifest_raw) if isinstance(manifest_raw, str) else manifest_raw
                    results = manifest.get("results", {})
                    artifacts = manifest.get("result_artifacts", [])
                    if manifest.get("status") == "succeeded" and results:
                        _directions = spec.metric_directions if spec else {}
                        for mi, (name, value) in enumerate(sorted(results.items()), 1):
                            artifact = next(
                                (a for a in artifacts if isinstance(a, dict) and a.get("artifact_type") == "metrics"),
                                artifacts[0] if artifacts else None,
                            )
                            _role = "comparison"
                            if name.startswith("baseline_"):
                                _role = "baseline"
                            elif name in ("improvement",) or name.endswith("_reduction") or name.endswith("_gain"):
                                _role = "derived"
                            markers.append(ResultMarker(
                                marker_index=mi, marker=f"RESULT-{mi}",
                                metric_name=name, observed_value=value,
                                artifact_path=artifact.get("filename", "") if isinstance(artifact, dict) else "",
                                artifact_sha256=artifact.get("sha256", "") if isinstance(artifact, dict) else "",
                                experiment_result_id=exp_result_id,
                                direction=_directions.get(name, ""),
                                role=_role,
                            ))

        if not exp_result_id:
            raise ConflictError(
                "No persisted experiment result found for this proposal. "
                "Repair requires registered experiment evidence."
            )

    # Invoke the remediator (outside the session — it manages its own sessions)
    result = await auto_revise_paper(
        proposal_id=proposal.id,
        experiment_result_id=exp_result_id,
        original_paper_md=paper_md,
        blocking_findings=blocking_findings,
        source_map=source_map,
        result_markers=markers,
        spec=spec,
        timeout_seconds=600.0,
    )

    # Run the full evaluator on the result (with R1 hydration for persisted markers)
    repair_eval_status = "unknown"
    repair_eval_hash = ""
    repair_gates = []

    if result.success and result.promoted:
        try:
            provider = create_provider()
            stage = PaperSynthesisStage(provider=provider)

            with get_session() as session:
                row = session.execute(
                    select(Proposal.paper_md, Proposal.paper_meta_json).where(
                        Proposal.id == proposal.id
                    )
                ).fetchone()
                new_md = row[0]
                new_meta = json.loads(row[1]) if row[1] else {}
                new_meta["paper_evaluation"] = {"status": "pending", "scope": "paper"}
                # Wire the promoted paper into the metadata so _evaluate_paper()
                # can read it. The evaluator reads metadata["full_paper"]
                # ["paper_markdown"] and ["source_map"], not proposal.paper_md
                # directly. Without this, the post-remediation evaluation
                # returns "unavailable" and the hash-binding contract
                # (eval.paper_hash == SHA256 of the current paper) is never
                # established for the successor.
                new_meta["full_paper"] = {
                    "paper_markdown": new_md,
                    "source_map": new_meta.get("source_map", []),
                }

            pipeline_result = PipelineResult()
            # Wire result_markers into the context so the numeric-fidelity
            # and experiment-alignment gates fire non-vacuously on the
            # successor paper. The markers are already in the proposal's
            # persisted metadata from the original pipeline run.
            if markers:
                pipeline_result.result_markers = {proposal.id: markers}
            # EAD-3e: Persist autonomous design state into the
            # proposal's metadata so cold repair can reconstruct it.
            auto_design = new_meta.get(
                "autonomous_experiment_design"
            )
            eval_params = {}
            if exp_spec_id:
                eval_params["experiment_spec_id"] = exp_spec_id
            if auto_design and auto_design.get("status") == "designed":
                eval_params["autonomous_experiment_design"] = auto_design

            # Cold re-evaluation must score the successor against the
            # SAME research intent as the original in-run evaluation.
            # The scope gate prefers ctx.research_question, then domain;
            # with neither it scored the revised paper against the
            # two-word generic domain and blocked on a 0.00-overlap
            # reading (run 2713). The frozen question lives in the
            # persisted design; the domain on the run row.
            eval_question = (auto_design or {}).get("research_question") or ""
            eval_domain = "machine learning"
            if idea_run_id:
                try:
                    with get_session() as dom_session:
                        from backend.db.models import PipelineRun as _Run

                        run_row = dom_session.get(_Run, idea_run_id)
                        if run_row is not None and run_row.domain:
                            eval_domain = run_row.domain
                except Exception:
                    pass

            eval_ctx = StageContext(
                result=pipeline_result,
                domain=eval_domain,
                research_question=eval_question,
                params=eval_params,
            )
            proposal_obj = SimpleNamespace(paper_md=new_md, metadata=new_meta)

            await stage._evaluate_paper(eval_ctx, proposal_obj, new_meta, proposal.id)

            eval_result = new_meta.get("paper_evaluation", {})
            repair_eval_status = eval_result.get("status", "unknown")
            repair_eval_hash = eval_result.get("paper_hash", "")
            repair_gates = eval_result.get("gates", [])

            with get_session() as session:
                session.execute(
                    Proposal.__table__.update().where(
                        Proposal.id == proposal.id
                    ).values(paper_meta_json=json.dumps(new_meta))
                )
                session.commit()
        except Exception:
            repair_eval_status = "failed"
            repair_eval_hash = ""

    return {
        "idea_id": idea_id,
        "proposal_id": proposal.id,
        "repair": {
            "success": result.success,
            "promoted": result.promoted,
            "revision_number": result.revision_number,
            "original_paper_hash": result.original_paper_hash,
            "revised_paper_hash": result.revised_paper_hash,
            "findings_count": len(blocking_findings),
            "findings": blocking_findings,
        },
        "evaluation": {
            "status": repair_eval_status,
            "paper_hash": repair_eval_hash,
            "gates": repair_gates,
        },
    }
