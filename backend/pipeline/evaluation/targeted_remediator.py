"""Phase 10 / 10D+10E — targeted section revision directive and assembly service.

Replaces only defective sections rather than regenerating the full paper.
Uses the section parser (10C) and structured findings (10B) to:
  1. Identify which sections need replacement
  2. Request replacements for ONLY those sections from the provider
  3. Assemble deterministically (unchanged sections byte-identical)
  4. Verify all integrity constraints
  5. Promote only if all gates pass
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from backend.pipeline.evaluation.claim_repair import ClaimRepairFinding, derive_repair_findings
from backend.pipeline.evaluation.paper_sections import (
    ParsedPaper,
    assemble_paper,
    parse_paper,
)
from backend.pipeline.evaluation.revision_directive import (
    EvidenceInvariant,
    verify_revised_paper_invariants,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TargetedRevisionDirective:
    """Directive for targeted section-level revision."""

    original_paper_hash: str
    allowed_sections: tuple[str, ...]  # sections that may be replaced
    findings: tuple[ClaimRepairFinding, ...]
    executed_method: str
    executed_dataset: str
    baseline_method: str
    comparison_method: str
    primary_metric: str
    metric_direction: str
    research_question: str
    task_type: str
    target_name: str
    split_method: str
    random_seed: int
    evidence: EvidenceInvariant

    def build_provider_prompt(
        self, defective_sections: dict[str, str],
    ) -> str:
        """Build the prompt for the targeted revision provider call.

        Sends only the defective sections (not the full paper) along with
        the exact findings and canonical experiment description.
        """
        lines = [
            "## TARGETED SECTION REVISION",
            "",
            "Revise ONLY the sections listed below. Do NOT modify any other section.",
            "Each replacement must fix the identified defect while preserving all",
            "[RESULT-N] and [SOURCE-N] markers and observed metric values.",
            "",
            "### CANONICAL EXPERIMENT DESCRIPTION",
            f"Research question: {self.research_question}",
            f"Task type: {self.task_type}",
            f"Dataset: {self.executed_dataset}",
            f"Target: {self.target_name}",
            f"Executed method: {self.executed_method}",
            f"Baseline: {self.baseline_method}",
            f"Comparison model: {self.comparison_method}",
            f"Primary metric: {self.primary_metric} ({self.metric_direction})",
            f"Split: {self.split_method}, seed={self.random_seed}",
            "",
            "### SECTIONS TO REVISE",
        ]
        for section_name, section_text in defective_sections.items():
            lines.append(f"\n#### {section_name.upper()}")
            lines.append(section_text)
            # Add the specific findings for this section
            section_findings = [f for f in self.findings if f.section == section_name]
            if section_findings:
                lines.append("\n**Defects to fix:**")
                for f in section_findings:
                    lines.append(f"- [{f.severity}] {f.finding_type}: {f.required_action}")

        lines.append("")
        lines.append("### REQUIRED OUTPUT FORMAT")
        lines.append("Return a JSON object with replacement_sections mapping section names")
        lines.append("to revised section text (including the heading line):")
        lines.append('```json')
        lines.append('{')
        lines.append('  "replacement_sections": {')
        for section_name in defective_sections:
            lines.append(f'    "{section_name}": "...revised section text..."')
        lines.append('  }')
        lines.append('}')
        lines.append('```')
        lines.append("")
        lines.append("Rules:")
        lines.append("- Only include sections that were listed above.")
        lines.append("- Each replacement must name the executed method and dataset.")
        lines.append("- Unexecuted methods (quantum, GNN, etc.) may appear ONLY as")
        lines.append("  explicitly labeled 'background' or 'future work'.")
        lines.append("- Preserve all [RESULT-N] and [SOURCE-N] markers.")
        lines.append("- Do not change any observed metric values.")

        return "\n".join(lines)


@dataclass
class TargetedRevisionResult:
    """Result of a targeted section revision."""

    success: bool
    promoted: bool
    revision_number: int
    eval_status: str
    gates: list[dict] = field(default_factory=list)
    blocking_reasons: list[str] = field(default_factory=list)
    changed_sections: list[str] = field(default_factory=list)
    unchanged_section_hashes: dict[str, str] = field(default_factory=dict)
    original_paper_hash: str = ""
    revised_paper_hash: str = ""
    findings_count: int = 0
    error: str = ""
    invariant_violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "promoted": self.promoted,
            "revision_number": self.revision_number,
            "eval_status": self.eval_status,
            "gates": self.gates,
            "blocking_reasons": self.blocking_reasons,
            "changed_sections": self.changed_sections,
            "unchanged_section_hashes": self.unchanged_section_hashes,
            "original_paper_hash": self.original_paper_hash,
            "revised_paper_hash": self.revised_paper_hash,
            "findings_count": self.findings_count,
            "error": self.error,
            "invariant_violations": self.invariant_violations,
        }


def validate_targeted_revision(
    original_parsed: ParsedPaper,
    replacement_sections: dict[str, str],
    allowed_sections: set[str],
    evidence: EvidenceInvariant,
    revised_paper_md: str,
) -> tuple[bool, list[str]]:
    """Validate that a targeted revision meets all integrity constraints.

    Returns (all_ok, violations).
    """
    violations: list[str] = []

    # Check 1: only allowed sections changed
    for section_name in replacement_sections:
        if section_name not in allowed_sections:
            violations.append(f"Unauthorized section replacement: {section_name}")

    # Check 2: unchanged sections must be byte-identical
    revised_parsed = parse_paper(revised_paper_md)
    for section in original_parsed.sections:
        if section.name not in replacement_sections:
            revised_section = revised_parsed.get_section(section.name)
            if revised_section and revised_section.hash != section.hash:
                violations.append(
                    f"Unchanged section '{section.name}' hash differs: "
                    f"expected {section.hash[:16]}..., got {revised_section.hash[:16]}..."
                )

    # Check 3: required replacement sections present
    for required in allowed_sections:
        if required not in replacement_sections:
            violations.append(f"Missing required replacement: {required}")

    # Check 4: no empty replacements
    for section_name, text in replacement_sections.items():
        if not text or not text.strip():
            violations.append(f"Empty replacement for section: {section_name}")

    # Check 5: evidence invariants (no invented markers)
    ok, marker_violations = verify_revised_paper_invariants(revised_paper_md, evidence)
    violations.extend(marker_violations)

    return (len(violations) == 0, violations)


async def auto_repair_paper_sections(
    proposal_id: int,
    experiment_result_id: int,
    original_paper_md: str,
    spec: Any,
    source_map: list[dict],
    result_markers: list,
    max_provider_calls: int = 1,
    timeout_seconds: float = 600.0,
    provider_call_fn: Any = None,
) -> TargetedRevisionResult:
    """Perform one targeted section-level repair.

    This is the Phase 10 entry point. It:
      1. Parses the original paper
      2. Derives repair findings
      3. Identifies sections to replace
      4. Calls the provider for replacement sections (one call max)
      5. Validates the response
      6. Assembles deterministically
      7. Verifies integrity
      8. Evaluates gates
      9. Promotes only if all gates pass

    Args:
        proposal_id: The proposal to repair.
        experiment_result_id: The persisted ExperimentResult.
        original_paper_md: The original (blocked) paper text.
        spec: The experiment specification.
        source_map: The frozen source map.
        result_markers: The frozen result markers.
        max_provider_calls: Maximum provider calls (default 1).
        timeout_seconds: Provider timeout.
        provider_call_fn: Optional override for the provider call (for testing).

    Returns:
        TargetedRevisionResult with the outcome.
    """
    original_hash = hashlib.sha256(original_paper_md.encode()).hexdigest()
    original_parsed = parse_paper(original_paper_md)

    # ── Step 1: Derive repair findings ──────────────────────────────
    findings = derive_repair_findings(
        paper_md=original_paper_md,
        spec_method=spec.analysis_method,
        spec_dataset=spec.dataset_name,
        spec_baseline=spec.baseline_method,
        spec_comparison=spec.comparison_method,
    )

    if not findings:
        return TargetedRevisionResult(
            success=False, promoted=False, revision_number=0,
            eval_status="blocked", error="No repair findings derived",
            original_paper_hash=original_hash, revised_paper_hash=original_hash,
            findings_count=0,
        )

    # Identify sections to replace
    defective_sections = set(f.section for f in findings)
    defective_section_texts = {}
    for section_name in defective_sections:
        section = original_parsed.get_section(section_name)
        if section:
            defective_section_texts[section_name] = section.full_text

    # ── Step 2: Build targeted directive ────────────────────────────
    from backend.pipeline.evaluation.revision_directive import EvidenceInvariant
    result_map_tuple = tuple((m.marker, m.observed_value) for m in result_markers)
    source_map_tuple = tuple(f"[{e.get('marker', '').strip('[]')}]" for e in (source_map or []))

    # Load manifest hash
    from backend.db.database import get_session
    from backend.db.models import ExperimentResult
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
        analysis_code_hash="",
    )

    directive = TargetedRevisionDirective(
        original_paper_hash=original_hash,
        allowed_sections=tuple(defective_sections),
        findings=tuple(findings),
        executed_method=spec.analysis_method,
        executed_dataset=spec.dataset_name,
        baseline_method=spec.baseline_method,
        comparison_method=spec.comparison_method,
        primary_metric=spec.primary_metric,
        metric_direction=spec.metric_directions.get(spec.primary_metric, ""),
        research_question=spec.research_question,
        task_type=spec.task_type,
        target_name=spec.target_name,
        split_method=spec.split_method,
        random_seed=spec.random_seed,
        evidence=evidence,
    )

    # ── Step 3: Call provider for replacement sections ──────────────
    prompt = directive.build_provider_prompt(defective_section_texts)

    if provider_call_fn:
        # Test mode: use the provided function
        replacement_sections = provider_call_fn(prompt, defective_sections)
    else:
        # Live mode: call the actual provider
        import asyncio

        from backend.config import get_settings
        from backend.providers.provider_factory import get_generation_provider

        settings = get_settings()
        provider = get_generation_provider(settings)

        try:
            response = await asyncio.wait_for(
                provider.complete(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=4096,
                ),
                timeout=timeout_seconds,
            )
            # Parse the JSON response
            replacement_sections = _parse_replacement_response(response, defective_sections)
        except Exception as e:
            logger.error("Targeted revision provider call failed: %s", e)
            return TargetedRevisionResult(
                success=False, promoted=False, revision_number=1,
                eval_status="blocked", error=str(e),
                original_paper_hash=original_hash, revised_paper_hash=original_hash,
                findings_count=len(findings),
            )

    if not replacement_sections:
        return TargetedRevisionResult(
            success=False, promoted=False, revision_number=1,
            eval_status="blocked", error="No replacement sections returned",
            original_paper_hash=original_hash, revised_paper_hash=original_hash,
            findings_count=len(findings),
        )

    # ── Step 4: Assemble deterministically ──────────────────────────
    revised_paper_md = assemble_paper(original_parsed, replacement_sections)

    # ── Step 5: Validate integrity ──────────────────────────────────
    ok, violations = validate_targeted_revision(
        original_parsed=original_parsed,
        replacement_sections=replacement_sections,
        allowed_sections=defective_sections,
        evidence=evidence,
        revised_paper_md=revised_paper_md,
    )

    if not ok:
        logger.warning("Targeted revision validation failed: %s", violations)
        return TargetedRevisionResult(
            success=False, promoted=False, revision_number=1,
            eval_status="blocked", invariant_violations=violations,
            original_paper_hash=original_hash,
            revised_paper_hash=hashlib.sha256(revised_paper_md.encode()).hexdigest(),
            findings_count=len(findings),
            changed_sections=list(replacement_sections.keys()),
        )

    # ── Step 6: Evaluate gates ──────────────────────────────────────
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

    # ── Step 7: Record unchanged section hashes ─────────────────────
    revised_parsed = parse_paper(revised_paper_md)
    unchanged_hashes = {}
    for section in original_parsed.sections:
        if section.name not in replacement_sections:
            revised_section = revised_parsed.get_section(section.name)
            if revised_section:
                unchanged_hashes[section.name] = revised_section.hash

    revised_hash = hashlib.sha256(revised_paper_md.encode()).hexdigest()

    # ── Step 8: Promote only if ready ───────────────────────────────
    promoted = (gate_eval.status == "ready")
    if promoted:
        from backend.db.database import get_session
        from backend.db.models import Proposal
        with get_session() as session:
            proposal = session.get(Proposal, proposal_id)
            if proposal:
                from backend.pipeline.evaluation.paper_release import (
                    load_paper_meta,
                    record_successor_revision_if_released,
                    write_paper_meta,
                )
                record_successor_revision_if_released(
                    session,
                    proposal,
                    revised_paper_md,
                    eval_status=gate_eval.status,
                    gates=gate_eval.gates,
                    source="targeted_remediation",
                    trigger="post_release_targeted_repair",
                    experiment_result_id=experiment_result_id,
                )
                meta = load_paper_meta(proposal)
                meta["paper_evaluation"] = {
                    "status": gate_eval.status,
                    "scope": "paper",
                    "paper_hash": revised_hash,
                    "gates": gate_eval.gates,
                    "blocking_reasons": gate_eval.blocking_reasons or None,
                }
                # Sync metadata so _evaluate_paper reads the promoted text
                fp = meta.get("full_paper")
                if isinstance(fp, dict):
                    fp["paper_markdown"] = revised_paper_md
                    meta["full_paper"] = fp
                proposal.paper_md = revised_paper_md
                write_paper_meta(proposal, meta)
                session.commit()
        logger.info("Targeted revision promoted for proposal %d", proposal_id)
    else:
        logger.info("Targeted revision blocked for proposal %d: %s", proposal_id, gate_eval.blocking_reasons)

    return TargetedRevisionResult(
        success=True,
        promoted=promoted,
        revision_number=1,
        eval_status=gate_eval.status,
        gates=gate_eval.gates,
        blocking_reasons=gate_eval.blocking_reasons,
        changed_sections=list(replacement_sections.keys()),
        unchanged_section_hashes=unchanged_hashes,
        original_paper_hash=original_hash,
        revised_paper_hash=revised_hash,
        findings_count=len(findings),
    )


def _parse_replacement_response(
    response: str,
    expected_sections: set[str],
) -> dict[str, str] | None:
    """Parse a provider response containing replacement sections.

    Expected format:
    ```json
    {
      "replacement_sections": {
        "abstract": "...",
        "conclusion": "..."
      }
    }
    ```
    """
    import re

    # Try to extract JSON from the response
    # Look for the outermost JSON object containing replacement_sections
    json_match = re.search(r'\{.*"replacement_sections".*\}', response, re.DOTALL)
    if not json_match:
        # Try to find a code block with JSON
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)

    if not json_match:
        logger.warning("Could not parse replacement_sections from response")
        return None

    try:
        data = json.loads(json_match.group(0))
        replacements = data.get("replacement_sections", {})
        # Validate: only expected sections
        valid = {}
        for section_name, text in replacements.items():
            if section_name in expected_sections:
                valid[section_name] = text
        return valid if valid else None
    except json.JSONDecodeError:
        logger.warning("Invalid JSON in replacement response")
        return None
