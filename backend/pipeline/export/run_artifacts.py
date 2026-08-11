"""Durable Run Export — write a structured per-run directory after each pipeline run.

Produces a directory structure that can be diffed, inspected, and archived:
    data/runs/run_XXXXXX/
        brief.json          — input parameters (domain, queries, strategy)
        plan.json           — stage ordering and execution reports
        gaps.json           — identified research gaps
        ideas.json          — generated research ideas
        proposals/          — one markdown file per proposal
        quality_report.json — evaluation + provenance results
        log.jsonl           — per-stage event log (one JSON per line)

Inspired by DeepScientist's quest repository structure.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from backend.pipeline.utils.filenames import safe_filename

if TYPE_CHECKING:
    from backend.pipeline.result import PipelineResult
    from backend.pipeline.stages import StageContext

logger = logging.getLogger(__name__)


def _serialize(obj: Any) -> Any:
    """Recursively serialize dataclass/pydantic objects for JSON output."""
    if obj is None:
        return None
    if isinstance(obj, str | int | float | bool):
        return obj
    if hasattr(obj, "model_dump"):  # Pydantic v2
        return obj.model_dump()
    if hasattr(obj, "dict"):  # Pydantic v1
        try:
            return obj.dict()
        except Exception:
            pass
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if isinstance(obj, dict):
        return {str(k): _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_serialize(v) for v in obj]
    # Fallback: string representation
    return str(obj)


class RunArtifactExporter:
    """Export a complete pipeline run as a structured directory."""

    def __init__(self, output_root: str = "./data/runs") -> None:
        self._root = Path(output_root)

    async def export_run(
        self,
        run_id: str,
        result: PipelineResult,
        ctx: StageContext,
        params: dict,
        domain: str = "",
        strategy: str = "",
    ) -> str:
        """Export all pipeline outputs to a structured directory.

        Args:
            run_id: Pipeline run identifier.
            result: Pipeline result with all stage outputs.
            ctx: Stage context with accumulated state.
            params: Run parameters.
            domain: Research domain.
            strategy: Pipeline strategy name.

        Returns:
            Path to the exported run directory.
        """
        run_dir = self._root / safe_filename(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)

        # brief.json — input parameters
        self._write_json(run_dir / "brief.json", {
            "run_id": run_id,
            "domain": domain or getattr(ctx, "domain", ""),
            "research_question": getattr(ctx, "research_question", None),
            "search_queries": getattr(ctx, "search_queries", []),
            "params": _serialize(params),
            "strategy": strategy or params.get("strategy", "deep_research"),
        })

        # plan.json — stage ordering + execution reports
        stage_reports_data = []
        for report in result.stage_report:
            if hasattr(report, "to_dict"):
                stage_reports_data.append(report.to_dict())
            elif is_dataclass(report):
                stage_reports_data.append(asdict(report))
            else:
                stage_reports_data.append(str(report))

        self._write_json(run_dir / "plan.json", {
            "stage_count": len(stage_reports_data),
            "stage_reports": stage_reports_data,
        })

        # gaps.json — identified research gaps
        gaps_data = [_serialize(g) for g in (result.gaps or [])]
        self._write_json(run_dir / "gaps.json", gaps_data)

        # ideas.json — generated research ideas
        ideas_data = []
        for idea in (result.ideas or []):
            idea_dict = _serialize(idea)
            ideas_data.append(idea_dict)
        self._write_json(run_dir / "ideas.json", ideas_data)

        # proposals/ — one markdown file per proposal
        proposals_dir = run_dir / "proposals"
        proposals_dir.mkdir(exist_ok=True)
        for idx, proposal in (result.proposals or {}).items():
            title = getattr(proposal, "title", f"proposal_{idx}")
            slug = safe_filename(str(title), max_length=40)
            content = self._extract_proposal_text(proposal)
            (proposals_dir / f"{idx:02d}_{slug}.md").write_text(
                content, encoding="utf-8"
            )

        # quality_report.json — evaluation + provenance
        self._write_json(
            run_dir / "quality_report.json",
            _serialize(result.quality_report) if result.quality_report else {},
        )

        # log.jsonl — per-stage event log
        log_path = run_dir / "log.jsonl"
        with open(log_path, "w", encoding="utf-8") as f:
            for report in stage_reports_data:
                f.write(json.dumps(_serialize(report), default=str) + "\n")

        logger.info("Run artifacts exported to %s", run_dir)
        return str(run_dir)

    def _write_json(self, path: Path, data: Any) -> None:
        """Write JSON with error handling."""
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(_serialize(data), f, indent=2, default=str, ensure_ascii=False)
        except Exception as e:
            logger.warning("Failed to write %s: %s", path, e)

    @staticmethod
    def _extract_proposal_text(proposal: Any) -> str:
        """Extract text content from a proposal object."""
        # Try common field names
        for field_name in ("content_md", "content", "markdown", "text"):
            text = getattr(proposal, field_name, None)
            if text and len(text) > 50:
                return text

        # Try to_markdown() method
        if hasattr(proposal, "to_markdown"):
            try:
                return proposal.to_markdown()
            except Exception:
                pass

        # Fallback: serialize to string
        return str(proposal)
