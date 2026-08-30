"""One-attempt, evidence-constrained paper remediation."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass

from sqlalchemy import select

from backend.db.database import get_session
from backend.db.models import ExperimentResult, PaperRevision
from backend.pipeline.evaluation.claim_result_validator import (
    validate_claim_result_alignment,
)
from backend.pipeline.evaluation.paper_sections import parse_paper
from backend.pipeline.gateway.transport import GatewayTransportError

logger = logging.getLogger(__name__)

_EMPIRICAL_PATTERNS = (
    re.compile(r"\bwe\s+demonstrate\b", re.I),
    re.compile(r"\bdemonstrates?\s+that\b", re.I),
    re.compile(r"\bexperimental\s+results?\b.{0,40}\b(show|indicate)\b", re.I),
    re.compile(r"\bresults?\s+(show|indicate)\s+that\b", re.I),
)
_RESULT_RE = re.compile(r"\[RESULT-\d+\]")


@dataclass
class RemediationResult:
    success: bool
    promoted: bool
    revision_number: int
    eval_status: str
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


def derive_numeric_repair_targets(paper_md: str, result_markers: list) -> tuple:
    """Transport existing numeric-validator findings into the revision prompt."""
    marker_by_bracket = {f"[{m.marker}]": m for m in (result_markers or [])}
    targets = []
    for mismatch in validate_claim_result_alignment(paper_md, list(result_markers or [])):
        if mismatch.section != "numeric_fidelity":
            continue
        marker_obj = marker_by_bracket.get(mismatch.marker)
        rendered = (
            mismatch.claim_text.split()[1]
            if mismatch.claim_text.startswith("rendered ") else ""
        )
        targets.append({
            "marker": mismatch.marker,
            "rendered_value": rendered,
            "required_value": marker_obj.observed_value if marker_obj else None,
            "metric_name": mismatch.marker_metric,
            "role": mismatch.marker_role,
            "experiment_result_id": (
                marker_obj.experiment_result_id if marker_obj else None
            ),
            "artifact_path": marker_obj.artifact_path if marker_obj else "",
            "artifact_sha256": marker_obj.artifact_sha256 if marker_obj else "",
        })
    context = tuple(
        (f"[{m.marker}]", m.metric_name, getattr(m, "role", ""), m.observed_value)
        for m in (result_markers or [])
    )
    return tuple(targets), context


def _sentences(text: str) -> list[tuple[str, str]]:
    parts = re.split(r"(?<=[.!?])(\s+)", text)
    return [
        (parts[i], parts[i + 1] if i + 1 < len(parts) else "")
        for i in range(0, len(parts), 2)
    ]


def _empirical(sentence: str) -> bool:
    return any(p.search(sentence) for p in _EMPIRICAL_PATTERNS)


def _backed_mappings(paper_md: str) -> dict[str, set[frozenset[str]]]:
    parsed = parse_paper(paper_md)
    out: dict[str, set[frozenset[str]]] = {}
    for name in ("abstract", "conclusion"):
        section = parsed.get_section(name)
        if not section:
            continue
        for sentence, _ in _sentences(section.body):
            markers = frozenset(_RESULT_RE.findall(sentence))
            if _empirical(sentence) and markers:
                out.setdefault(name, set()).add(markers)
    return out


def _unbacked_sections(paper_md: str) -> set[str]:
    parsed = parse_paper(paper_md)
    out = set()
    for name in ("abstract", "conclusion"):
        section = parsed.get_section(name)
        if section and any(
            _empirical(s) and not _RESULT_RE.search(s) for s, _ in _sentences(section.body)
        ):
            out.add(name)
    return out


def _derive_repair_sections(
    paper_md: str,
    blocking_findings: list[str],
    numeric_repair_targets: tuple,
    result_markers: list,
    claim_result,
) -> tuple[str, ...]:
    """Map existing diagnostics to the smallest existing editable section set."""
    parsed = parse_paper(paper_md)
    selected: set[str] = set()
    markers = {t["marker"] for t in numeric_repair_targets}
    markers.update(
        m.marker for m in validate_claim_result_alignment(paper_md, result_markers or [])
    )
    for section in parsed.sections:
        if section.name != "references" and any(m in section.full_text for m in markers):
            selected.add(section.name)

    text = "\n".join(map(str, blocking_findings or [])).lower()
    if "conclusion" in text:
        selected.update({"abstract", "conclusion"})
    if "scope" in text:
        selected.add("abstract")
    if "experiment_alignment" in text or "experiment alignment" in text:
        selected.update({"abstract", "conclusion"})
    if "method_fidelity" in text or "method fidelity" in text or "methodology" in text:
        selected.add("methods")
    if "contribution" in text:
        selected.update({"abstract", "introduction"})
    if getattr(claim_result, "unexecuted_method_in_abstract", None):
        selected.add("abstract")
    if getattr(claim_result, "unexecuted_method_in_conclusion", None):
        selected.add("conclusion")
    selected.update(_unbacked_sections(paper_md))

    existing = {s.name for s in parsed.sections}
    selected &= existing
    selected -= {"references", "title"}
    if not selected:
        selected.update(name for name in ("abstract", "conclusion") if name in existing)
    return tuple(s.name for s in parsed.sections if s.name in selected)


def _build_scoped_revision_prompt(paper_md: str, directive, targets: tuple[str, ...]) -> str:
    parsed = parse_paper(paper_md)
    lines = [
        "## DEFECT-SCOPED PAPER REVISION",
        "Revise ONLY the sections below. Untargeted paper bytes are immutable.",
        "Do not return a full paper or an unlisted section.",
        "",
        directive.build_revision_prompt(),
        "",
        "## TARGET SECTIONS",
    ]
    for name in targets:
        section = parsed.get_section(name)
        lines.extend([f"### TARGET: {name}", section.full_text if section else ""])
    lines.extend([
        "",
        "## REQUIRED OUTPUT FORMAT",
        "Return every target exactly once, including its unchanged heading:",
    ])
    for name in targets:
        lines.extend([
            f"<<<SECTION:{name}>>>",
            f"<full revised {name} section>",
            "<<<END_SECTION>>>",
        ])
    lines.extend([
        "Do not invent RESULT or SOURCE markers or change correct values.",
        "Unsupported Abstract/Conclusion empirical assertions may be removed or weakened.",
    ])
    return "\n".join(lines)


def _parse_scoped_replacements(
    response: str, targets: tuple[str, ...], paper_md: str,
) -> dict[str, str] | None:
    parsed = parse_paper(paper_md)
    expected = set(targets)
    found: dict[str, str] = {}
    pattern = re.compile(
        r"<<<SECTION:(?P<name>[a-z_]+)>>>\s*\n?(?P<text>.*?)\n?<<<END_SECTION>>>",
        re.S,
    )
    for match in pattern.finditer(response or ""):
        name, text = match.group("name"), match.group("text").strip("\n")
        section = parsed.get_section(name)
        if name not in expected or name in found or not section or not text.strip():
            return None
        if text.split("\n", 1)[0].strip() != section.heading:
            return None
        found[name] = text
    return found if set(found) == expected else None


def _assemble_scoped_candidate(original: str, replacements: dict[str, str]) -> str:
    parsed = parse_paper(original)
    edits = []
    for name, replacement in replacements.items():
        section = parsed.get_section(name)
        if not section:
            raise ValueError(f"Unknown target section: {name}")
        span = original[section.start:section.end]
        suffix_match = re.search(r"\s*$", span)
        suffix = suffix_match.group(0) if suffix_match else ""
        edits.append((section.start, section.end, replacement.rstrip() + suffix))
    revised = original
    for start, end, replacement in sorted(edits, reverse=True):
        revised = revised[:start] + replacement + revised[end:]
    return revised


def _finalize_conclusion_support(
    original: str, revised: str, allowed_sections: tuple[str, ...],
) -> tuple[str, list[str], list[str]]:
    """Remove new/unbacked strong claims; never add a RESULT mapping."""
    backed, allowed = _backed_mappings(original), set(allowed_sections)
    parsed = parse_paper(revised)
    replacements, removed, violations = {}, [], []
    for name in ("abstract", "conclusion"):
        section = parsed.get_section(name)
        if not section:
            continue
        kept, changed = [], False
        for sentence, ws in _sentences(section.body):
            if not _empirical(sentence):
                kept.extend([sentence, ws])
                continue
            markers = frozenset(_RESULT_RE.findall(sentence))
            if markers and markers in backed.get(name, set()):
                kept.extend([sentence, ws])
            elif name not in allowed:
                violations.append(f"unbacked empirical claim in untargeted {name}")
                kept.extend([sentence, ws])
            else:
                changed = True
                removed.append(sentence.strip())
        if changed:
            body = "".join(kept).strip("\n")
            replacements[name] = section.heading + "\n" + body
    if violations or not replacements:
        return revised, removed, violations
    return _assemble_scoped_candidate(revised, replacements), removed, []


def _blocked(
    original_hash: str,
    blocking_findings: list[str],
    error: str,
    revised_hash: str | None = None,
    violations: list[str] | None = None,
) -> RemediationResult:
    return RemediationResult(
        success=False,
        promoted=False,
        revision_number=1,
        eval_status="blocked",
        gates=[],
        blocking_reasons=blocking_findings,
        original_paper_hash=original_hash,
        revised_paper_hash=revised_hash or original_hash,
        invariant_violations=violations or [],
        error=error,
    )


async def auto_revise_paper(
    proposal_id: int,
    experiment_result_id: int,
    original_paper_md: str,
    blocking_findings: list[str],
    source_map: list[dict],
    result_markers: list,
    spec,
    timeout_seconds: float = 600.0,
    method_facts: dict | None = None,
) -> RemediationResult:
    """Produce one defect-scoped candidate; the API route owns promotion."""
    from backend.pipeline.evaluation.claim_alignment import evaluate_claim_alignment
    from backend.pipeline.evaluation.revision_directive import (
        EvidenceInvariant,
        RevisionDirective,
        verify_revised_paper_invariants,
    )

    original_hash = hashlib.sha256(original_paper_md.encode()).hexdigest()
    result_map = tuple((m.marker, m.observed_value) for m in result_markers)
    source_ids = tuple(
        f"[{entry.get('marker', '').strip('[]')}]" for entry in (source_map or [])
    )
    with get_session() as session:
        exp = session.get(ExperimentResult, experiment_result_id)
        manifest_hash = hashlib.sha256(
            (exp.manifest_json or "").encode()
        ).hexdigest() if exp and exp.manifest_json else ""
    evidence = EvidenceInvariant(
        result_map=result_map,
        source_map=source_ids,
        experiment_manifest_hash=manifest_hash,
        dataset_hash=spec.dataset_raw_sha256,
        analysis_code_hash="",
    )

    parent_id = None
    try:
        with get_session() as session:
            rev0 = session.execute(select(PaperRevision).where(
                PaperRevision.proposal_id == proposal_id,
                PaperRevision.revision_number == 0,
            )).scalar_one_or_none()
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
                session.commit()
            parent_id = rev0.id
    except Exception as exc:
        logger.error("Failed to store revision 0: %s", exc)

    try:
        with get_session() as session:
            existing = session.execute(select(PaperRevision).where(
                PaperRevision.proposal_id == proposal_id,
                PaperRevision.revision_number == 1,
            )).scalar_one_or_none()
            if existing:
                detail = {}
                if existing.trigger_detail_json:
                    try:
                        detail = json.loads(existing.trigger_detail_json)
                    except Exception:
                        detail = {}
                authoritative = detail.get("authoritative")
                if authoritative:
                    status = authoritative.get("status", existing.eval_status)
                    return RemediationResult(
                        True, status == "ready", 1, status,
                        authoritative.get(
                            "gates",
                            json.loads(existing.gates_json) if existing.gates_json else [],
                        ),
                        detail.get("blocking_findings", []),
                        original_hash, existing.paper_hash, [],
                    )
                return RemediationResult(
                    True, False, 1, existing.eval_status,
                    json.loads(existing.gates_json) if existing.gates_json else [],
                    detail.get("blocking_findings", []),
                    original_hash, existing.paper_hash, [],
                )
    except Exception as exc:
        logger.error("Failed to inspect revision 1: %s", exc)
        return RemediationResult(
            False, False, 0, "blocked", [], blocking_findings,
            original_hash, original_hash, [], str(exc),
        )

    claim_result = evaluate_claim_alignment(
        paper_md=original_paper_md,
        spec_method=spec.analysis_method,
        spec_dataset=spec.dataset_name,
        spec_baseline=spec.baseline_method,
        spec_comparison=spec.comparison_method,
    )
    numeric_targets, result_context = derive_numeric_repair_targets(
        original_paper_md, result_markers,
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
        numeric_repair_targets=numeric_targets,
        result_context=result_context,
    )
    targets = _derive_repair_sections(
        original_paper_md, blocking_findings, numeric_targets,
        result_markers, claim_result,
    )
    if not targets:
        _persist_revision(
            proposal_id, experiment_result_id, parent_id, original_paper_md,
            "auto_remediation", "alignment_blocked", blocking_findings,
            directive, "blocked", [], evidence,
        )
        return _blocked(original_hash, blocking_findings, "no_repairable_sections")

    from backend.config import get_settings
    from backend.providers.provider_factory import get_generation_provider

    provider = get_generation_provider(get_settings())
    prompt = _build_scoped_revision_prompt(original_paper_md, directive, targets)
    try:
        response = await asyncio.wait_for(
            provider.complete(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=32768,
            ),
            timeout=timeout_seconds,
        )
    except GatewayTransportError:
        raise
    except TimeoutError:
        logger.error("Revision synthesis timed out after %.1fs", timeout_seconds)
        _persist_revision(
            proposal_id, experiment_result_id, parent_id, original_paper_md,
            "auto_remediation", "alignment_blocked", blocking_findings,
            directive, "blocked", [], evidence,
        )
        return _blocked(original_hash, blocking_findings, "revision_timeout")
    except Exception as exc:
        logger.error("Revision synthesis failed: %s", exc)
        response = ""

    replacements = _parse_scoped_replacements(response or "", targets, original_paper_md)
    if not replacements:
        _persist_revision(
            proposal_id, experiment_result_id, parent_id, original_paper_md,
            "auto_remediation", "alignment_blocked", blocking_findings,
            directive, "blocked", [], evidence,
        )
        return _blocked(
            original_hash, blocking_findings, "invalid_scoped_revision_output",
        )

    revised = _assemble_scoped_candidate(original_paper_md, replacements)
    revised, removed, finalizer_violations = _finalize_conclusion_support(
        original_paper_md, revised, targets,
    )
    if removed:
        logger.info("R4 finalizer removed %d unsupported empirical claim(s)", len(removed))
    revised_hash = hashlib.sha256(revised.encode()).hexdigest()
    if finalizer_violations:
        _persist_revision(
            proposal_id, experiment_result_id, parent_id, revised,
            "auto_remediation", "alignment_blocked", blocking_findings,
            directive, "blocked", [], evidence,
        )
        return _blocked(
            original_hash, blocking_findings,
            "conclusion_support_postcondition_failed", revised_hash,
            finalizer_violations,
        )

    ok, violations = verify_revised_paper_invariants(revised, evidence)
    if not ok:
        _persist_revision(
            proposal_id, experiment_result_id, parent_id, revised,
            "auto_remediation", "alignment_blocked", blocking_findings,
            directive, "blocked", [], evidence,
        )
        return _blocked(
            original_hash, blocking_findings, "", revised_hash, violations,
        )

    from backend.pipeline.evaluation.paper_gate_evaluator import evaluate_paper_gates

    gate_eval = evaluate_paper_gates(
        paper_md=revised,
        source_map=source_map,
        research_intent=spec.research_question,
        domain=spec.task_type or "machine learning",
        result_markers=result_markers,
        spec_method=spec.analysis_method,
        spec_dataset=spec.dataset_name,
        spec_baseline=spec.baseline_method,
        spec_comparison=spec.comparison_method,
    )
    _persist_revision(
        proposal_id, experiment_result_id, parent_id, revised,
        "auto_remediation", "alignment_blocked", blocking_findings,
        directive, gate_eval.status, gate_eval.gates, evidence,
    )
    return RemediationResult(
        True, False, 1, gate_eval.status, gate_eval.gates,
        gate_eval.blocking_reasons, original_hash, revised_hash, [],
    )


def _persist_revision(
    proposal_id, experiment_result_id, parent_id, paper_md,
    source, trigger, blocking_findings, directive, eval_status,
    gates, evidence,
):
    paper_hash = hashlib.sha256(paper_md.encode()).hexdigest()
    with get_session() as session:
        session.add(PaperRevision(
            proposal_id=proposal_id,
            experiment_result_id=experiment_result_id,
            revision_number=1,
            parent_revision_id=parent_id,
            paper_md=paper_md,
            paper_hash=paper_hash,
            source=source,
            trigger=trigger,
            trigger_detail_json=json.dumps({"blocking_findings": blocking_findings}),
            directive_json=json.dumps(directive.to_dict()),
            eval_status=eval_status,
            gates_json=json.dumps(gates),
            experiment_manifest_hash=evidence.experiment_manifest_hash,
            result_map_hash=evidence.result_map_hash,
            source_map_hash=evidence.source_map_hash,
        ))
        session.commit()
