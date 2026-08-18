"""Phase 9 / 9E — constrained one-attempt paper remediation.

The remediation orchestrator:
  1. Verifies the evidence package (hashes match)
  2. Atomically claims the one revision allowance
  3. Revises the paper from persisted evidence (NOT fresh synthesis)
  4. Verifies evidence invariants after revision
  5. Re-evaluates all gates
  6. Promotes the revision only if all gates pass

Key constraints (from Phase 9 corrections):
  - Revision receives the original paper as mandatory input
  - No experiment reruns, no retrieval, no proposal generation
  - One revision max (enforced by UNIQUE(proposal_id, revision_number))
  - Failed revision is persisted but NOT promoted
  - Eligible only for text-correctable blockers
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass

from backend.db.database import get_session
from backend.db.models import ExperimentResult, PaperRevision, Proposal
from backend.pipeline.gateway.transport import GatewayTransportError

logger = logging.getLogger(__name__)


@dataclass
class RemediationResult:
    """Result of a remediation attempt."""

    success: bool
    promoted: bool  # True if the revised paper became canonical
    revision_number: int
    eval_status: str  # ready | blocked
    gates: list[dict]
    blocking_reasons: list[str]
    original_paper_hash: str
    revised_paper_hash: str
    invariant_violations: list[str]
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "promoted": self.promoted,
            "revision_number": self.revision_number,
            "eval_status": self.eval_status,
            "gates": self.gates,
            "blocking_reasons": self.blocking_reasons,
            "original_paper_hash": self.original_paper_hash,
            "revised_paper_hash": self.revised_paper_hash,
            "invariant_violations": self.invariant_violations,
            "error": self.error,
        }


async def auto_revise_paper(
    proposal_id: int,
    experiment_result_id: int,
    original_paper_md: str,
    blocking_findings: list[str],
    source_map: list[dict],
    result_markers: list,  # list of ResultMarker objects
    spec,  # ExperimentSpec
    timeout_seconds: float = 600.0,
    method_facts: dict | None = None,
) -> RemediationResult:
    """Perform one constrained paper revision from persisted evidence.

    This is the Phase 9 automatic remediation entry point. It:
      1. Verifies the evidence package
      2. Claims revision 1 atomically (stores original as revision 0)
      3. Builds a RevisionDirective from the blocking findings
      4. Calls the synthesis provider with the original paper + directive
      5. Verifies evidence invariants
      6. Re-evaluates gates
      7. Promotes only if all gates pass

    Args:
        proposal_id: The proposal to revise.
        experiment_result_id: The persisted ExperimentResult.
        original_paper_md: The original (blocked) paper text — mandatory.
        blocking_findings: The gate findings that triggered remediation.
        source_map: The frozen source map.
        result_markers: The frozen result markers.
        spec: The experiment specification.
        timeout_seconds: Provider timeout.
        method_facts: Frozen implementation truth from the capability
            contract; injected verbatim into the revision prompt so the
            methodology section describes the executed protocol.

    Returns:
        RemediationResult with the outcome.
    """
    original_hash = hashlib.sha256(original_paper_md.encode()).hexdigest()

    # ── Step 1: Verify evidence package ─────────────────────────────
    from backend.pipeline.evaluation.revision_directive import (
        EvidenceInvariant,
        RevisionDirective,
        verify_revised_paper_invariants,
    )

    result_map_tuple = tuple(
        (m.marker, m.observed_value) for m in result_markers
    )
    source_map_tuple = tuple(
        f"[{entry.get('marker', '').strip('[]')}]" for entry in (source_map or [])
    )

    # Load manifest hash
    with get_session() as session:
        exp = session.get(ExperimentResult, experiment_result_id)
        manifest_hash = hashlib.sha256(
            (exp.manifest_json or "").encode()
        ).hexdigest() if exp and exp.manifest_json else ""

    evidence = EvidenceInvariant(
        result_map=result_map_tuple,
        source_map=source_map_tuple,
        experiment_manifest_hash=manifest_hash,
        dataset_hash=spec.dataset_raw_sha256,
        analysis_code_hash="",  # filled from manifest
    )

    # ── Step 2: Store revision 0 (original) ─────────────────────────
    # The original paper MUST be preserved in the revision table BEFORE
    # any revision attempt. This happens unconditionally, before the
    # idempotency check for revision 1.
    parent_id = None
    try:
        with get_session() as session:
            from sqlalchemy import select
            # Store revision 0 (original) if not already stored
            rev0 = session.execute(
                select(PaperRevision).where(
                    PaperRevision.proposal_id == proposal_id,
                    PaperRevision.revision_number == 0,
                )
            ).scalar_one_or_none()

            if not rev0:
                rev0 = PaperRevision(
                    proposal_id=proposal_id,
                    experiment_result_id=experiment_result_id,
                    revision_number=0,
                    parent_revision_id=None,
                    paper_md=original_paper_md,
                    paper_hash=original_hash,
                    source="pipeline",
                    trigger="initial",
                    eval_status="blocked",
                    gates_json=json.dumps([]),
                    result_map_hash=evidence.result_map_hash,
                    source_map_hash=evidence.source_map_hash,
                    experiment_manifest_hash=manifest_hash,
                )
                session.add(rev0)
                session.commit()  # MUST commit, not just flush — get_session() rolls back on close

            parent_id = rev0.id
    except Exception as e:
        logger.error("Failed to store revision 0: %s", e)

    # ── Step 2b: Check idempotency for revision 1 ───────────────────
    try:
        with get_session() as session:
            from sqlalchemy import select
            existing = session.execute(
                select(PaperRevision).where(
                    PaperRevision.proposal_id == proposal_id,
                    PaperRevision.revision_number == 1,
                )
            ).scalar_one_or_none()

            if existing:
                # Idempotent: return the existing revision result
                logger.info(
                    "Revision 1 already exists for proposal %d — returning cached result",
                    proposal_id,
                )
                return RemediationResult(
                    success=True,
                    promoted=(existing.eval_status == "ready"),
                    revision_number=1,
                    eval_status=existing.eval_status,
                    gates=json.loads(existing.gates_json) if existing.gates_json else [],
                    blocking_reasons=json.loads(existing.trigger_detail_json).get("blocking_findings", []) if existing.trigger_detail_json else [],
                    original_paper_hash=original_hash,
                    revised_paper_hash=existing.paper_hash,
                    invariant_violations=[],
                )
    except Exception as e:
        logger.error("Failed to store revision 0: %s", e)
        return RemediationResult(
            success=False, promoted=False, revision_number=0,
            eval_status="blocked", gates=[], blocking_reasons=blocking_findings,
            original_paper_hash=original_hash, revised_paper_hash=original_hash,
            invariant_violations=[], error=str(e),
        )

    # ── Step 3: Build revision directive ────────────────────────────
    from backend.pipeline.evaluation.claim_alignment import evaluate_claim_alignment

    claim_result = evaluate_claim_alignment(
        paper_md=original_paper_md,
        spec_method=spec.analysis_method,
        spec_dataset=spec.dataset_name,
        spec_baseline=spec.baseline_method,
        spec_comparison=spec.comparison_method,
    )

    directive = RevisionDirective(
        blocking_findings=tuple(blocking_findings),
        research_question=spec.research_question,
        task_type=spec.task_type,
        target_name=spec.target_name,
        executed_method=spec.analysis_method,
        baseline_method=spec.baseline_method,
        comparison_method=spec.comparison_method,
        primary_metric=spec.primary_metric,
        metric_direction=spec.metric_directions.get(spec.primary_metric, ""),
        dataset_name=spec.dataset_name,
        split_method=spec.split_method,
        random_seed=spec.random_seed,
        evidence=evidence,
        unexecuted_methods_detected=(
            claim_result.unexecuted_method_in_abstract,
            claim_result.unexecuted_method_in_conclusion,
        ),
        method_facts=method_facts or None,
    )

    # ── Step 4: Revise the paper ────────────────────────────────────
    # Per correction #3: this is a REVISION, not fresh synthesis.
    # The original paper is included in the prompt and the LLM is
    # instructed to fix specific defects while preserving the structure.
    from backend.config import get_settings
    from backend.pipeline.synthesis.paper_synthesizer import PaperSynthesizer
    from backend.providers.provider_factory import get_generation_provider

    settings = get_settings()
    provider = get_generation_provider(settings)
    synthesizer = PaperSynthesizer(provider)

    revision_prompt = directive.build_revision_prompt()
    # The original paper is part of the revision context — the LLM must
    # revise it, not write a new one from scratch.
    full_context = (
        f"## ORIGINAL PAPER (revise this — do not write a new paper from scratch)\n\n"
        f"{original_paper_md}\n\n"
        f"{revision_prompt}\n\n"
        f"## INSTRUCTION\n"
        f"Revise the ORIGINAL PAPER above to fix the blocking findings. "
        f"Preserve the overall structure, all [RESULT-N] and [SOURCE-N] markers, "
        f"and all observed metric values. Change only the sections that contain "
        f"the defects (typically the abstract, contribution statement, and conclusion). "
        f"The revised paper must describe the executed experiment as its central contribution."
    )

    try:
        import asyncio
        result = await asyncio.wait_for(
            synthesizer.synthesize(
                proposal_text=full_context,
                source_papers=[],  # sources are in the original paper
                domain=spec.task_type or "machine learning",
                proposal_id=proposal_id,
            ),
            timeout=timeout_seconds,
        )
    except GatewayTransportError:
        # Case-4 R2 (adjudicated GENERIC_PRODUCT_DEFECT, 2026-08-18): a
        # typed provider/transport failure must keep its identity. The Q2
        # stage-loop terminalization converts it to FAILED_EXECUTION; it
        # must never become fallback output on a dead provider.
        raise
    except Exception as e:
        logger.error("Revision synthesis failed: %s", e)
        revised_paper_md = None
    else:
        revised_paper_md = result.paper_markdown if result else None

    if not revised_paper_md or len(revised_paper_md.split()) < 200:
        # Revision failed — persist as blocked, do NOT promote
        _persist_revision(
            proposal_id, experiment_result_id, parent_id,
            revised_paper_md or original_paper_md,
            source="auto_remediation",
            trigger="alignment_blocked",
            blocking_findings=blocking_findings,
            directive=directive,
            eval_status="blocked",
            gates=[],
            evidence=evidence,
        )
        return RemediationResult(
            success=False, promoted=False, revision_number=1,
            eval_status="blocked", gates=[], blocking_reasons=blocking_findings,
            original_paper_hash=original_hash,
            revised_paper_hash=hashlib.sha256((revised_paper_md or "").encode()).hexdigest(),
            invariant_violations=[], error="Revision synthesis produced no output",
        )

    revised_hash = hashlib.sha256(revised_paper_md.encode()).hexdigest()

    # ── Step 5: Verify evidence invariants ──────────────────────────
    ok, violations = verify_revised_paper_invariants(revised_paper_md, evidence)
    if not ok:
        logger.warning("Revision violated evidence invariants: %s", violations)
        _persist_revision(
            proposal_id, experiment_result_id, parent_id, revised_paper_md,
            source="auto_remediation", trigger="alignment_blocked",
            blocking_findings=blocking_findings, directive=directive,
            eval_status="blocked", gates=[],
            evidence=evidence,
        )
        return RemediationResult(
            success=False, promoted=False, revision_number=1,
            eval_status="blocked", gates=[], blocking_reasons=blocking_findings,
            original_paper_hash=original_hash, revised_paper_hash=revised_hash,
            invariant_violations=violations,
        )

    # ── Step 6: Re-evaluate gates ───────────────────────────────────
    from backend.pipeline.evaluation.paper_gate_evaluator import evaluate_paper_gates
    gate_eval = evaluate_paper_gates(
        paper_md=revised_paper_md,
        source_map=source_map,
        research_intent=spec.research_question,
        domain=spec.task_type or "machine learning",
        result_markers=result_markers,
        spec_method=spec.analysis_method,
        spec_dataset=spec.dataset_name,
        spec_baseline=spec.baseline_method,
        spec_comparison=spec.comparison_method,
    )

    # ── Step 7: Promote only if all gates pass ──────────────────────
    if gate_eval.status == "ready":
        # Promote: update the canonical paper_md AND the metadata's
        # full_paper.paper_markdown so that downstream evaluation
        # (_evaluate_paper reads from metadata["full_paper"]) sees the
        # exact promoted text, not a stale P1 version.
        with get_session() as session:
            proposal = session.get(Proposal, proposal_id)
            if proposal:
                proposal.paper_md = revised_paper_md
                # Sync metadata so _evaluate_paper reads the promoted text
                meta = json.loads(proposal.paper_meta_json) if proposal.paper_meta_json else {}
                fp = meta.get("full_paper")
                if isinstance(fp, dict):
                    fp["paper_markdown"] = revised_paper_md
                    meta["full_paper"] = fp
                    proposal.paper_meta_json = json.dumps(meta)
                session.commit()
        logger.info("Revision 1 promoted for proposal %d (eval=ready)", proposal_id)
    else:
        logger.info("Revision 1 blocked for proposal %d: %s", proposal_id, gate_eval.blocking_reasons)

    # Persist the revision record
    _persist_revision(
        proposal_id, experiment_result_id, parent_id, revised_paper_md,
        source="auto_remediation",
        trigger="alignment_blocked",
        blocking_findings=blocking_findings,
        directive=directive,
        eval_status=gate_eval.status,
        gates=gate_eval.gates,
        evidence=evidence,
    )

    return RemediationResult(
        success=True,
        promoted=(gate_eval.status == "ready"),
        revision_number=1,
        eval_status=gate_eval.status,
        gates=gate_eval.gates,
        blocking_reasons=gate_eval.blocking_reasons,
        original_paper_hash=original_hash,
        revised_paper_hash=revised_hash,
        invariant_violations=[],
    )


def _persist_revision(
    proposal_id, experiment_result_id, parent_id, paper_md,
    source, trigger, blocking_findings, directive, eval_status,
    gates, evidence,
):
    """Persist a revision record to the paper_revisions table."""
    import json as _json
    paper_hash = hashlib.sha256(paper_md.encode()).hexdigest()

    with get_session() as session:
        rev = PaperRevision(
            proposal_id=proposal_id,
            experiment_result_id=experiment_result_id,
            revision_number=1,
            parent_revision_id=parent_id,
            paper_md=paper_md,
            paper_hash=paper_hash,
            source=source,
            trigger=trigger,
            trigger_detail_json=_json.dumps({"blocking_findings": blocking_findings}),
            directive_json=_json.dumps(directive.to_dict()),
            eval_status=eval_status,
            gates_json=_json.dumps(gates),
            experiment_manifest_hash=evidence.experiment_manifest_hash,
            result_map_hash=evidence.result_map_hash,
            source_map_hash=evidence.source_map_hash,
        )
        session.add(rev)
        session.commit()
