"""Phase 9 / 9E — constrained one-attempt paper remediation.

The remediation orchestrator:
  1. Verifies the evidence package (hashes match)
  2. Atomically claims the one revision allowance
  3. Derives deterministic exact-span numeric patches from persisted
     RESULT evidence and applies them (Productive-1 R5; no repair-side
     LLM call — replaces the section-regeneration path that R4 proved
     could destroy already-passing gates and invent section structure)
  4. Verifies evidence invariants after patching
  5. Re-evaluates all gates, with explicit preservation postconditions:
     every gate green before repair must still be green after
  6. Persists the candidate; the repair route remains the sole
     promotion authority (PAC)

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
from dataclasses import dataclass, field

from backend.db.database import get_session
from backend.db.models import ExperimentResult, PaperRevision
from backend.pipeline.evaluation.numeric_patcher import (
    PatchApplicationError,
    apply_numeric_patches,
    derive_numeric_patch_manifest,
    gate_regressions,
    verify_patch_postconditions,
)

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
    patch_manifest: list[dict] = field(default_factory=list)

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
            "patch_manifest": self.patch_manifest,
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
      3. Derives deterministic exact-span numeric patches from the
         persisted RESULT evidence (no repair-side LLM call)
      4. Applies them, proving byte identity outside the authorized
         spans and the structural preservation contract
      5. Enforces preservation postconditions: every gate green before
         repair (including method fidelity) must still be green after
      6. Verifies evidence invariants and re-evaluates gates
      7. Persists the candidate; the repair route remains the sole
         promotion authority (PAC)

    Args:
        proposal_id: The proposal to revise.
        experiment_result_id: The persisted ExperimentResult.
        original_paper_md: The original (blocked) paper text — mandatory.
        blocking_findings: The gate findings that triggered remediation.
        source_map: The frozen source map.
        result_markers: The frozen result markers.
        spec: The experiment specification.
        timeout_seconds: Retained for signature compatibility only —
            deterministic repair has no model deadline. Per the frozen
            R5 contract the 600-second ceiling is an authoritative
            evaluation/provider budget, enforced downstream of the
            candidate.
        method_facts: Frozen implementation truth from the capability
            contract; a previously passing method-fidelity contract must
            still pass after patching (preservation postcondition).

    Returns:
        RemediationResult with the outcome.
    """
    original_hash = hashlib.sha256(original_paper_md.encode()).hexdigest()

    # ── Step 1: Verify evidence package ─────────────────────────────
    from backend.pipeline.evaluation.revision_directive import (
        EvidenceInvariant,
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
                # Idempotent retry (PAC-7). Two interruption classes:
                # (a) revision 1 carries a TERMINAL authoritative record
                #     (stamped by the route's atomic finalization in the
                #     SAME commit as the promotion) — return that
                #     terminal result; never synthesize again;
                # (b) revision 1 exists WITHOUT an authoritative record
                #     (crash between synthesis and authoritative
                #     evaluation) — return the persisted candidate with
                #     promoted=False so the route performs the
                #     authoritative full evaluation; NO second model
                #     call. An unstamped revision must NEVER be treated
                #     as authoritative merely because its screening
                #     eval_status is "ready" (owner review of PR #43:
                #     that inference let retry bypass the required
                #     full-paper evaluation while the canonical paper
                #     was still the original). A crash after the
                #     route's atomic commit cannot produce an unstamped
                #     promoted revision — the stamp is written before
                #     that same session.commit().
                detail = {}
                if existing.trigger_detail_json:
                    try:
                        detail = json.loads(existing.trigger_detail_json)
                    except Exception:
                        detail = {}
                authoritative = detail.get("authoritative")
                logger.info(
                    "Revision 1 already exists for proposal %d — %s",
                    proposal_id,
                    "returning terminal authoritative result"
                    if authoritative
                    else "returning persisted candidate for"
                         " authoritative evaluation",
                )
                if authoritative:
                    status = authoritative.get(
                        "status", existing.eval_status)
                    return RemediationResult(
                        success=True,
                        promoted=(status == "ready"),
                        revision_number=1,
                        eval_status=status,
                        gates=authoritative.get(
                            "gates",
                            json.loads(existing.gates_json)
                            if existing.gates_json else [],
                        ),
                        blocking_reasons=detail.get(
                            "blocking_findings", []),
                        original_paper_hash=original_hash,
                        revised_paper_hash=existing.paper_hash,
                        invariant_violations=[],
                    )
                return RemediationResult(
                    success=True,
                    promoted=False,
                    revision_number=1,
                    eval_status=existing.eval_status,
                    gates=json.loads(existing.gates_json) if existing.gates_json else [],
                    blocking_reasons=detail.get("blocking_findings", []),
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

    # ── Step 3: Derive deterministic numeric patches (R5) ───────────
    # Frozen contract (owner, 2026-08-30): every numeric-fidelity
    # mismatch is repaired at the smallest identifiable text span, with
    # the replacement taken from the persisted observed_value. No
    # repair-side LLM call, no retry loop, no regeneration — the R4
    # section-rewrite path (destroyer of already-passing method
    # fidelity, inventor of section structure) is gone.
    manifest = derive_numeric_patch_manifest(original_paper_md, result_markers)
    manifest_payload = {
        "derived_from": "persisted RESULT evidence",
        "blocking_findings": list(blocking_findings),
        "patch_manifest": [dict(p) for p in manifest],
    }

    if not manifest:
        _persist_revision(
            proposal_id, experiment_result_id, parent_id, original_paper_md,
            source="auto_remediation", trigger="alignment_blocked",
            blocking_findings=blocking_findings,
            directive_payload=manifest_payload,
            eval_status="blocked", gates=[], evidence=evidence,
        )
        return RemediationResult(
            success=False, promoted=False, revision_number=1,
            eval_status="blocked", gates=[], blocking_reasons=blocking_findings,
            original_paper_hash=original_hash, revised_paper_hash=original_hash,
            invariant_violations=[], error="no_numeric_defects",
            patch_manifest=[],
        )

    # ── Step 4: Apply the patches deterministically ─────────────────
    try:
        revised_paper_md = apply_numeric_patches(original_paper_md, manifest)
    except PatchApplicationError as exc:
        logger.error("Numeric patch application failed closed: %s", exc)
        _persist_revision(
            proposal_id, experiment_result_id, parent_id, original_paper_md,
            source="auto_remediation", trigger="alignment_blocked",
            blocking_findings=blocking_findings,
            directive_payload=manifest_payload,
            eval_status="blocked", gates=[], evidence=evidence,
        )
        return RemediationResult(
            success=False, promoted=False, revision_number=1,
            eval_status="blocked", gates=[], blocking_reasons=blocking_findings,
            original_paper_hash=original_hash, revised_paper_hash=original_hash,
            invariant_violations=[], error=str(exc),
            patch_manifest=[dict(p) for p in manifest],
        )

    # ── Step 4b: Structural postconditions (fail-closed, typed) ─────
    # Reconstruction proves byte identity outside the authorized spans;
    # the heading sequence and RESULT/SOURCE token multiset must be
    # identical. A numeric-token patch cannot represent a structural
    # change — this check makes that a proven contract, not an
    # emergent hope.
    post_violations = verify_patch_postconditions(
        original_paper_md, revised_paper_md, manifest,
    )
    if post_violations:
        logger.warning("Numeric patch postconditions violated: %s", post_violations)
        _persist_revision(
            proposal_id, experiment_result_id, parent_id, revised_paper_md,
            source="auto_remediation", trigger="alignment_blocked",
            blocking_findings=blocking_findings,
            directive_payload=manifest_payload,
            eval_status="blocked", gates=[], evidence=evidence,
        )
        return RemediationResult(
            success=False, promoted=False, revision_number=1,
            eval_status="blocked", gates=[],
            blocking_reasons=blocking_findings + post_violations,
            original_paper_hash=original_hash,
            revised_paper_hash=hashlib.sha256(revised_paper_md.encode()).hexdigest(),
            invariant_violations=post_violations,
            error="; ".join(post_violations),
            patch_manifest=[dict(p) for p in manifest],
        )

    # ── Step 4c: Preservation postconditions (P4) ───────────────────
    # Every gate green before repair must still be green after — the
    # authoritative evaluator re-checks all of these downstream, but a
    # candidate that provably regresses a passing gate is rejected here
    # so it can never be handed to promotion. Method fidelity is
    # checked explicitly because the pure gate evaluator does not
    # include it (stages.py owns that gate); this is the exact R4
    # regression class.
    from backend.pipeline.evaluation.paper_gate_evaluator import evaluate_paper_gates

    gates_before = evaluate_paper_gates(
        paper_md=original_paper_md,
        source_map=source_map,
        research_intent=spec.research_question,
        domain=spec.task_type or "machine learning",
        result_markers=result_markers,
        spec_method=spec.analysis_method,
        spec_dataset=spec.dataset_name,
        spec_baseline=spec.baseline_method,
        spec_comparison=spec.comparison_method,
    ).gates
    gates_after = evaluate_paper_gates(
        paper_md=revised_paper_md,
        source_map=source_map,
        research_intent=spec.research_question,
        domain=spec.task_type or "machine learning",
        result_markers=result_markers,
        spec_method=spec.analysis_method,
        spec_dataset=spec.dataset_name,
        spec_baseline=spec.baseline_method,
        spec_comparison=spec.comparison_method,
    ).gates
    preservation = gate_regressions(gates_before, gates_after)

    if method_facts:
        from backend.pipeline.evaluation.method_fidelity import evaluate_method_fidelity

        mf_before = evaluate_method_fidelity(original_paper_md, method_facts)
        mf_after = evaluate_method_fidelity(revised_paper_md, method_facts)
        if mf_before.passed and not mf_after.passed:
            preservation.append(
                "preservation_violation:method_fidelity:"
                + (mf_after.reason[:200] or "previously passing facts now fail")
            )

    if preservation:
        logger.warning("Numeric patch preservation violations: %s", preservation)
        _persist_revision(
            proposal_id, experiment_result_id, parent_id, revised_paper_md,
            source="auto_remediation", trigger="alignment_blocked",
            blocking_findings=blocking_findings,
            directive_payload=manifest_payload,
            eval_status="blocked", gates=[], evidence=evidence,
        )
        return RemediationResult(
            success=False, promoted=False, revision_number=1,
            eval_status="blocked", gates=[],
            blocking_reasons=blocking_findings + preservation,
            original_paper_hash=original_hash,
            revised_paper_hash=hashlib.sha256(revised_paper_md.encode()).hexdigest(),
            invariant_violations=preservation,
            error="; ".join(preservation),
            patch_manifest=[dict(p) for p in manifest],
        )

    revised_hash = hashlib.sha256(revised_paper_md.encode()).hexdigest()

    # ── Step 5: Verify evidence invariants ──────────────────────────
    ok, violations = verify_revised_paper_invariants(revised_paper_md, evidence)
    if not ok:
        logger.warning("Revision violated evidence invariants: %s", violations)
        _persist_revision(
            proposal_id, experiment_result_id, parent_id, revised_paper_md,
            source="auto_remediation", trigger="alignment_blocked",
            blocking_findings=blocking_findings,
            directive_payload=manifest_payload,
            eval_status="blocked", gates=[],
            evidence=evidence,
        )
        return RemediationResult(
            success=False, promoted=False, revision_number=1,
            eval_status="blocked", gates=[], blocking_reasons=blocking_findings,
            original_paper_hash=original_hash, revised_paper_hash=revised_hash,
            invariant_violations=violations,
            error="; ".join(str(v) for v in violations),
            patch_manifest=[dict(p) for p in manifest],
        )

    # ── Step 6: Re-evaluate gates ───────────────────────────────────
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

    # ── Step 7: Screening verdict — NOT promotion (PAC-2) ───────────
    # The remediator is a candidate producer. The pure gate screen above
    # remains useful (an obviously blocked revision skips the more
    # expensive full evaluation downstream), but it no longer mutates
    # the canonical Proposal: promotion authority moved to the repair
    # route's atomic finalization after the production full-paper
    # evaluation returns ready for the exact candidate bytes
    # (Promotion-Authority-Consistency successor, owner plan 2026-08-20;
    # demonstrated defect: split authority let promoted=true coexist
    # with a final authoritative blocked evaluation — regr-B#2).
    if gate_eval.status == "ready":
        logger.info(
            "Revision 1 candidate passed screening for proposal %d"
            " (authoritative full evaluation pending)",
            proposal_id,
        )
    else:
        logger.info(
            "Revision 1 blocked at screening for proposal %d: %s",
            proposal_id, gate_eval.blocking_reasons,
        )

    # Persist the revision record (the immutable candidate)
    _persist_revision(
        proposal_id, experiment_result_id, parent_id, revised_paper_md,
        source="auto_remediation",
        trigger="alignment_blocked",
        blocking_findings=blocking_findings,
        directive_payload=manifest_payload,
        eval_status=gate_eval.status,
        gates=gate_eval.gates,
        evidence=evidence,
    )

    return RemediationResult(
        success=True,
        # Truthful under the new contract: a newly generated candidate
        # performs no canonical mutation. The route's atomic
        # finalization is the only promotion authority.
        promoted=False,
        revision_number=1,
        eval_status=gate_eval.status,
        gates=gate_eval.gates,
        blocking_reasons=gate_eval.blocking_reasons,
        original_paper_hash=original_hash,
        revised_paper_hash=revised_hash,
        invariant_violations=[],
        patch_manifest=[dict(p) for p in manifest],
    )


def _persist_revision(
    proposal_id, experiment_result_id, parent_id, paper_md,
    source, trigger, blocking_findings, directive_payload, eval_status,
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
            directive_json=_json.dumps(directive_payload),
            eval_status=eval_status,
            gates_json=_json.dumps(gates),
            experiment_manifest_hash=evidence.experiment_manifest_hash,
            result_map_hash=evidence.result_map_hash,
            source_map_hash=evidence.source_map_hash,
        )
        session.add(rev)
        session.commit()
