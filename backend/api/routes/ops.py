"""Operational dashboard API — aggregated platform metrics.

Read-only endpoint that aggregates data from existing tables.
Returns partial metrics gracefully — a missing metric returns null/unknown
rather than failing the entire response.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlalchemy import select, func, and_

from backend.db.database import get_session
from backend.db.models import (
    PipelineRun,
    RunEvent,
    Idea,
    Proposal,
    Paper,
    IdeaPaperLink,
    ProposalSectionRevision,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/dashboard",
    summary="Operational dashboard metrics",
    description="Aggregated platform metrics for observability. Read-only, bounded by time window.",
)
async def get_dashboard(
    days: int = Query(default=7, ge=1, le=90, description="Time window in days (max 90)"),
    limit: int = Query(default=50, ge=1, le=200, description="Max items per metric section"),
):
    """Get aggregated operational metrics.

    Returns partial metrics — if a section fails, it returns null
    rather than breaking the entire response.

    Args:
        days: Time window in days (default 7, max 90).
        limit: Max items per metric section (default 50, max 200).

    Returns:
        Structured dashboard JSON with 4 sections: run_health,
        model_usage, source_health, quality_trends.
    """
    # Resolve Query defaults to ints (for direct calls outside FastAPI)
    if not isinstance(days, int):
        days = 7
    if not isinstance(limit, int):
        limit = 50
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)

    return {
        "window": {
            "days": days,
            "from": since.isoformat(),
            "to": now.isoformat(),
        },
        "run_health": _run_health(since, limit),
        "model_usage": _model_usage(since, limit),
        "source_health": _source_health(since, limit),
        "quality_trends": _quality_trends(since, limit),
    }


def _run_health(since: datetime, limit: int) -> dict:
    """Aggregate run status, duration, and slowest stages."""
    try:
        with get_session() as session:
            base = select(PipelineRun).where(PipelineRun.created_at >= since)

            total = session.execute(
                select(func.count(PipelineRun.id)).where(PipelineRun.created_at >= since)
            ).scalar() or 0

            status_counts = {}
            for status, count in session.execute(
                select(PipelineRun.status, func.count())
                .where(PipelineRun.created_at >= since)
                .group_by(PipelineRun.status)
            ).all():
                status_counts[status] = count

            # Average duration for completed runs
            completed = session.execute(
                select(PipelineRun)
                .where(
                    and_(
                        PipelineRun.created_at >= since,
                        PipelineRun.status == "completed",
                        PipelineRun.completed_at != None,
                    )
                )
                .limit(limit)
            ).scalars().all()

            durations = []
            for r in completed:
                if r.completed_at and r.created_at:
                    dur = (r.completed_at - r.created_at).total_seconds()
                    durations.append(dur)

            avg_duration = sum(durations) / len(durations) if durations else 0

            # Slowest stages from stage reports
            stage_times: dict[str, list[float]] = {}
            for r in completed:
                if not r.stage_report_json:
                    continue
                try:
                    report = json.loads(r.stage_report_json)
                    if isinstance(report, list):
                        for stage in report:
                            if isinstance(stage, dict) and stage.get("elapsed_s"):
                                name = stage.get("name", "unknown")
                                elapsed = stage.get("elapsed_s", 0)
                                if elapsed > 0:
                                    stage_times.setdefault(name, []).append(elapsed)
                except (json.JSONDecodeError, TypeError):
                    pass

            slowest = sorted(
                (
                    {
                        "stage": name,
                        "avg_seconds": sum(times) / len(times),
                        "max_seconds": max(times),
                        "samples": len(times),
                    }
                    for name, times in stage_times.items()
                ),
                key=lambda x: x["avg_seconds"],
                reverse=True,
            )[:5]

            return {
                "total_runs": total,
                "completed": status_counts.get("completed", 0),
                "failed": status_counts.get("failed", 0),
                "cancelled": status_counts.get("cancelled", 0),
                "running": status_counts.get("running", 0),
                "pending": status_counts.get("pending", 0),
                "average_duration_s": round(avg_duration, 1),
                "slowest_stages": slowest,
            }
    except Exception as e:
        logger.warning("run_health metric failed: %s", e)
        return {"error": str(e)}


def _model_usage(since: datetime, limit: int) -> dict:
    """Aggregate model receipt and cost data."""
    try:
        models: dict[str, dict] = {}
        total_receipts = 0

        with get_session() as session:
            # Check stage reports for model info
            runs = session.execute(
                select(PipelineRun)
                .where(
                    and_(
                        PipelineRun.created_at >= since,
                        PipelineRun.stage_report_json != None,
                    )
                )
                .limit(limit)
            ).scalars().all()

            for run in runs:
                try:
                    report = json.loads(run.stage_report_json)
                    if isinstance(report, list):
                        for stage in report:
                            if not isinstance(stage, dict):
                                continue
                            # Check for model receipts in stage data
                            receipts = stage.get("model_receipts") or []
                            for r in receipts:
                                if not isinstance(r, dict):
                                    continue
                                total_receipts += 1
                                model_key = f"{r.get('provider', '?')}/{r.get('served_model', '?')}"
                                entry = models.setdefault(model_key, {
                                    "provider": r.get("provider", "?"),
                                    "served_model": r.get("served_model", "?"),
                                    "calls": 0,
                                })
                                entry["calls"] += 1
                except (json.JSONDecodeError, TypeError):
                    pass

        # Also check section revisions for receipts
        try:
            with get_session() as session:
                revisions = session.execute(
                    select(ProposalSectionRevision)
                    .where(ProposalSectionRevision.created_at >= since)
                    .where(ProposalSectionRevision.model_receipt_json != None)
                    .limit(limit)
                ).scalars().all()

                for rev in revisions:
                    try:
                        receipt = json.loads(rev.model_receipt_json)
                        if isinstance(receipt, dict):
                            total_receipts += 1
                            model_key = f"{receipt.get('provider', '?')}/{receipt.get('served_model', '?')}"
                            entry = models.setdefault(model_key, {
                                "provider": receipt.get("provider", "?"),
                                "served_model": receipt.get("served_model", "?"),
                                "calls": 0,
                            })
                            entry["calls"] += 1
                    except (json.JSONDecodeError, TypeError):
                        pass
        except Exception:
            pass

        # Warnings: check for compatibility-mode runs (no receipts)
        warnings = []
        if total_receipts == 0:
            warnings.append("No model receipts found in window — runs may be using compatibility mode")

        return {
            "models": sorted(models.values(), key=lambda x: x["calls"], reverse=True),
            "total_receipts": total_receipts,
            "warnings": warnings,
        }
    except Exception as e:
        logger.warning("model_usage metric failed: %s", e)
        return {"error": str(e)}


def _source_health(since: datetime, limit: int) -> dict:
    """Aggregate source API health and paper yield."""
    try:
        with get_session() as session:
            # Papers by source (all-time — papers aren't timestamped by run)
            source_counts = {}
            for source, count in session.execute(
                select(Paper.source, func.count(Paper.id)).group_by(Paper.source)
            ).all():
                source_counts[source] = count

            total_papers = sum(source_counts.values())

            # Zero-result runs: check stage reports for contract violations
            zero_result_runs = 0
            runs = session.execute(
                select(PipelineRun.stage_report_json)
                .where(
                    and_(
                        PipelineRun.created_at >= since,
                        PipelineRun.stage_report_json != None,
                    )
                )
                .limit(limit)
            ).scalars().all()

            for report_json in runs:
                try:
                    report = json.loads(report_json)
                    if isinstance(report, list):
                        for stage in report:
                            if not isinstance(stage, dict):
                                continue
                            violations = stage.get("contract_violations") or []
                            if any("0 items" in str(v) for v in violations):
                                if stage.get("name") == "literature_search":
                                    zero_result_runs += 1
                                    break
                except (json.JSONDecodeError, TypeError):
                    pass

            sources = [
                {"source": s, "papers": c}
                for s, c in sorted(source_counts.items(), key=lambda x: x[1], reverse=True)
            ]

            return {
                "papers_found_total": total_papers,
                "zero_result_runs": zero_result_runs,
                "sources": sources,
            }
    except Exception as e:
        logger.warning("source_health metric failed: %s", e)
        return {"error": str(e)}


def _quality_trends(since: datetime, limit: int) -> dict:
    """Aggregate quality check pass rates and remediation metrics."""
    try:
        from backend.api.quality_checks import compute_quality_checks, audit_citations

        with get_session() as session:
            proposals = session.execute(select(Proposal)).scalars().all()

            total_sections = 0
            passed_sections = 0
            failure_counter: dict[str, int] = {}
            total_citation_needed = 0
            total_valid_citations = 0
            total_resolved = 0
            total_unresolved = 0
            proposal_count = 0

            for p in proposals:
                sections = json.loads(p.sections_json) if p.sections_json else {}
                if not sections:
                    continue
                proposal_count += 1

                qc = compute_quality_checks(sections) or []
                for check in qc:
                    total_sections += 1
                    if check["passed"]:
                        passed_sections += 1
                    for failure in check.get("failures", []):
                        failure_counter[failure] = failure_counter.get(failure, 0) + 1

                # Citation audit
                audit = audit_citations(sections)
                if audit:
                    summary = next((a for a in audit if a["section"] == "_summary"), None)
                    if summary:
                        total_citation_needed += summary.get("citation_needed_count", 0)
                        total_valid_citations += summary.get("valid_citation_count", 0)

            # Reference resolution from IdeaPaperLinks
            links = session.execute(
                select(IdeaPaperLink.role, func.count()).group_by(IdeaPaperLink.role)
            ).all()

            pass_rate = (passed_sections / total_sections * 100) if total_sections > 0 else 0
            citation_rate = None
            if total_valid_citations + total_citation_needed > 0:
                citation_rate = round(
                    total_valid_citations / (total_valid_citations + total_citation_needed) * 100, 1
                )

            # Remediation stats
            remediation_count = session.execute(
                select(func.count(ProposalSectionRevision.id))
                .where(ProposalSectionRevision.source == "section_refine")
            ).scalar() or 0
            restore_count = session.execute(
                select(func.count(ProposalSectionRevision.id))
                .where(ProposalSectionRevision.source == "rollback")
            ).scalar() or 0

            common_failures = sorted(
                (
                    {"failure": f, "count": c}
                    for f, c in failure_counter.items()
                ),
                key=lambda x: x["count"],
                reverse=True,
            )[:5]

            return {
                "proposal_count": proposal_count,
                "quality_pass_rate": round(pass_rate, 1),
                "common_failures": common_failures,
                "citation_resolution_rate": citation_rate,
                "total_citation_needed": total_citation_needed,
                "total_valid_citations": total_valid_citations,
                "remediation_count": remediation_count,
                "restore_count": restore_count,
            }
    except Exception as e:
        logger.warning("quality_trends metric failed: %s", e)
        return {"error": str(e)}
