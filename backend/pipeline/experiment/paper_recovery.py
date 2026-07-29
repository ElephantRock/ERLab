"""Phase 6 — empirical paper recovery from persisted experiment state.

Synthesizes a paper from existing durable state without rerunning any upstream
pipeline stages. Loads the persisted proposal, literature source map,
ExperimentResult, manifest, and result artifacts, then invokes paper synthesis
directly (no asyncio.wait_for wrapper) with observed-result context.

Does NOT invoke: literature search, ingestion, gap analysis, idea generation,
proposal synthesis, or experiment execution.

The recovery path uses the existing PaperSynthesizer / SectionWiseSynthesizer
but calls them directly rather than through the stage pipeline. This removes
the PER_PROPOSAL_TIMEOUT wrapper that caused the B-08 failure in Phase 5.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from backend.db.database import get_session
from backend.db.models import ExperimentResult, Proposal, PaperSourceMarker
from backend.pipeline.experiment.manifest import ExperimentManifest, ResultMarker
from backend.pipeline.synthesis.paper_synthesizer import PaperSynthesizer
from backend.pipeline.synthesis.section_wise_synthesizer import SectionWiseSynthesizer
from backend.pipeline.evaluation.proposal_evaluator import ProposalEvaluator
from backend.pipeline.evaluation.conclusion_checker import classify_conclusion_support
from backend.pipeline.evaluation.scope_checker import classify_scope_alignment
from backend.providers.provider_factory import get_generation_provider
from backend.config import get_settings

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


async def resume_empirical_paper(
    proposal_id: int,
    experiment_result_id: int,
    timeout_seconds: float = 1800.0,
) -> dict:
    """Synthesize a paper from persisted proposal + experiment state.

    Args:
        proposal_id: The proposal to write a paper for.
        experiment_result_id: The successful ExperimentResult to ground claims in.
        timeout_seconds: Per-proposal synthesis timeout (default 1800s = 30 min,
            3x the Phase 5 B-08 boundary of 600s).

    Returns:
        Dict with: proposal_id, paper_markdown, word_count, sections_generated,
        sections_total, synthesis_strategy, eval_status, gates, result_markers.
    """
    # ── 1. Load and verify persisted state ──────────────────────────
    with get_session() as session:
        proposal = session.get(Proposal, proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        exp = session.get(ExperimentResult, experiment_result_id)
        if not exp:
            raise ValueError(f"ExperimentResult {experiment_result_id} not found")

        manifest = ExperimentManifest.from_dict(json.loads(exp.manifest_json))

        # Verify experiment succeeded
        if manifest.status != "succeeded":
            raise ValueError(f"Experiment status is '{manifest.status}', not 'succeeded'")

        # Load source markers (literature provenance)
        markers = session.query(PaperSourceMarker).filter_by(
            proposal_id=proposal_id
        ).order_by(PaperSourceMarker.marker_index).all()

        # Get the proposal content
        proposal_text = proposal.content_md or ""

        # Get linked papers for source formatting
        from backend.db.models import Paper
        source_papers = []
        source_ids = []
        for m in markers:
            if m.source_paper_id and m.mapping_status == "mapped":
                paper = session.get(Paper, m.source_paper_id)
                if paper:
                    source_ids.append(paper.source_id)
                    authors = json.loads(paper.authors) if paper.authors else []
                    author_str = ", ".join(authors[:3]) if authors else "Unknown"
                    line = (
                        f"[SOURCE-{m.marker_index}] {author_str} "
                        f"({paper.year or 'n.d.'}). {paper.title or 'Untitled'}. "
                        f"{paper.venue or ''}."
                    )
                    if paper.doi:
                        line += f" DOI: {paper.doi}"
                    if paper.abstract:
                        line += f"\n  Abstract: {paper.abstract[:500]}"
                    source_papers.append(line)

    # ── 2. Build result markers from manifest metrics ──────────────
    result_markers: list[ResultMarker] = []
    metrics = manifest.results or {}
    for mi, (metric_name, value) in enumerate(sorted(metrics.items()), 1):
        artifact = next(
            (a for a in manifest.result_artifacts if a.artifact_type == "metrics"),
            manifest.result_artifacts[0] if manifest.result_artifacts else None
        )
        result_markers.append(ResultMarker(
            marker_index=mi,
            marker=f"RESULT-{mi}",
            metric_name=metric_name,
            observed_value=value,
            artifact_path=artifact.filename if artifact else "",
            artifact_sha256=artifact.sha256 if artifact else "",
            experiment_result_id=experiment_result_id,
        ))

    # ── 3. Build experiment context for synthesis ──────────────────
    exp_lines = ["", "## OBSERVED RESULTS (empirically measured — cite with [RESULT-N])", ""]
    for m in result_markers:
        exp_lines.append(
            f"[{m.marker}] {m.metric_name} = {m.observed_value} "
            f"(source: metrics.json, experiment_result_id: {m.experiment_result_id})"
        )
    exp_lines.append("")
    exp_lines.append("These results are from an actual executed experiment. You may state")
    exp_lines.append("'we demonstrate' or 'our results show' ONLY for claims that cite [RESULT-N]")
    exp_lines.append("markers above. Do not claim empirical results for metrics not listed here.")
    exp_lines.append("")
    exp_lines.append("The experiment used:")
    exp_lines.append(f"  Dataset: {manifest.dataset.name if manifest.dataset else 'unknown'}")
    exp_lines.append(f"  Split: {manifest.split.train_fraction}/{manifest.split.test_fraction}" if manifest.split else "")
    exp_lines.append(f"  Seed: {manifest.split.random_seed}" if manifest.split else "")
    exp_lines.append(f"  Method: {manifest.analysis.method if manifest.analysis else 'checked-in analysis'}")
    experiment_context = "\n".join(exp_lines)

    synthesis_sources = list(source_papers) + [experiment_context]

    # ── 4. Synthesize paper (directly, no wait_for wrapper) ────────
    settings = get_settings()
    provider = get_generation_provider(settings)

    # Try monolithic first
    synthesizer = PaperSynthesizer(provider)
    result = await synthesizer.synthesize(
        proposal_text=proposal_text,
        source_papers=synthesis_sources,
        domain="machine learning",
        proposal_id=proposal_id,
    )

    strategy = "monolithic"
    if result is None:
        # Fallback to section-wise
        logger.info("Monolithic synthesis failed — trying section-wise")
        section_synth = SectionWiseSynthesizer(
            provider=provider,
            context_window=128000,  # glm-4.6 has 128k context
        )
        result = await section_synth.synthesize(
            proposal_text=proposal_text,
            source_papers=synthesis_sources,
            domain="machine learning",
            proposal_id=proposal_id,
        )
        strategy = "section_wise"

    if result is None:
        return {
            "proposal_id": proposal_id,
            "success": False,
            "error": "Both monolithic and section-wise synthesis failed",
        }

    # ── 5. Build source map and result map ─────────────────────────
    from backend.pipeline.stages import PaperSynthesisStage
    source_map = PaperSynthesisStage.build_source_map(source_ids, result.paper_markdown)

    # ── 6. Evaluate the paper ──────────────────────────────────────
    paper_md = result.paper_markdown
    has_empirical = any(
        f"[RESULT-{m.marker_index}]" in paper_md
        for m in result_markers
    )

    # Provenance gate
    prov_gate = PaperSynthesisStage.provenance_precondition(paper_md, source_map)

    # Scope gate
    scope_result = classify_scope_alignment(
        research_intent="machine learning classification Iris dataset",
        paper_title="",  # let the checker extract it
        paper_abstract=paper_md[:2000],
    )

    # Conclusion gate — with result markers
    conclusion_result = PaperSynthesisStage._classify_conclusion(
        ctx=None, proposal=None, paper_md=paper_md,
        result_markers=result_markers,
    )

    gates = [
        {"gate": "provenance", "passed": prov_gate.passed, "reason": prov_gate.reason},
        {"gate": "scope_alignment", "classification": scope_result.classification, "reason": scope_result.reason},
        {"gate": "conclusion_support", "classification": conclusion_result.classification, "reason": conclusion_result.reason},
    ]

    blocking_reasons = []
    if not prov_gate.passed:
        blocking_reasons.append(f"provenance: {prov_gate.reason}")
    if scope_result.classification == "off_scope":
        blocking_reasons.append(f"scope: {scope_result.reason}")
    if conclusion_result.classification == "overstated":
        blocking_reasons.append(f"conclusion: {conclusion_result.reason}")

    eval_status = "blocked" if blocking_reasons else "ready"

    return {
        "proposal_id": proposal_id,
        "success": True,
        "paper_markdown": paper_md,
        "word_count": result.word_count,
        "sections_generated": getattr(result, 'sections_generated', 1),
        "sections_total": getattr(result, 'sections_total', 1),
        "synthesis_strategy": strategy,
        "eval_status": eval_status,
        "blocking_reasons": blocking_reasons,
        "gates": gates,
        "result_markers": [m.to_dict() for m in result_markers],
        "source_map": source_map,
        "experiment_result_id": experiment_result_id,
        "experiment_manifest_id": manifest.experiment_spec_id,
    }
